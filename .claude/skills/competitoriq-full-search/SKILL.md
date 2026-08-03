# CompetitorIQ Full Search Skill

Run a full (pro-tier) competitor customer search using CompetitorIQ and return all discovered companies across all 12 data sources.

## API base

The live backend is:

```
https://competitor-discovery.onrender.com
```

(The public site `competitorcustomer.com` is a static Vercel frontend and does NOT serve `/api/*` — calling it returns 404. Always hit the Render backend above.)

## The 12 sources

Two kinds of source run in one pass:

- **Page probes (no API key):** logo wall on the homepage/`/customers`/`/case-studies`, customer-index pages, and the XML sitemap. This is the PRIMARY source — the competitor's own page — and always runs.
- **Web-search signals (require `BRAVE_API_KEY` on the backend):** customer signals, job postings, tech-stack databases (BuiltWith, ZoomInfo, Enlyft, StackShare, G2), review sites (G2 / Capterra / Trustpilot), LinkedIn, and blog/press/Reddit.

If the results come back with **every company tagged `own_site` and nothing from any other signal group**, that is the tell that `BRAVE_API_KEY` is unset (or exhausted) on the backend — the 11 web-search sources are silently returning zero. Call this out in the output rather than reporting it as "no results found."

## Steps

1. POST to `https://competitor-discovery.onrender.com/api/search` with body:
```json
   { "domain": "<COMPETITOR_DOMAIN>", "brand": "", "tier": "pro", "mode": "live", "icp_industries": [], "icp_size": "", "icp_region": "" }
```
2. Save the returned `job_id`.
3. Poll `https://competitor-discovery.onrender.com/api/results/<job_id>` every 5 seconds until `status == "done"`.
4. Return the full company list as a formatted table: Company Name | Domain | Industry | Relationship | Signal Source | Confidence.
5. Save results to a CSV file in the workspace folder named `<domain>_<date>.csv`.

## Output

- Total companies found
- Full table of all companies
- A per-source breakdown (how many companies came from each signal group)
- An explicit note if only `own_site` returned (see "The 12 sources" above)
- CSV file saved to workspace
