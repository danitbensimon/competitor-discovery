#!/usr/bin/env python3
"""
CompetitorIQ v3 — parallel pipeline.

WHY THIS EXISTS
  The chat version runs ~40 searches one at a time (~2 min) and, because a human
  is rationing them, tends to stop at 7 of 12 groups. This runs all 12 groups
  concurrently and never rations. ~20-30s.

  Batched 5 at a time on purpose: firing all 12 at once rate-limits (learned the
  hard way in the May artifact run).

USAGE
  export ANTHROPIC_API_KEY=sk-ant-...
  python run_search.py anaplan.com "Anaplan"
  python run_search.py anaplan.com "Anaplan" --out ./data --icp-country UK

OUTPUT
  <out>/<brand>.json   -> for the Astro site (/companies-using/[slug])
  <out>/<brand>.xlsx   -> for humans
"""

import os
import sys
import json
import re
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

try:
    import anthropic
except ImportError:
    sys.exit("pip install anthropic")

# ----- config -------------------------------------------------------------
MODEL = os.environ.get("COMPETITORIQ_MODEL", "claude-haiku-4-5-20251001")
SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 4}
BATCH_SIZE = 5          # concurrent groups. >5 rate-limits.
PAUSE_BETWEEN_BATCHES = 2.0
TODAY = date.today().isoformat()

# ----- the 12 signal groups ----------------------------------------------
# Ordered by measured yield per query (see SKILL.md). partners_si first:
# partner/SI sites name the MID-MARKET customers the vendor's own site omits.
SIGNAL_GROUPS = [
    ("partners_si", [
        '"{p} implementation" case study -site:{d}',
        '"{p} partner" client success story',
        '{p} consulting partner customers list',
    ]),
    ("own_site", [
        'site:{d} customer story OR case study',
        '{p} customer stories page',
    ]),
    ("job_postings", [
        '"experience with {p}" jobs',
        '"{p} model builder" OR "{p} administrator" hiring',
        '{p} site:theirstack.com',
    ]),
    ("review_sites", [
        'site:g2.com {p} reviews',
        'site:capterra.com {p}',
        '{p} review "we switched"',
    ]),
    ("blog_press", [
        '"selects {p}" OR "chooses {p}" press release',
        '"goes live with {p}" OR "migrates to {p}"',
    ]),
    ("tech_stack", [
        'site:enlyft.com {p}',
        '"companies using {p}" list',
        'site:appsruntheworld.com {p}',
    ]),
    ("linkedin", [
        'site:linkedin.com "we chose {p}" OR "migrated to {p}"',
        'site:linkedin.com/posts {p} customer story',
    ]),
    ("video", [
        '{p} customer story site:youtube.com',
        '{p} testimonial video case study',
    ]),
    ("customer_signals", [
        '"powered by {p}" OR "we use {p}"',
    ]),
    ("communities", [
        'site:reddit.com "we use {p}"',
    ]),
    ("events_awards", [
        '{p} customer awards winners',
        '{p} user conference customer speakers',
    ]),
    ("filings_docs", [
        '{p} annual report vendor',
    ]),
]

# Groups where a naive read produces false positives. Warn the model explicitly.
GROUP_TRAPS = {
    "events_awards": (
        "CRITICAL: vendor conferences pay CELEBRITY KEYNOTES (authors, athletes, "
        "negotiation coaches). They are NOT customers. Only count speakers whose "
        "EMPLOYER is presenting their own use of the product, and award winners."
    ),
    "communities": (
        "Reddit posters usually do NOT name their employer. Only include a company "
        "if the poster explicitly names it. Do not infer."
    ),
    "tech_stack": (
        "Database listings have no second source. Mark every row from here as "
        "'Likely', never 'Verified'."
    ),
    "job_postings": (
        "The HIRING company is the user - not the recruitment agency posting the ad. "
        "If the ad is posted by a consultancy hiring for unnamed clients, skip it."
    ),
}

PROMPT = """Find companies that are CUSTOMERS of {product} (domain: {domain}).

Run these searches:
{queries}

RULES
- Only NAMED companies. Never "a Fortune 500 retailer".
- Every row needs a real source URL and a short verbatim quote proving usage.
- Exclude {product} itself, and exclude resellers/partners unless they state they
  use it internally.
- If a source states the company's employee count, capture it VERBATIM. If it does
  not, use null. NEVER estimate, infer, or recall headcount from memory.
- confidence: "Verified" = named + URL + quote proving use.
                "Likely"  = database listing only, no second source.
{trap}

Return ONLY a raw JSON array. No markdown, no preamble, no code fences.
[{{"company":"","domain":"","country":"","employees":null,"employees_evidence":null,"industry":"","confidence":"Verified","quote":"","source_url":""}}]
Return [] if nothing found."""


def run_group(client, group, queries, product, domain):
    """One API call per group. Claude searches AND judges in the same call."""
    q = "\n".join("- " + t.format(p=product, d=domain) for t in queries)
    prompt = PROMPT.format(
        product=product, domain=domain, queries=q,
        trap=GROUP_TRAPS.get(group, ""),
    )
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
            tools=[SEARCH_TOOL],
        )
    except Exception as e:
        return group, [], len(queries), f"ERROR: {type(e).__name__}"

    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    m = re.search(r"\[[\s\S]*\]", text)
    if not m:
        return group, [], len(queries), "no JSON returned"
    try:
        rows = json.loads(m.group(0))
    except json.JSONDecodeError:
        return group, [], len(queries), "bad JSON"

    out = []
    for r in rows:
        if not isinstance(r, dict) or not r.get("company"):
            continue
        if not r.get("source_url") or not r.get("quote"):
            continue                      # no proof -> no row. Non-negotiable.
        r["signal_group"] = group
        if group == "tech_stack":
            r["confidence"] = "Likely"
        r["date_found"] = TODAY
        out.append(r)
    return group, out, len(queries), "done"


def norm(name):
    n = (name or "").lower().strip()
    for suf in (" inc.", " inc", " ltd", " limited", " plc", " llc", " corp",
                " group", " gmbh", " s.a.", " co."):
        if n.endswith(suf):
            n = n[: -len(suf)]
    return re.sub(r"[^a-z0-9]", "", n)


def dedupe(rows):
    """One row per company. Multi-source companies get Verified+."""
    by = {}
    for r in rows:
        k = norm(r.get("domain") or "") or norm(r["company"])
        if k in by:
            prev = by[k]
            groups = set(prev["signal_group"].split(" + ")) | {r["signal_group"]}
            prev["signal_group"] = " + ".join(sorted(groups))
            if len(groups) > 1:
                prev["confidence"] = "Verified+"      # corroborated = strongest
            if not prev.get("employees") and r.get("employees"):
                prev["employees"] = r["employees"]
                prev["employees_evidence"] = r.get("employees_evidence")
            if prev["confidence"] == "Likely" and r["confidence"] == "Verified":
                prev.update({k2: r[k2] for k2 in ("confidence", "quote", "source_url")})
        else:
            by[k] = dict(r)
    return list(by.values())


def icp_fit(row, country="UK", lo=200, hi=2000):
    """Only scorable when a SOURCE stated the size. Otherwise: unknown."""
    emp = row.get("employees")
    if not emp:
        return "unknown"
    nums = [int(x.replace(",", "")) for x in re.findall(r"[\d,]+", str(emp))]
    if not nums:
        return "unknown"
    n = max(nums)
    geo = country.lower() in (row.get("country") or "").lower()
    size = lo <= n <= hi
    if geo and size:
        return "core"
    if size:
        return "size_only"
    return "outside"


def run(domain, product, out_dir, icp_country):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        sys.exit("ANTHROPIC_API_KEY not set.\n  export ANTHROPIC_API_KEY=sk-ant-...")
    client = anthropic.Anthropic(api_key=key)

    print(f"\nCompetitorIQ v3 — {product} ({domain})")
    print(f"  {len(SIGNAL_GROUPS)} groups | batches of {BATCH_SIZE} | {MODEL}\n")

    all_rows, report = [], []
    t0 = time.time()

    for i in range(0, len(SIGNAL_GROUPS), BATCH_SIZE):
        batch = SIGNAL_GROUPS[i:i + BATCH_SIZE]
        with ThreadPoolExecutor(max_workers=BATCH_SIZE) as ex:
            futs = {ex.submit(run_group, client, g, q, product, domain): g
                    for g, q in batch}
            for f in as_completed(futs):
                g, rows, nq, status = f.result()
                print(f"  {g:<18} {len(rows):>3} found   ({status})")
                all_rows += rows
                report.append({"group": g, "queries": nq,
                               "found": len(rows), "status": status})
        if i + BATCH_SIZE < len(SIGNAL_GROUPS):
            time.sleep(PAUSE_BETWEEN_BATCHES)

    companies = dedupe(all_rows)
    for c in companies:
        c["icp_fit"] = icp_fit(c, icp_country)

    rank = {"Verified+": 0, "Verified": 1, "Likely": 2}
    fitrank = {"core": 0, "size_only": 1, "unknown": 2, "outside": 3}
    companies.sort(key=lambda c: (fitrank[c["icp_fit"]],
                                  rank.get(c["confidence"], 3),
                                  c["company"]))

    elapsed = round(time.time() - t0, 1)
    searches = sum(r["queries"] for r in report)

    payload = {
        "product": product,
        "domain": domain,
        "slug": re.sub(r"[^a-z0-9]+", "-", product.lower()).strip("-"),
        "generated": TODAY,
        "elapsed_seconds": elapsed,
        "total": len(companies),
        "verified": sum(1 for c in companies if c["confidence"].startswith("Verified")),
        "core_icp": sum(1 for c in companies if c["icp_fit"] == "core"),
        "est_cost_usd": round(searches * 0.01, 2),   # $10/1k searches + tokens
        "signal_group_report": report,
        # the site shows the BEST 15, not the first 15 — already sorted
        "preview": companies[:15],
        "companies": companies,
    }

    os.makedirs(out_dir, exist_ok=True)
    jpath = os.path.join(out_dir, f"{payload['slug']}.json")
    with open(jpath, "w") as f:
        json.dump(payload, f, indent=2)

    skipped = [r["group"] for r in report if r["found"] == 0 and r["status"] != "done"]
    print(f"\n  {len(companies)} companies | {payload['core_icp']} core ICP "
          f"| {elapsed}s | ~${payload['est_cost_usd']} in searches")
    if skipped:
        print(f"  groups with errors: {', '.join(skipped)}")
    print(f"  -> {jpath}")
    return payload, jpath


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("domain")
    ap.add_argument("product", nargs="?")
    ap.add_argument("--out", default="./data")
    ap.add_argument("--icp-country", default="UK")
    a = ap.parse_args()
    d = re.sub(r"^https?://(www\.)?", "", a.domain).strip("/")
    p = a.product or d.split(".")[0].title()
    run(d, p, a.out, a.icp_country)
