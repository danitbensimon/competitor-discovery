# extract.py — Downloads page content, scores confidence, and extracts companies.
# Only passes medium/high confidence pages to Claude for company extraction.

import re
import anthropic
from fetch import fetch_page_text

client = anthropic.Anthropic()

# Phrases that indicate a company is actively using the brand
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


def extract_companies(pages: list[dict], brand: str = "Deel") -> list[dict]:
    """
    For each page:
      1. Download full page content
      2. Score confidence based on signal phrases
      3. Skip low-confidence pages
      4. Use Claude to extract the company name and domain
    Returns deduplicated list of {name, domain, source_url, confidence}.
    """
    qualified_pages = []

    print(f"  Fetching content for {len(pages)} pages...")
    for i, page in enumerate(pages):
        print(f"    [{i+1}/{len(pages)}] {page['url'][:80]}", end=" ", flush=True)

        content = fetch_page_text(page["url"])

        # Fall back to snippet if page download failed
        text = content if content else f"{page['title']} {page['snippet']}"

        # Determine confidence: signal group takes priority over phrase matching
        url_lower = page["url"].lower()
        signal_group = page.get("signal_group", "")

        if any(seg in url_lower for seg in ("/case-study/", "/case_study/", "/customer-stor", "/customers/", "/clients/")):
            confidence = "high"
        elif signal_group in ("job_postings", "linkedin", "review_sites", "tech_stack"):
            # Trust the search query — if it matched, the page is relevant
            confidence = "medium"
        else:
            confidence = score_confidence(text, brand)

        print(f"→ {confidence}")

        if confidence in ("high", "medium"):
            qualified_pages.append({
                **page,
                "content": text,
                "confidence": confidence,
            })

    print(f"\n  {len(qualified_pages)} pages passed confidence filter. Extracting companies...")

    if not qualified_pages:
        return []

    companies = []
    seen_domains = set()

    # Process in batches of 5 pages per Claude call to stay efficient
    batch_size = 5
    for i in range(0, len(qualified_pages), batch_size):
        batch = qualified_pages[i:i + batch_size]
        extracted = extract_from_batch(batch, brand)
        for company in extracted:
            domain = company["domain"].lower()
            if domain not in seen_domains and brand.lower() not in domain:
                seen_domains.add(domain)
                companies.append(company)

    print(f"  Extracted {len(companies)} unique companies.")
    return companies


def extract_from_batch(pages: list[dict], brand: str) -> list[dict]:
    """Send a batch of pages to Claude and extract company names/domains."""
    blocks = []
    for p in pages:
        blocks.append(
            f"SOURCE: {p['url']}\n"
            f"SIGNAL: {p.get('signal_group', 'unknown')}\n"
            f"CONTENT:\n{p['content'][:2000]}\n"
        )

    combined = "\n---\n".join(blocks)

    prompt = f"""You are a research assistant identifying companies that use {brand}.

Below are web pages that mention {brand}. Each page has a SIGNAL type that tells you why it was found:
- own_site / blog_press / customer_signals: likely a case study or direct customer mention
- job_postings: a job ad — the hiring company is a {brand} user
- linkedin: a LinkedIn post or profile — the company or person mentioned uses {brand}
- review_sites: a review platform — extract the reviewing company if identifiable
- tech_stack: an integration or tech stack page — extract the company using {brand}

For each page, identify the company that is a {brand} customer or user.

Rules:
- Extract only real companies (not {brand} itself, not directories, not media outlets)
- For job postings: extract the company posting the job
- For LinkedIn: extract the company the person works at, or the company mentioned as using {brand}
- Use the source URL to help identify the company's domain when possible

For each company found, respond with one line in this exact format:
COMPANY: <name> | DOMAIN: <domain> | SOURCE: <url> | SIGNAL: <signal_group>

If no clear company can be identified from a page, skip it.

Pages:
{combined}
"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        print(f"  Warning: Claude API error during extraction: {e}")
        return []

    raw = message.content[0].text
    results = []

    for line in raw.splitlines():
        match = re.match(
            r"COMPANY:\s*(.+?)\s*\|\s*DOMAIN:\s*(.+?)\s*\|\s*SOURCE:\s*(.+?)\s*\|\s*SIGNAL:\s*(.+)",
            line,
        )
        if match:
            results.append({
                "name": match.group(1).strip(),
                "domain": match.group(2).strip().lower(),
                "source_url": match.group(3).strip(),
                "signal_group": match.group(4).strip().lower(),
            })

    return results
