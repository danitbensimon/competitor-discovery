# extract.py — Downloads page content, scores confidence, and extracts companies.
# Keeps page rank score and other evidence so scoring can use it later.

import re
import anthropic
from concurrent.futures import ThreadPoolExecutor, as_completed
from fetch import fetch_page_text

client = anthropic.Anthropic()


def _confidence_phrases(brand: str):
    b = brand.lower()
    high = [
        f"using {b}",
        f"implemented {b}",
        f"{b} customer",
        f"powered by {b}",
    ]
    medium = [
        f"switched to {b}",
        f"moved to {b}",
        f"running payroll on {b}",
        f"company uses {b}",
        f"team uses {b}",
        f"experience with {b}",
        f"integration with {b}",
        f"connected to {b}",
        f"familiar with {b}",
        f"manage {b}",
    ]
    return high, medium


def score_confidence(text: str, brand: str = "Deel") -> str:
    lowered = text.lower()
    high, medium = _confidence_phrases(brand)

    for phrase in high:
        if phrase in lowered:
            return "high"

    for phrase in medium:
        if phrase in lowered:
            return "medium"

    return "low"


def _fetch_one(page: dict, fetch_content: bool) -> dict:
    """Fetch a single page and return enriched dict with text + confidence."""
    if fetch_content:
        content = fetch_page_text(page["url"])
        text = content if content else f"{page.get('title', '')} {page.get('snippet', '')}"
    else:
        text = f"{page.get('title', '')} {page.get('snippet', '')}"
    return {**page, "_text": text}


def extract_companies(pages: list[dict], brand: str = "Deel", fetch_content: bool = True) -> list[dict]:
    """
    For each page:
      1. Download page content in parallel (or use snippet only when fetch_content=False)
      2. Score confidence based on signal phrases
      3. Use Claude to extract company name and domain
    Returns a list of company evidence rows.
    """

    qualified_pages = []

    print(f"  Parallel {'fetching' if fetch_content else 'snippet'} for {len(pages)} pages...")

    # Fetch all pages concurrently — stays within ~10s regardless of page count
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_fetch_one, page, fetch_content): page for page in pages}
        enriched = []
        for future in as_completed(futures):
            try:
                enriched.append(future.result())
            except Exception as e:
                print(f"  Fetch error: {e}")

    for page in enriched:
        text = page.pop("_text", "")
        url_lower = page["url"].lower()
        signal_group = page.get("signal_group", "") or page.get("group", "")

        if any(seg in url_lower for seg in ("/case-study/", "/case_study/", "/customer-stor", "/customers/", "/clients/")):
            confidence = "high"
        elif signal_group in ("own_site", "customer_signals"):
            confidence = "high"
        elif signal_group in ("job_postings", "linkedin", "review_sites", "tech_stack", "blog_press"):
            confidence = "medium"
        else:
            confidence = score_confidence(text, brand)

        if confidence in ("high", "medium", "low"):
            qualified_pages.append({
                **page,
                "content": text,
                "confidence": confidence,
            })

    print(f"\n  {len(qualified_pages)} pages passed confidence filter. Extracting companies...")

    if not qualified_pages:
        return []

    companies = []

    batch_size = 5
    for i in range(0, len(qualified_pages), batch_size):
        batch = qualified_pages[i:i + batch_size]
        extracted = extract_from_batch(batch, brand)
        companies.extend(extracted)

    print(f"  Extracted {len(companies)} company evidence rows.")
    return companies


def extract_from_batch(pages: list[dict], brand: str) -> list[dict]:
    """Send a batch of pages to Claude and extract company names/domains."""

    blocks = []
    for p in pages:
        blocks.append(
            f"SOURCE: {p['url']}\n"
            f"SIGNAL: {p.get('signal_group', 'unknown')}\n"
            f"RANK_SCORE: {p.get('rank_score', 0)}\n"
            f"CONFIDENCE: {p.get('confidence', 'unknown')}\n"
            f"CONTENT:\n{p['content'][:2000]}\n"
        )

    combined = "\n---\n".join(blocks)

    prompt = f"""You are a research assistant identifying companies that use {brand}.

Below are web pages that mention {brand}. Each page has:
- SOURCE
- SIGNAL
- RANK_SCORE
- CONFIDENCE

For each page, identify the company that is a {brand} customer or user.

Rules:
- Extract only real companies
- Do not extract {brand} itself
- Do not extract media sites, directories, or review platforms as the company
- For job postings: extract the company posting the job
- For LinkedIn: extract the company the person works at, or the company mentioned as using {brand}
- For review sites: extract the reviewing company if identifiable
- Use the source URL to help identify the company's domain when possible
- If no clear company can be identified from a page, skip it

Return one line per company in this exact format:
COMPANY: <name> | DOMAIN: <domain> | SOURCE: <url>

Pages:
{combined}
"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        print(f"  Warning: Claude API error during extraction: {e}")
        return []

    raw = message.content[0].text
    results = []

    source_map = {}
    for p in pages:
        source_map[p["url"]] = p

    for line in raw.splitlines():
        match = re.match(
            r"COMPANY:\s*(.+?)\s*\|\s*DOMAIN:\s*(.+?)\s*\|\s*SOURCE:\s*(.+)",
            line,
        )
        if match:
            company_name = match.group(1).strip()
            company_domain = match.group(2).strip().lower()
            source_url = match.group(3).strip()

            original_page = source_map.get(source_url, {})

            results.append({
                "name": company_name,
                "domain": company_domain,
                "company_name": company_name,
                "company_domain": company_domain,
                "source_url": source_url,
                "signal_group": original_page.get("signal_group", ""),
                "rank_score": original_page.get("rank_score", 0),
                "confidence": original_page.get("confidence", ""),
                "title": original_page.get("title", ""),
                "snippet": original_page.get("snippet", ""),
            })

    return results