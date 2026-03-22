# search.py
import os
import requests

BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "").strip()


def brand_from_domain(domain: str) -> str:
    domain = domain.lower().strip()
    domain = domain.replace("https://", "").replace("http://", "")
    domain = domain.replace("www.", "")
    domain = domain.split("/")[0]
    if "." in domain:
        return domain.split(".")[0].capitalize()
    return domain.capitalize()


def _brave_search(query: str, num: int = 20, offset: int = 0) -> dict:
    if not BRAVE_API_KEY:
        raise ValueError("Missing BRAVE_API_KEY environment variable")
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": BRAVE_API_KEY,
    }
    params = {
        "q": query,
        "count": min(num, 20),
        "offset": offset,
    }
    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def _fetch_query(query: str, group_name: str, seen_urls: set, pages: int = 1) -> list[dict]:
    results = []
    for page in range(pages):
        offset = page * 20
        try:
            data = _brave_search(query, num=20, offset=offset)
            organic = data.get("web", {}).get("results", [])
            if not organic:
                break
            for item in organic:
                page_url = item.get("url")
                if not page_url or page_url in seen_urls:
                    continue
                seen_urls.add(page_url)
                results.append({
                    "title": item.get("title", ""),
                    "url": page_url,
                    "snippet": item.get("description", ""),
                    "group": group_name,
                })
        except Exception as e:
            print(f"Search error ({query}): {e}")
            break
    print(f'{query} → {len(results)} results')
    return results


def _test_pages(domain: str, brand: str) -> list[dict]:
    return [
        {"title": f"Acme uses {brand}", "url": "https://example.com/acme", "snippet": f"Acme uses {brand} for global hiring.", "group": "own_site"},
        {"title": f"Startup switched to {brand}", "url": "https://example.com/startup", "snippet": f"The company switched to {brand}.", "group": "customer_signals"},
        {"title": f"{brand} review on G2", "url": "https://example.com/g2", "snippet": f"A reviewer describes using {brand}.", "group": "review_sites"},
    ]


def _build_queries(domain: str, brand: str, tier: str) -> list[tuple[str, str]]:
    b = brand

    # GROUP 1: Customer signals — direct usage evidence
    customer_signals = [
        (f'"using {b}"', "customer_signals"),
        (f'"implemented {b}"', "customer_signals"),
        (f'"switched to {b}"', "customer_signals"),
        (f'"moved to {b}"', "customer_signals"),
        (f'"powered by {b}"', "customer_signals"),
        (f'"integrates {b}"', "customer_signals"),
        (f'"integrated {b}"', "customer_signals"),
        (f'"partnered with {b}"', "customer_signals"),
        (f'"company uses {b}"', "customer_signals"),
        (f'"we use {b}"', "customer_signals"),
        (f'"{b} partner"', "customer_signals"),
    ]

    # GROUP 2: Job postings — companies hiring people who know the tool
    job_postings = [
        (f'"experience with {b}"', "job_postings"),
        (f'"familiar with {b}"', "job_postings"),
        (f'"manage {b}"', "job_postings"),
        (f'"administer {b}"', "job_postings"),
    ]

    # GROUP 3: Tech stack / integrations — including tech intelligence databases
    tech_stack = [
        (f'site:enlyft.com "{b}"', "tech_stack"),
        (f'site:theirstack.com "{b}"', "tech_stack"),
        (f'site:zoominfo.com "{b}"', "tech_stack"),
        (f'site:builtwith.com "{b}"', "tech_stack"),
        (f'site:stackshare.io "{b}"', "tech_stack"),
        (f'"{b} integration"', "tech_stack"),
        (f'"integration with {b}"', "tech_stack"),
        (f'"{b} API" company', "tech_stack"),
        (f'"{b}" customers site:g2.com', "tech_stack"),
    ]

    # GROUP 4: Review sites
    review_sites = [
        (f'site:g2.com "{b}"', "review_sites"),
        (f'site:capterra.com "{b}"', "review_sites"),
        (f'site:trustpilot.com "{b}"', "review_sites"),
        (f'"{b} review" company', "review_sites"),
    ]

    # GROUP 5: LinkedIn
    linkedin = [
        (f'site:linkedin.com "using {b}"', "linkedin"),
        (f'site:linkedin.com "{b}" customers', "linkedin"),
    ]

    # GROUP 6: Blog / press / own site
    blog_press = [
        (f'site:{domain} customers', "own_site"),
        (f'site:{domain} "case study"', "own_site"),
        (f'site:{domain} "success story"', "own_site"),
        (f'"{b} customers"', "blog_press"),
        (f'"{b} case study"', "blog_press"),
        (f'"{b} success story"', "blog_press"),
        (f'"{b} customer"', "blog_press"),
    ]

    if tier == "lite":
        # Core queries from each group — ~22 queries total
        # customer_signals[:5] picks: using, implemented, switched, moved, powered_by, integrates
        return (
            customer_signals[:6] +   # using, implemented, switched, moved, powered_by, integrates
            job_postings[:2] +
            tech_stack[:5] +         # all 5 intelligence databases
            review_sites[:2] +
            linkedin[:1] +
            blog_press[:4]
        )
    if tier == "pro":
        return customer_signals + job_postings + tech_stack[:7] + review_sites + linkedin + blog_press
    # advanced: everything
    return customer_signals + job_postings + tech_stack + review_sites + linkedin + blog_press


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
        rows = _fetch_query(query, group_name, seen_urls, pages=1)
        all_results.extend(rows)

    print(f"\nTotal URLs collected: {len(all_results)}")
    return all_results
