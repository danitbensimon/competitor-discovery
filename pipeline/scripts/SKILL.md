---
name: competitor-iq
description: "Run a full CompetitorIQ search to discover every company using a competitor's product. Use this skill EVERY TIME the user wants to find customers of a competitor, discover who's using a competitor tool, research a competitor's customer base, or export a list of companies using a specific product. Triggers for: 'find customers of X', 'who uses X', 'discover companies using X', 'run competitor search for X', 'get customer list for X', 'research X's customers', 'CompetitorIQ search', or any request to find companies that are customers of a named tool or domain."
---

# CompetitorIQ (v3 — parallel pipeline)

Find every NAMED company using a competitor's product, prove each with a source,
export to JSON (for competitorcustomer.com) and Excel (for humans).

## Two modes. Use Mode A unless it is impossible.

### Mode A — the pipeline (default)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python scripts/run_search.py anaplan.com "Anaplan" --out ./data
python scripts/export_xlsx.py data/anaplan.json
```

All 12 groups, concurrent, batched 5. ~20-30s. ~$0.25-2.00 per competitor
($10 per 1,000 searches + tokens). Outputs `data/<slug>.json` for the Astro site
and `data/<slug>.xlsx`.

**Why this is the default:** it runs all 12 groups every time and never rations.

### Mode B — chat fallback

Only when there is no API key. Claude runs the searches with `web_search`
directly. It is sequential (~2 min), and the failure mode is real: **a human
rationing searches stops around group 7 and silently under-delivers by ~2x.**
A documented run produced 56 companies from 4 groups; the same target reached 95
once the remaining groups were run. If using Mode B, say up front that it is
partial and follow every rule below.

## Non-negotiable rules (both modes)

1. **Every row: a named company + source URL + verbatim quote.** No proof, no row.
2. **Never estimate headcount.** Use the number only if a source states it, and
   store the exact wording next to it. No source = `null`, resolved downstream in
   Clay (Crunchbase/Dealroom). A guessed size is worse than a blank.
3. **All 12 groups, every run.** A group returning 0 is a *finding*, not a gap.
   Never skip a group on a prediction — spend the query and let the result decide.
4. **Print the Signal Group Report before exporting.** No report, no export.
5. **Volume is not the goal — ICP fit is.** Report the ICP-relevant count next to
   the headline. 100 enterprise logos for a mid-market ICP is a failed run.
6. **Stop rule:** stop only after 2 consecutive rounds each add <5 new companies.
   Stopping for budget/time is allowed but must be *declared*, not hidden.

## The 12 signal groups — measured yield per query

Real numbers, Anaplan/Vena/Planful, Jul 2026. Order is by yield.

| # | Group | Yield | Note |
|---|---|---|---|
| 1 | `partners_si` | ~6 | **Richest.** SI/partner sites name the mid-market customers the vendor omits. |
| 2 | `own_site` | ~6 | High volume, skews enterprise — often the wrong ICP. |
| 3 | `job_postings` | ~4 | **Best for ICP-sized targets.** Hiring "X model builder" = runs X now, at scale. Found Monzo, Legal & General, Greystar — none in any case study. |
| 4 | `review_sites` | ~2 | (A one-off 9 came from a vendor G2 blurb listing customers.) |
| 5 | `blog_press` | ~5 | "selects/chooses/implements X". Reliable. |
| 6 | `tech_stack` | ~3 | Always `Likely` — no second source. Buyer-intent tables flag *evaluating* companies. |
| 7 | `linkedin` | ~5 | Vendor's own posts name customer stories. |
| 8 | `video` | untested | |
| 9 | `communities` | ~0 | Great *quotes* (pain evidence), rarely names employers. Use for messaging, not sourcing. |
| 10 | `events_awards` | ~0 | **Trap:** vendor conferences pay celebrity keynotes (Chris Voss, Robert Cialdini). NOT customers. |
| 11 | `customer_signals` | ~0 | "we use X" is swamped by vendor comparison blogs. |
| 12 | `filings_docs` | untested | FP&A tools rarely named in filings. |

Yields shift by product. Update this table when a run contradicts it.

## Scoring

- **Verified+** — 2+ signal groups agree. Strongest.
- **Verified** — named + URL + quote proving use.
- **Likely** — database listing only (Enlyft/ARTW/BuiltWith), no second source.
- Exclude the vendor itself; exclude resellers unless they state internal use.
- Dedupe on normalised domain, then name.

## ICP fit

Scorable **only** where a source stated size. `core` = right geography AND inside
the size band. Everything else: `unknown - enrich`. Never guessed.

## Site output (competitorcustomer.com)

`data/<slug>.json` feeds `/companies-using/[slug]`. Astro builds static pages, so
the visitor waits ~0.5s and Googlebot sees real HTML — **never search on page load.**
`preview` = the best 15 rows (sorted by ICP fit, then confidence), not the first 15.
Refresh weekly via CI; commit the JSON to the repo.

## Layers (don't confuse them)

| Layer | What | Cost |
|---|---|---|
| Anthropic API + web_search | finds pages **and** judges them | ~$1-2/competitor |
| TheirStack / BuiltWith / Apify | structured technographics at scale | subscription |
| The 12-group taxonomy + proof rules | **the actual IP** | yours |

Brave is not needed: the Anthropic web_search tool searches *and* reads in one call.
A raw search API returns links; something still has to decide Huel is a customer and
Chris Voss is not.
