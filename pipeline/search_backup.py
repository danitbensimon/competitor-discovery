# search.py — Searches the web using structured signal groups.
# For each query: paginates up to MAX_PER_QUERY results.
# All results are merged and deduplicated by URL.

import time
import requests
import config

SIGNAL_GROUPS = {
    "own_site": [
        'site:{domain} "case study"',
        'site:{domain} "customer"',
        'site:{domain} "success story"',
    ],
    "customer_signals": [
        '"using {brand}"',
        '"implemented {brand}"',
        '"switched to {brand}"',
        '"moved to {brand}"',
        '"powered by {brand}"',
        '"running payroll on {brand}"',
        '"company uses {brand}"',
        '"team uses {brand}"',
    ],
    "job_postings": [
        '"experience with {brand}"',
        '"familiar with {brand}"',
        '"manage {brand}"',
        '"administer {brand}"',
        '"responsible for {brand}"',
    ],
    "tech_stack": [
        '"integration with {brand}"',
        '"connected to {brand}"',
        '"{brand} integration"',
    ],
    "review_sites": [
        'site:g2.com "{brand}"',
        'site:capterra.com "{brand}"',
    ],
    "linkedin": [
        'site:linkedin.com "{brand}"',
        'site:linkedin.com "using {brand}"',
    ],
    "blog_press": [
        '"{brand} customer"',
        '"{brand} case study"',
        '"{brand} success story"',
    ],
}

RESULTS_PER_PAGE = 10
MAX_PER_QUERY = 200          # paginate up to this many results per query
SLEEP_BETWEEN_REQUESTS = 0.5  # seconds, to avoid rate limiting


def brand_from_domain(domain: str) -> str:
    """Extracts a brand name from a domain. e.g. 'deel.com' → 'Deel'"""
    return domain.split(".")[0].capitalize()


def search_customer_mentions(domain: str, brand: str = None) -> list[dict]:
    """
    Runs all signal group queries for the given brand.
    Each query paginates up to MAX_PER_QUERY results.
    Results are merged and deduplicated by URL across all queries.
    Returns a list of {url, title, snippet, query, signal_group} dicts.
    """
    if not brand:
        brand = brand_from_domain(domain)
    total_queries = sum(len(q) for q in SIGNAL_GROUPS.values())
    print(f"  Brand: {brand} | Signal groups: {len(SIGNAL_GROUPS)} | Queries: {total_queries} | Max per query: {MAX_PER_QUERY}")

    all_results = []
    seen_urls = set()

    for group_name, templates in SIGNAL_GROUPS.items():
        print(f"\n  [{group_name}]")
        for template in templates:
            query = template.replace("{brand}", brand).replace("{domain}", domain)
            query_results = _fetch_query(query, group_name, seen_urls)

            # For non-own_site groups, exclude URLs from the brand's own domain
            if group_name != "own_site":
                query_results = [r for r in query_results if domain not in r["url"]]

            all_results.extend(query_results)
            for r in query_results:
                seen_urls.add(r["url"])
            print(f"    {query} → {len(query_results)} new results")

    print(f"\n  Total unique URLs collected: {len(all_results)}")
    return all_results


def _fetch_query(query: str, group_name: str, seen_urls: set) -> list[dict]:
    """
    Fetches up to MAX_PER_QUERY results for a single query via pagination.
    Skips URLs already in seen_urls.
    Returns a list of new {url, title, snippet, query, signal_group} dicts.
    """
    results = []
    max_pages = MAX_PER_QUERY // RESULTS_PER_PAGE

    for page in range(max_pages):
        params = {
            "q": query,
            "num": RESULTS_PER_PAGE,
            "start": page * RESULTS_PER_PAGE,
            "api_key": config.SERPAPI_KEY,
            "engine": "google",
        }

        try:
            response = requests.get(
                "https://serpapi.com/search", params=params, timeout=15
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"      Warning: request failed on page {page}: {e}")
            break

        organic = response.json().get("organic_results", [])

        if not organic:
            break  # no more results for this query

        for r in organic:
            url = r.get("link", "")
            if url and url not in seen_urls:
                results.append({
                    "url": url,
                    "title": r.get("title", ""),
                    "snippet": r.get("snippet", ""),
                    "query": query,
                    "signal_group": group_name,
                })

        time.sleep(SLEEP_BETWEEN_REQUESTS)

    return results
