# CompetitorIQ Full Search Skill

Run a full (pro-tier) competitor customer search using CompetitorIQ and return all discovered companies.

## Task

Given a competitor domain, run the full search pipeline against competitorcustomer.com using the pro tier (all query groups: customer signals, job postings, tech stack databases, review sites, LinkedIn, blog & press).

## Steps

1. POST to `https://competitorcustomer.com/api/search` with body:
```json
   { "domain": "<COMPETITOR_DOMAIN>", "brand": "", "tier": "pro", "mode": "live", "icp_industries": [], "icp_size": "", "icp_region": "" }
```
2. Save the returned `job_id`.
3. Poll `https://competitorcustomer.com/api/results/<job_id>` every 5 seconds until `status == "done"`.
4. Return the full company list as a formatted table: Company Name | Domain | Industry | Signal Source.
5. Save results to a CSV file in the workspace folder named `<domain>_<date>.csv`.

## Output

- Total companies found
- Full table of all companies
- CSV file saved to workspace
- Note any sources that returned results (G2, LinkedIn, case studies, etc.)
