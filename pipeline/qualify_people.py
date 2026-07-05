# qualify_people.py — Reads qualified_input_leads.csv and scores each person.
#
# For each row:
#   1. Check if jobTitle matches a target marketing leadership title → is_target_title
#   2. Visit companyUrl and classify B2B vs B2C from page content → is_b2b_company
#   3. Derive qualification_status and export to qualified_people.csv

import csv
import re
from fetch import fetch_page_text

INPUT_FILE = "qualified_input_leads.csv"
OUTPUT_FILE = "qualified_people.csv"

OUTPUT_FIELDS = [
    "firstname",
    "lastname",
    "jobTitle",
    "companyName",
    "companyUrl",
    "linkedinUrl",
    "is_target_title",
    "is_b2b_company",
    "qualification_status",
]

# Exact and partial title matches (case-insensitive)
TARGET_TITLES = [
    "cmo",
    "chief marketing officer",
    "vp marketing",
    "vice president of marketing",
    "head of marketing",
    "director of marketing",
    "marketing director",
]

# Signals found in page text (case-insensitive)
B2B_SIGNALS = [
    "request demo",
    "request a demo",
    "contact sales",
    "talk to sales",
    "enterprise",
    "platform",
    "solutions",
    "for teams",
]

B2C_SIGNALS = [
    "shop",
    "buy now",
    "store",
    "add to cart",
]


# ── Step 1: Title matching ────────────────────────────────────────────────────

def is_target_title(job_title: str) -> bool:
    """Returns True if the job title matches one of the target marketing titles."""
    normalized = job_title.strip().lower()
    return any(target in normalized for target in TARGET_TITLES)


# ── Step 2: B2B classification from company URL ───────────────────────────────

def classify_b2b(company_url: str) -> str:
    """
    Fetches the company URL and counts B2B vs B2C signals in the page text.
    Returns "true", "false", or "unknown" (if page unreachable or no signals found).
    """
    if not company_url or not company_url.startswith("http"):
        return "unknown"

    text = fetch_page_text(company_url)
    if not text:
        return "unknown"

    lowered = text.lower()
    b2b_score = sum(1 for s in B2B_SIGNALS if s in lowered)
    b2c_score = sum(1 for s in B2C_SIGNALS if s in lowered)

    if b2b_score == 0 and b2c_score == 0:
        return "unknown"
    if b2b_score >= b2c_score:
        return "true"
    return "false"


# ── Step 3: Qualification status ─────────────────────────────────────────────

def get_qualification_status(target_title: bool, b2b: str) -> str:
    """
    qualified     → right title AND b2b company
    wrong_title   → title doesn't match (regardless of b2b)
    not_b2b       → right title but company is B2C
    unknown       → right title but couldn't determine b2b status
    """
    if not target_title:
        return "wrong_title"
    if b2b == "true":
        return "qualified"
    if b2b == "false":
        return "not_b2b"
    return "unknown"


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    with open(INPUT_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Loaded {len(rows)} leads from {INPUT_FILE}\n")

    results = []
    for i, row in enumerate(rows):
        name = f"{row.get('firstname', '')} {row.get('lastname', '')}".strip()
        title = row.get("jobTitle", "")
        url = row.get("companyUrl", "").strip()

        print(f"[{i+1}/{len(rows)}] {name} — {title}")

        title_match = is_target_title(title)
        b2b = classify_b2b(url)
        status = get_qualification_status(title_match, b2b)

        print(f"         title={title_match} | b2b={b2b} | status={status}")

        results.append({
            "firstname": row.get("firstname", ""),
            "lastname": row.get("lastname", ""),
            "jobTitle": title,
            "companyName": row.get("companyName", ""),
            "companyUrl": url,
            "linkedinUrl": row.get("linkedinUrl", ""),
            "is_target_title": title_match,
            "is_b2b_company": b2b,
            "qualification_status": status,
        })

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    qualified = sum(1 for r in results if r["qualification_status"] == "qualified")
    print(f"\nExported {len(results)} rows to {OUTPUT_FILE}")
    print(f"Qualified: {qualified} | Wrong title: {sum(1 for r in results if r['qualification_status'] == 'wrong_title')} | Not B2B: {sum(1 for r in results if r['qualification_status'] == 'not_b2b')} | Unknown: {sum(1 for r in results if r['qualification_status'] == 'unknown')}")


if __name__ == "__main__":
    run()
