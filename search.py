# search.py
import os
import requests


SERPAPI_KEY = os.getenv("SERPAPI_KEY", "").strip()


def brand_from_domain(domain: str) -> str:
    domain = domain.lower().strip()
    domain = domain.replace("https://", "").replace("http://", "")
    domain = domain.replace("www.", "")
    domain = domain.split("/")[0]

    if "." in domain:
        return domain.split(".")[0].capitalize()

    return domain.capitalize()


def _serpapi_search(query: str, num: int = 10) -> dict:
    if not SERPAPI_KEY:
        raise ValueError("Missing SERPAPI_KEY environment variable")

    url = "https://serpapi.com/search"
    params = {
        "engine": "google",
        "q": query,
        "num": num,
        "api_key": SERPAPI_KEY,
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def _fetch_query(query: str, group_name: str, seen_urls: set) -> list[dict]:
    results = []

    try:
        data = _serpapi_search(query, num=10)
        organic = data.get("organic_results", [])

        for item in organic:
            page_url = item.get("link")
            if not page_url or page_url in seen_urls:
                continue

            seen_urls.add(page_url)

            results.append(
                {
                    "title": item.get("title", ""),
                    "url": page_url,
                    "snippet": item.get("snippet", ""),
                    "group": group_name,
                }
            )

        print(f'{query} → {len(results)} results')

    except Exception as e:
        print(f"Search error: {e}")
        print(f'{query} → 0 results')

    return results


def _test_pages(domain: str, brand: str) -> list[dict]:
    return [
        {
            "title": f"Acme uses {brand} for global hiring",
            "url": "https://example.com/acme-case-study",
            "snippet": f"Acme explains how it uses {brand} to manage international hiring and payroll.",
            "group": "own_site",
        },
        {
            "title": f"Startup switched to {brand}",
            "url": "https://example.com/startup-switched",
            "snippet": f"The company switched to {brand} and improved contractor onboarding.",
            "group": "customer_signals",
        },
        {
            "title": f"{brand} customer review on G2",
            "url": "https://example.com/g2-review",
            "snippet": f"A reviewer describes using {brand} across multiple regions.",
            "group": "review_sites",
        },
    ]


def _build_queries(domain: str, brand: str, tier: str) -> list[tuple[str, str]]:
    lite_queries = [
        ('site:' + domain + ' "case study"', "own_site"),
        (f'"using {brand}"', "customer_signals"),
        (f'"{brand} customer"', "blog_press"),
        ('site:g2.com "' + brand + '"', "review_sites"),
    ]

    pro_extra = [
        ('site:' + domain + ' "customer"', "own_site"),
        (f'"implemented {brand}"', "customer_signals"),
        (f'"switched to {brand}"', "customer_signals"),
        ('site:capterra.com "' + brand + '"', "review_sites"),
    ]

    advanced_extra = [
        ('site:' + domain + ' "success story"', "own_site"),
        (f'"moved to {brand}"', "customer_signals"),
        (f'"powered by {brand}"', "customer_signals"),
        (f'"{brand} case study"', "blog_press"),
        (f'"{brand} success story"', "blog_press"),
    ]

    if tier == "lite":
        return lite_queries
    if tier == "pro":
        return lite_queries + pro_extra
    return lite_queries + pro_extra + advanced_extra


def search_customer_mentions(domain: str, brand: str = None, mode: str = "live", tier: str = "lite") -> list[dict]:
    brand = brand or brand_from_domain(domain)

    if mode == "test":
        pages = _test_pages(domain, brand)
        print(f"[test mode] Returning {len(pages)} fake pages")
        return pages

    queries = _build_queries(domain, brand, tier)
    seen_urls = set()
    all_results = []

    print(f"Brand: {brand} | Queries: {len(queries)} | Tier: {tier}")

    current_group = None
    for query, group_name in queries:
        if group_name != current_group:
            current_group = group_name
            print(f"\n[{group_name}]")

        rows = _fetch_query(query, group_name, seen_urls)
        all_results.extend(rows)

    print(f"\nTotal URLs collected: {len(all_results)}")
    return all_results