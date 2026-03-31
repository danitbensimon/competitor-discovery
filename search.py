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
        (f'site:{domain} blog', "own_site"),
        (f'site:{domain} testimonial', "own_site"),
        (f'site:{domain} "customer story"', "own_site"),
        (f'"{b} customers"', "blog_press"),
        (f'"{b} case study"', "blog_press"),
        (f'"{b} success story"', "blog_press"),
        (f'"{b} customer"', "blog_press"),
        (f'"{b} review" "company"', "blog_press"),
        (f'site:reddit.com "{b}"', "blog_press"),
        (f'"{b}" "we switched" OR "we moved" OR "we chose"', "blog_press"),
    ]

    if tier == "lite":
        return [
            customer_signals[0],   # "using {b}"
            blog_press[0],         # site:{domain} customers
            blog_press[1],         # site:{domain} "case study"
            blog_press[6],         # "{b} customers"
            blog_press[7],         # "{b} case study"
            blog_press[9],         # "{b} customer"
            tech_stack[0],         # site:enlyft.com
            tech_stack[1],         # site:theirstack.com
            review_sites[0],       # site:g2.com
            review_sites[1],       # site:capterra.com
        ]
    if tier == "pro":
        return customer_signals + job_postings + tech_stack[:7] + review_sites + linkedin + blog_press
    # advanced: everything
    return customer_signals + job_postings + tech_stack + review_sites + linkedin + blog_press


def _probe_customer_index_pages(domain: str, brand: str) -> list[dict]:
    """
    Directly probe well-known customer/case-study listing paths on the competitor's site.
    Adds the index page AND follows all case study sub-links found on it.
    """
    import requests as _req
    import re as _re_probe
    try:
        from bs4 import BeautifulSoup as _BS
        _has_bs4 = True
    except ImportError:
        _has_bs4 = False

    candidate_paths = [
        "/customers", "/case-studies", "/clients",
        "/success-stories", "/our-customers", "/customer-stories",
        "/testimonials", "/references",
    ]
    # URL segments that indicate an individual customer/case-study page
    case_study_segs = [
        "/case-studies/", "/case-study/", "/case_study/",
        "/customers/", "/clients/", "/success-stories/",
        "/customer-stories/", "/our-customers/",
    ]
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    found = []
    seen_urls = set()

    for path in candidate_paths:
        url = f"https://{domain}{path}"
        try:
            resp = _req.get(url, headers=headers, timeout=5, allow_redirects=True)
            if resp.status_code != 200 or domain not in resp.url or len(resp.text) < 1000:
                continue

            # Add the index page itself
            if resp.url not in seen_urls:
                found.append({
                    "url": resp.url,
                    "title": f"{brand} customers",
                    "snippet": f"Customer listing page for {brand} — may contain multiple customer names.",
                    "group": "own_site",
                    "signal_group": "own_site",
                })
                seen_urls.add(resp.url)
                print(f"  [probe] found customer index: {resp.url}")

            # Follow individual case study links from this index page
            if _has_bs4:
                soup = _BS(resp.text, "html.parser")
                hrefs = [a.get("href", "") for a in soup.find_all("a", href=True)]
            else:
                hrefs = _re_probe.findall(r'href=["\']([^"\']+)["\']', resp.text)

            for href in hrefs:
                # Normalise to absolute URL
                if href.startswith("/"):
                    href = f"https://{domain}{href}"
                elif not href.startswith("http"):
                    continue
                # Only keep links on the same domain that look like individual case pages
                if domain not in href:
                    continue
                if "#" in href or "?" in href:
                    href = href.split("#")[0].split("?")[0]
                if href in seen_urls:
                    continue
                if any(seg in href for seg in case_study_segs):
                    found.append({
                        "url": href,
                        "title": f"{brand} case study",
                        "snippet": f"Individual case study page for a {brand} customer.",
                        "group": "own_site",
                        "signal_group": "own_site",
                    })
                    seen_urls.add(href)

        except Exception:
            pass

    print(f"  [probe] total pages found: {len(found)}")
    return found


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

    # Run all search queries IN PARALLEL instead of one by one
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed
    lock = threading.Lock()

    def fetch_query_safe(query_group):
        query, group_name = query_group
        return _fetch_query(query, group_name, set(), pages=1)

    # Probe customer index pages directly (runs in parallel with Brave queries)
    with ThreadPoolExecutor(max_workers=6) as executor:
        probe_future = executor.submit(_probe_customer_index_pages, domain, brand)
        query_futures = {executor.submit(fetch_query_safe, qg): qg for qg in queries}

        # Collect Brave results
        for future in as_completed(query_futures):
            try:
                rows = future.result()
                with lock:
                    for row in rows:
                        if row["url"] not in seen_urls:
                            seen_urls.add(row["url"])
                            all_results.append(row)
            except Exception as e:
                print(f"Search error: {e}")

        # Prepend probed index pages so they get processed first (highest priority)
        try:
            probe_pages = probe_future.result()
            with lock:
                for row in probe_pages:
                    if row["url"] not in seen_urls:
                        seen_urls.add(row["url"])
                        all_results.insert(0, row)  # prepend = high priority
        except Exception as e:
            print(f"Probe error: {e}")

    print(f"\nTotal URLs collected: {len(all_results)}")
    return all_results
