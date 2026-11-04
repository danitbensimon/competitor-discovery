import { getCollection } from 'astro:content';

export async function GET() {
  const files = import.meta.glob('../data/competitors/*.json', { eager: true });
  const lists = Object.values(files)
    .map((d) => ({ name: d.competitor.name, slug: d.competitor.slug, count: d.company_count, date: d.generated_at.slice(0, 10) }))
    .sort((a, b) => a.name.localeCompare(b.name));
  const posts = (await getCollection('blog', ({ data }) => !data.draft)).sort((a, b) => b.data.date - a.data.date);
  const site = 'https://competitorcustomer.com';
  const lines = [
    '# CompetitorIQ',
    '> Evidence-verified lists of companies using B2B products. Every company is backed by a public source URL (case study, job post, review, trust page). Free to browse and download.',
    '',
    '## Customer lists',
    ...lists.map((l) => `- [Who uses ${l.name}? ${l.count} verified customers](${site}/companies-using/${l.slug}/): verified ${l.date}`),
  ];
  if (posts.length) {
    lines.push('', '## Guides');
    posts.forEach((p) => lines.push(`- [${p.data.title}](${site}/blog/${p.slug}/): ${p.data.answer}`));
  }
  lines.push('', '## Run a search', `- [CompetitorIQ live search](${site}/): enter any competitor domain, get 10 companies using it free.`);
  return new Response(lines.join('\n') + '\n', { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
}
