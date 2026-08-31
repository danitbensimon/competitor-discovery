// v3 <-> legacy normalisation for /companies-using/[slug].
//
// v3 run_search.py emits: product/domain/slug/generated/total/verified/
// core_icp/signal_group_report/preview/companies, with per-row company/
// confidence(Verified+|Verified|Likely)/quote/employees/icp_fit/signal_group.
// The committed files still use the legacy shape (competitor{}/company_count/
// generated_at, per-row name/grade/evidence). This shim renders BOTH so the
// live pages never break, and drives everything off `confidence`.
//
// Lives in its own module because Astro runs getStaticPaths() in isolation —
// helpers must be importable, not just declared in the .astro frontmatter.

export const CONF_RANK = { 'Verified+': 0, Verified: 1, Likely: 2 };
export const FIT_RANK = { core: 0, size_only: 1, unknown: 2, outside: 3 };

export function normalizeCompany(c) {
  let confidence = c.confidence;
  if (!confidence) confidence = c.grade === 'A' ? 'Verified+' : c.grade === 'B' ? 'Verified' : 'Likely';
  const company = c.company ?? c.name ?? '';
  const quote = c.quote ?? c.evidence ?? '';
  return {
    ...c,
    name: company,
    company,
    domain: c.domain ?? '',
    employees: c.employees ?? null,
    employees_evidence: c.employees_evidence ?? null,
    industry: c.industry ?? '',
    country: c.country ?? '',
    signal_group: c.signal_group ?? c.signal_groups ?? '',
    confidence,
    quote,
    evidence: quote,
    source_url: c.source_url ?? '',
    icp_fit: c.icp_fit ?? 'unknown',
    date_found: c.date_found ?? '',
  };
}

export function normalizeData(raw) {
  const competitor = raw.competitor ?? { name: raw.product, slug: raw.slug, domain: raw.domain };
  const companies = (raw.companies ?? []).map(normalizeCompany);
  // Strongest first: ICP fit, then confidence, then name. v3 is already sorted
  // this way; sorting again is idempotent and rescues legacy/unsorted files.
  companies.sort((a, b) =>
    (FIT_RANK[a.icp_fit] ?? 2) - (FIT_RANK[b.icp_fit] ?? 2) ||
    (CONF_RANK[a.confidence] ?? 3) - (CONF_RANK[b.confidence] ?? 3) ||
    a.name.localeCompare(b.name));
  const company_count = raw.total ?? raw.company_count ?? companies.length;
  const generated_at = raw.generated ?? raw.generated_at;
  // Prompt: render `preview` (best 15, pre-sorted) directly — never a raw
  // companies[0:15]. Legacy files have no preview, so take the best 15 sorted.
  const preview = (Array.isArray(raw.preview) && raw.preview.length)
    ? raw.preview.map(normalizeCompany)
    : companies.slice(0, 15);
  return {
    ...raw,
    competitor,
    companies,
    company_count,
    generated_at,
    preview,
    core_icp: raw.core_icp ?? null,
    verified: raw.verified ?? companies.filter((c) => (c.confidence || '').startsWith('Verified')).length,
    signal_group_report: raw.signal_group_report ?? [],
  };
}

export function confStyle(cf) {
  if (cf === 'Verified+') return 'background:linear-gradient(135deg,#4B3BFF,#7C3AED);color:#fff;border:none;';
  if (cf === 'Verified') return 'background:#EEF0FF;color:#4B3BFF;border:1px solid #DBE0FF;';
  return 'background:#F1F1F4;color:#6A6A74;border:1px solid #E4E4EA;';
}
