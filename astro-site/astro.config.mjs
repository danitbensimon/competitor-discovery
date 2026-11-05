import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import rehypeCompanyCards from './src/lib/rehype-company-cards.mjs';

export default defineConfig({
  site: 'https://competitorcustomer.com',
  integrations: [sitemap()],
  markdown: { rehypePlugins: [rehypeCompanyCards] },
});
