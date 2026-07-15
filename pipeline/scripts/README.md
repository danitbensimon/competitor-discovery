# CompetitorIQ v3

## Install
    pip install anthropic openpyxl
    export ANTHROPIC_API_KEY=sk-ant-...     # get from console.anthropic.com

## Run
    python scripts/run_search.py anaplan.com "Anaplan" --out ./data
    python scripts/export_xlsx.py data/anaplan.json

## What changed from v2
- 12 groups (was 7), run CONCURRENTLY in batches of 5 (~20-30s, was ~2 min)
- Batching is deliberate: unbatched calls rate-limit
- Haiku 4.5 for extraction (fast + cheap); override with COMPETITORIQ_MODEL
- Never estimates headcount — sourced numbers only, with the quote
- Signal Group Report ships in every export (coverage proof)
- Outputs JSON for the Astro site + Excel for humans

## Cost
$10 per 1,000 searches + tokens. 25 queries/run ~= $0.25-2.00 per competitor.
Failed searches are not billed.

## For competitorcustomer.com
Commit data/<slug>.json to the repo; Astro builds static pages from it.
Never search on page load — Googlebot won't wait, and the page must exist to rank.
