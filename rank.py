from urllib.parse import urlparse

TIER_LIMITS = {
    "lite": 6,
    "pro": 200,
    "advanced": 400,
}

SIGNAL_WEIGHTS = {
    "own_site": 5,
    "customer_signals": 4,
    "blog_press": 4,
    "review_sites": 3,
    "tech_stack": 3,
    "job_postings": 2,
    "linkedin": 1,
}

HIGH_INTENT_PHRASES = [
    "using",
    "implemented",
    "switched to",
    "moved to",
    "powered by",
    "customer",
    "case study",
    "success story",
]

MEDIUM_INTENT_PHRASES = [
    "experience with",
    "familiar with",
    "integration",
    "connected to",
    "manage",
    "administer",
]


def score_result(page: dict, brand: str) -> int:
    score = 0

    signal_group = page.get("signal_group", "") or page.get("group", "")
    score += SIGNAL_WEIGHTS.get(signal_group, 0)

    url = page.get("url", "").lower()
    title = page.get("title", "").lower()
    snippet = page.get("snippet", "").lower()
    combined = f"{title} {snippet}"

    if any(x in url for x in ["/case-study", "/customers", "/customer", "/success", "/clients"]):
        score += 4

    if brand.lower() in combined:
        score += 2

    for phrase in HIGH_INTENT_PHRASES:
        if phrase in combined:
            score += 3

    for phrase in MEDIUM_INTENT_PHRASES:
        if phrase in combined:
            score += 1

    domain = urlparse(url).netloc
    if "linkedin.com" in domain:
        score -= 1

    return score


def rank_candidates(pages: list[dict], brand: str, tier: str = "lite") -> list[dict]:
    ranked_pages = []

    for page in pages:
        page_copy = dict(page)
        page_copy["rank_score"] = score_result(page_copy, brand)
        ranked_pages.append(page_copy)

    ranked_pages = sorted(ranked_pages, key=lambda x: x["rank_score"], reverse=True)
    limit = TIER_LIMITS.get(tier, 25)
    shortlisted = ranked_pages[:limit]

    print(f"  Shortlisted {len(shortlisted)} pages out of {len(ranked_pages)}")
    return shortlisted