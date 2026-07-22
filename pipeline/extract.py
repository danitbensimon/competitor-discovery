# extract.py â Downloads page content, scores confidence, and extracts companies.
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
    """Fetch a single page and return enriched dict with text + confidence.
    - probe_sublink pages: skip fetch â company name is already in title/snippet from URL slug
    - own_site / customer_signals: fetch full content
    - others: use snippet only
    """
    signal_group = page.get("signal_group", "") or page.get("group", "")
    # Probe sub-links already have a company name hint in title â no fetch needed
    if page.get("probe_sublink"):
        text = f"{page.get('title', '')} {page.get('snippet', '')}"
    elif fetch_content and signal_group in ("own_site", "customer_signals"):
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

    # Fetch all pages concurrently â stays within ~8s regardless of page count
    with ThreadPoolExecutor(max_workers=6) as executor:
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

        if page.get("logo_wall"):
            confidence = "high"
        elif any(seg in url_lower for seg in ("/case-study/", "/case-studies/", "/case_study/", "/customer-stor", "/customers/", "/clients/")):
            confidence = "high"
        elif signal_group in ("own_site", "customer_signals"):
            confidence = "high"
        elif signal_group == "partners":
            confidence = "low"
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

    qualified_pages = qualified_pages[:70]   # was 40 — logo-wall rows are 1 page per company

    print(f"\n  {len(qualified_pages)} pages passed confidence filter. Extracting companies...")

    if not qualified_pages:
        return []

    import re as _re
    import threading
    companies = []
    seen_sources: dict = {}
    results_lock = threading.Lock()

    batch_size = 5
    batches = [qualified_pages[i:i + batch_size] for i in range(0, len(qualified_pages), batch_size)]

    # Run up to 3 extraction batches in parallel to cut Claude latency
    with ThreadPoolExecutor(max_workers=3) as ex:
        future_to_batch = {ex.submit(extract_from_batch, batch, brand): batch for batch in batches}
        for future in as_completed(future_to_batch):
            try:
                rows = future.result()
            except Exception as e:
                print(f"  Extraction batch error: {e}")
                continue
            with results_lock:
                for row in rows:
                    src = row.get("source_url", "")
                    src = _re.sub(r'(\.html){2,}', '.html', src)
                    row["source_url"] = src
                    # Customer index pages (/customers, /case-studies, /clients) can yield
                    # many real companies â allow up to 30 per source instead of 5
                    is_index = any(p in src for p in ['/customers', '/case-studies', '/clients', '/success-stories'])
                    per_source_limit = 30 if is_index else 5
                    if seen_sources.get(src, 0) < per_source_limit:
                        companies.append(row)
                        seen_sources[src] = seen_sources.get(src, 0) + 1

    print(f"  Extracted {len(companies)} company evidence rows.")
    return companies[:80]   # was 50 — leave headroom; ICP + source validation trim later


def extract_from_batch(pages: list[dict], brand: str) -> list[dict]:
    """Send a batch of pages to Claude and extract company names/domains."""

    blocks = []
    for p in pages:
        signal = p.get('signal_group') or p.get('group', 'unknown')
        blocks.append(
            f"SOURCE: {p['url']}\n"
            f"SIGNAL: {signal}\n"
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

Then judge the RELATIONSHIP between that company and {brand}. This matters more
than the company name — a partner listed on a website is not a customer, and
labelling one as the other makes the whole list untrustworthy.
- customer  — evidence the company USES {brand}: a case study, "trusted by", a
  customer story, a review they wrote, a job ad asking for {brand} experience
- partner   — reseller, integration partner, channel partner, technology partner,
  distributor, logistics or fulfilment partner, "works with", "available on"
- investor  — investor, backer, accelerator, or the company funded {brand}
- unclear   — the page shows the logo or name but gives no basis to tell which

Judge from the page's own words, and commit to a judgement. "unclear" is for
pages that genuinely say nothing about the relationship, not for ordinary
uncertainty. If a company's logo sits in a band the site itself labels "Trusted
by", "Our customers", "Powering", "Used by" or "Join N teams", that IS the site
claiming them as a customer — answer customer. A case study, success story or
customer quote is a customer. A named reviewer is a customer.

Answer partner when the band or page is labelled partners, integrations,
resellers, "works with" or "available on", or when the named entity is itself a
software product rather than a company that would buy one. Answer investor for
investors, backers and accelerators. Answer unclear only when a name appears
with no surrounding label at all.

A logo band's label applies to every logo in that band. If the page shows more
than one band, use the label nearest the company, and where the context lists
several labels, pick the one that fits that specific company.

Return one line per company in this exact format:
COMPANY: <name> | DOMAIN: <domain> | RELATIONSHIP: <customer|partner|investor|unclear> | SOURCE: <url>

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
    input_urls = list(source_map.keys())

    def _snap_source(model_url: str):
        """
        Never trust the URL the model echoes back — it may be hallucinated or
        mangled (extra path segments, .pdf suffixes, etc.). Snap it to one of the
        REAL input page URLs we actually fetched. Returns None if the model's URL
        cannot be matched to any input page (so the row is dropped, not invented).
        """
        if model_url in source_map:
            return model_url
        from urllib.parse import urlparse
        m = urlparse(model_url)
        m_host = m.netloc.replace("www.", "")
        best, best_len = None, -1
        for u in input_urls:
            pu = urlparse(u)
            if pu.netloc.replace("www.", "") != m_host:
                continue
            # same host → choose the input URL sharing the longest path prefix
            shared = 0
            for a, b in zip(m.path, pu.path):
                if a != b:
                    break
                shared += 1
            if shared > best_len:
                best, best_len = u, shared
        return best  # None if no input URL shares the host

    for line in raw.splitlines():
        match = re.match(
            r"COMPANY:\s*(.+?)\s*\|\s*DOMAIN:\s*(.+?)"
            r"(?:\s*\|\s*RELATIONSHIP:\s*(\w+))?"
            r"\s*\|\s*SOURCE:\s*(.+)",
            line,
        )
        if match:
            company_name = match.group(1).strip()
            company_domain = match.group(2).strip().lower()
            relationship = (match.group(3) or "unclear").strip().lower()
            if relationship not in ("customer", "partner", "investor", "unclear"):
                relationship = "unclear"
            model_source = match.group(4).strip()

            source_url = _snap_source(model_source)
            if not source_url:
                # Model cited a URL we never fetched → unverifiable, skip it.
                continue

            original_page = source_map.get(source_url, {})

            results.append({
                "name": company_name,
                "domain": company_domain,
                "company_name": company_name,
                "company_domain": company_domain,
                "relationship": relationship,
                "source_url": source_url,
                "signal_group": original_page.get("signal_group") or original_page.get("group", ""),
                "rank_score": original_page.get("rank_score", 0),
                "confidence": original_page.get("confidence", ""),
                "title": original_page.get("title", ""),
                "snippet": original_page.get("snippet", ""),
            })

    return results
