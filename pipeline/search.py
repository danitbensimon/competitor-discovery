# search.py
import os
import re
import html as html_lib
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
    print(f'{query} â {len(results)} results')
    return results


def _test_pages(domain: str, brand: str) -> list[dict]:
    return [
        {"title": f"Acme uses {brand}", "url": "https://example.com/acme", "snippet": f"Acme uses {brand} for global hiring.", "group": "own_site"},
        {"title": f"Startup switched to {brand}", "url": "https://example.com/startup", "snippet": f"The company switched to {brand}.", "group": "customer_signals"},
        {"title": f"{brand} review on G2", "url": "https://example.com/g2", "snippet": f"A reviewer describes using {brand}.", "group": "review_sites"},
    ]


def _build_queries(domain: str, brand: str, tier: str) -> list[tuple[str, str]]:
    b = brand

    # GROUP 1: Customer signals â direct usage evidence
    customer_signals = [
        (f'"using {b}"', "customer_signals"),
        (f'"implemented {b}"', "customer_signals"),
        (f'"switched to {b}"', "customer_signals"),
        (f'"moved to {b}"', "customer_signals"),
        (f'"powered by {b}"', "customer_signals"),
        (f'"integrates {b}"', "customer_signals"),
        (f'"integrated {b}"', "customer_signals"),
        # Partners are NOT customers — kept in their own group so they never
        # inherit customer-level confidence in extract.py.
        (f'"partnered with {b}"', "partners"),
        (f'"company uses {b}"', "customer_signals"),
        (f'"we use {b}"', "customer_signals"),
    ]

    # GROUP 2: Job postings â companies hiring people who know the tool
    job_postings = [
        (f'"experience with {b}"', "job_postings"),
        (f'"familiar with {b}"', "job_postings"),
        (f'"manage {b}"', "job_postings"),
        (f'"administer {b}"', "job_postings"),
    ]

    # GROUP 3: Tech stack / integrations â including tech intelligence databases
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


def _slug_to_company_hint(slug: str) -> str:
    """Extract a likely company name from a URL slug like 'the-beard-club-saves-40-pct'."""
    STOP = {'saves', 'saved', 'increases', 'increased', 'reduces', 'reduced',
            'slashes', 'cuts', 'grows', 'achieves', 'how', 'why', 'with',
            'using', 'and', 'for', 'of', 'a', 'to', 'in', 'on', 'at',
            'case', 'study', 'customer', 'success', 'story', 'boost', 'boosted'}
    words = slug.replace('-', ' ').replace('_', ' ').split()
    out = []
    for w in words[:6]:
        if w.lower() in STOP and out:
            break
        if not w.isdigit():
            out.append(w.capitalize())
    return ' '.join(out) if out else slug.replace('-', ' ').title()


def _probe_customer_index_pages(domain: str, brand: str) -> list[dict]:
    """
    Directly probe well-known customer/case-study listing paths on the competitor's site.
    Paths are fetched IN PARALLEL for speed. Adds the index page AND follows sub-links.
    Sub-links get a company name hint from the URL slug so full-page fetch can be skipped.
    """
    import requests as _req
    import re as _re_probe
    from concurrent.futures import ThreadPoolExecutor as _TPE, as_completed as _ac
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

    def _fetch_path(path):
        url = f"https://{domain}{path}"
        try:
            resp = _req.get(url, headers=headers, timeout=4, allow_redirects=True)
            if resp.status_code == 200 and domain in resp.url and len(resp.text) > 1000:
                return resp
        except Exception:
            pass
        return None

    found = []
    seen_urls = set()

    # Fetch all candidate paths IN PARALLEL
    with _TPE(max_workers=8) as tpe:
        future_to_path = {tpe.submit(_fetch_path, p): p for p in candidate_paths}
        for future in _ac(future_to_path):
            resp = future.result()
            if resp is None:
                continue

            if resp.url not in seen_urls:
                found.append({
                    "url": resp.url,
                    "title": f"{brand} customers",
                    "snippet": f"Customer listing page for {brand} â may contain multiple customer names.",
                    "group": "own_site",
                    "signal_group": "own_site",
                    "probe_index": True,
                })
                seen_urls.add(resp.url)
                print(f"  [probe] found index: {resp.url}")

            # Follow sub-links (cap at 15 to avoid overwhelming extraction)
            if _has_bs4:
                hrefs = [a.get("href", "") for a in _BS(resp.text, "html.parser").find_all("a", href=True)]
            else:
                hrefs = _re_probe.findall(r'href=["\']([^"\']+)["\']', resp.text)

            sub_count = 0
            for href in hrefs:
                if sub_count >= 40:   # was 15 — capped niche tools (e.g. Swimm) at ~5 results
                    break
                if href.startswith("/"):
                    href = f"https://{domain}{href}"
                elif not href.startswith("http"):
                    continue
                if domain not in href:
                    continue
                href = href.split("#")[0].split("?")[0]
                if href in seen_urls:
                    continue
                if any(seg in href for seg in case_study_segs):
                    slug = href.rstrip("/").split("/")[-1]
                    name_hint = _slug_to_company_hint(slug)
                    found.append({
                        "url": href,
                        "title": name_hint,
                        "snippet": f"{brand} customer: {name_hint}",
                        "group": "own_site",
                        "signal_group": "own_site",
                        "probe_sublink": True,   # skip full-page fetch in extract.py
                    })
                    seen_urls.add(href)
                    sub_count += 1

    print(f"  [probe] total: {len(found)} pages")
    return found


# ── Logo wall harvesting ──────────────────────────────────────────────────────
# Most B2B sites put their customer logos front and centre on the homepage and
# nowhere else. Those logos are usually machine-readable without any search API:
# an <img alt>, a logo filename, an inline <svg><title>, or a JS carousel array.
# This is the highest-yield, lowest-cost source we have, so it runs first.

# Words that appear in logo filenames/alt text but are not part of a company name
_LOGO_NOISE = re.compile(
    r"\b(logo|logos|icon|img|image|images|brand|brands|client|clients|customer|"
    r"customers|partner|partners|grey|gray|colou?r|white|black|dark|light|new|"
    r"final|small|large|full|wide|mono|transparent|v\d+|\d{2,4}x\d{2,4})\b",
    re.I,
)
# alt/src/class values that mark an element as part of a logo band
_LOGO_HINT = re.compile(r"logo|client|customer|partner|brand|trusted", re.I)
# Generic labels that mean "this one image contains ALL the logos" → needs vision
_LOGO_STRIP = re.compile(r"^(partner|client|customer|brand|company)?\s*logos?$", re.I)


def _clean_logo_name(raw: str) -> str:
    """Turn 'Giesecke-logo.webp' or 'sony_logo_grey' into 'Giesecke' / 'Sony'."""
    s = re.sub(r"\.(svg|png|webp|jpe?g|gif|avif)$", "", raw.strip(), flags=re.I)
    s = re.sub(r"[-_+]+", " ", s)
    s = _LOGO_NOISE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip(" -_|·,")
    return s


def _plausible_company(name: str, brand: str) -> bool:
    if not name or len(name) < 2 or len(name) > 40:
        return False
    if not re.search(r"[A-Za-z]{2}", name):
        return False
    # The site's own wordmark files (Sensos-Logo-Negative.svg) look exactly like
    # a logo-wall entry — reject anything containing the brand, not just an
    # exact match.
    if brand.lower() in name.lower():
        return False
    # Reject filename leftovers like 'image 117' or 'Group 1000003401'
    if re.fullmatch(r"(image|group|frame|rectangle|asset|vector|mask)\s*\d*", name, re.I):
        return False
    return True


# Wording that labels a logo band. Which side of this line a company falls on
# is the whole customer-vs-partner question, so we look for it explicitly.
_BAND_LANG = re.compile(
    r"trusted by|our customers|customers|our clients|clients|used by|powering|"
    r"loved by|join \d|case stud|success stor|"
    r"partners?|integrat|resellers?|works with|available on|"
    r"backed by|investors?|as seen in|featured in|awards?",
    re.I,
)


def _nearest_heading(html: str, pos: int) -> str:
    """
    The label above a logo band — 'Trusted by...' (customers) vs 'Our integration
    partners' (partners). Searches BOTH directions, because a JS-built carousel
    lives in a <script> that can sit far from the band it renders into, and
    accepts styled <p>/<div> labels, not just <h1>-<h6>: plenty of sites set
    their band title as a 36px paragraph.
    """
    start = max(0, pos - 6000)
    window = html[start:pos + 6000]
    best, best_dist = "", 10 ** 9
    fallback, fb_dist = "", 10 ** 9

    for m in re.finditer(r"<(h[1-6]|p|div|span)[^>]*>([^<]{8,140})</\1>", window, re.I):
        text = re.sub(r"\s+", " ", html_lib.unescape(m.group(2))).strip()
        if not text:
            continue
        dist = abs((start + m.start()) - pos)
        if _BAND_LANG.search(text):
            if dist < best_dist:
                best, best_dist = text, dist
        elif m.group(1).lower().startswith("h") and dist < fb_dist:
            fallback, fb_dist = text, dist

    return (best or fallback)[:120]


def _page_band_labels(html: str) -> str:
    """
    Every logo-band label on the page, e.g. "Trusted by the World's Leading Supply
    Chains" or "Our integration partners". Used when a band has no label near it
    in the markup — a JS carousel can render nowhere near the copy that titles
    it. Better to hand Claude the page's own wording than to assume "customer".
    """
    labels, seen = [], set()
    for m in re.finditer(r"<(h[1-6]|p|div|span)[^>]*>([^<]{8,140})</\1>", html, re.I):
        text = re.sub(r"\s+", " ", html_lib.unescape(m.group(2))).strip()
        if _BAND_LANG.search(text) and text.lower() not in seen:
            seen.add(text.lower())
            labels.append(text)
        if len(labels) >= 4:
            break
    return " / ".join(labels)


def _harvest_logo_names(html: str, brand: str) -> tuple[list[tuple[str, str]], list[str]]:
    """
    Pull company names out of a page's logo band(s).
    Returns (names_with_context, strip_image_urls) where strip images are single
    flattened graphics containing many logos — those need vision, not regex.
    """
    found: dict[str, str] = {}   # lowercased name → (name, heading context)
    names: list[tuple[str, str]] = []
    strips: list[str] = []

    def _add(name: str, pos: int):
        name = _clean_logo_name(html_lib.unescape(name))
        if not _plausible_company(name, brand):
            return
        key = name.lower()
        if key in found:
            return
        found[key] = name
        names.append((name, _nearest_heading(html, pos)))

    # 1. JS-built carousels: `const logos = [{name: 'Bayer', svg: ...}, ...]`
    for script in re.finditer(r"<script[^>]*>(.*?)</script>", html, re.S | re.I):
        body = script.group(1)
        if "logo" not in body.lower():
            continue
        # A carousel script often sits far from the band it renders into, so the
        # nearest heading to the SCRIPT is meaningless. Follow the selector the
        # script targets and read the heading next to that container instead.
        anchor_pos = script.start()
        sel = re.search(r"querySelector(?:All)?\(\s*['\"]([.#][\w-]+)", body)
        if sel:
            token = sel.group(1)[1:]
            hit = re.search(rf"(?:class|id)=[\"'][^\"']*\b{re.escape(token)}\b", html)
            if hit:
                anchor_pos = hit.start()
        for m in re.finditer(r"\b(?:name|title|alt|label)\s*:\s*['\"]([^'\"]{2,40})['\"]", body):
            _add(m.group(1), anchor_pos)

    # 2. <img> tags inside logo bands — prefer alt text, fall back to the filename
    for m in re.finditer(r"<img[^>]+>", html, re.I):
        tag = m.group(0)
        alt = (re.search(r"\balt=[\"']([^\"']*)[\"']", tag, re.I) or [None, ""])[1]
        src = (re.search(r"\bsrc=[\"']([^\"']*)[\"']", tag, re.I) or [None, ""])[1]
        cls = (re.search(r"\bclass=[\"']([^\"']*)[\"']", tag, re.I) or [None, ""])[1]
        if not _LOGO_HINT.search(f"{alt} {src} {cls}"):
            continue
        if alt and _LOGO_STRIP.match(alt.strip()):
            # "Partner Logos" = one image holding every logo → hand to vision
            if src.startswith("http"):
                strips.append(src)
            continue
        _add(alt or src.split("/")[-1], m.start())

    # 3. Inline SVG logos carry their name in <title>
    for m in re.finditer(r"<svg[^>]*>.{0,400}?<title[^>]*>(.*?)</title>", html, re.S | re.I):
        _add(re.sub(r"<[^>]+>", "", m.group(1)), m.start())

    return names, strips[:3]


def _read_logo_strip(image_urls: list[str], brand: str) -> list[str]:
    """Ask Claude vision to read company names off a flattened logo strip."""
    if not image_urls:
        return []
    import base64
    import anthropic

    headers = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
               "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")}
    blocks = []
    for url in image_urls:
        ext = url.rsplit(".", 1)[-1].lower().split("?")[0]
        media = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png",
                 "gif": "gif", "webp": "webp"}.get(ext)
        if not media:
            continue
        try:
            r = requests.get(url, headers=headers, timeout=8)
            if r.status_code != 200 or len(r.content) > 4_000_000:
                continue
            blocks.append({
                "type": "image",
                "source": {"type": "base64", "media_type": f"image/{media}",
                           "data": base64.b64encode(r.content).decode()},
            })
        except Exception as e:
            print(f"  [logo-vision] fetch failed {url}: {e}")

    if not blocks:
        return []

    prompt = (
        f"These images are logo bands from {brand}'s website. "
        "List the company names you can read, one per line, nothing else. "
        "Skip any logo that is a wordmark for the website's own brand. "
        "If you cannot read a logo confidently, leave it out."
    )
    try:
        msg = anthropic.Anthropic().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": blocks + [{"type": "text", "text": prompt}]}],
        )
        lines = [l.strip(" -•*\t") for l in msg.content[0].text.splitlines()]
        out = [l for l in lines if _plausible_company(l, brand)]
        print(f"  [logo-vision] read {len(out)} names from {len(blocks)} image(s)")
        return out
    except Exception as e:
        print(f"  [logo-vision] error: {e}")
        return []


def _probe_logo_wall(domain: str, brand: str) -> list[dict]:
    """
    Harvest the customer logo wall from the homepage (and /customers if present).
    Each company becomes its own row carrying the band's heading as context, so
    extract.py can tell 'Trusted by' (customer) from 'Our partners' (partner).
    """
    headers = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
               "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")}
    rows, seen = [], set()

    for path in ("/", "/customers", "/case-studies"):
        page_url = f"https://{domain}{path}"
        try:
            resp = requests.get(page_url, headers=headers, timeout=8, allow_redirects=True)
            if resp.status_code != 200 or len(resp.text) < 1000:
                continue
        except Exception:
            continue

        names, strips = _harvest_logo_names(resp.text, brand)
        page_labels = _page_band_labels(resp.text)
        for name in _read_logo_strip(strips, brand):
            names.append((name, ""))

        for name, heading in names:
            # No label beside this band → fall back to the page's own band wording
            heading = heading or page_labels
            if name.lower() in seen:
                continue
            seen.add(name.lower())
            # Every row needs a UNIQUE url: the pipeline de-dupes on url, and all
            # of these come off one page. The anchor is ignored by every fetcher,
            # so the link still resolves to the real page it was found on.
            anchor = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
            rows.append({
                "url": f"{resp.url.split('#')[0]}#logo-{anchor}",
                "title": name,
                "snippet": (f"{name} appears in a logo band on {brand}'s site"
                            + (f", under: \"{heading}\"" if heading else "")),
                "group": "own_site",
                "signal_group": "own_site",
                "logo_wall": True,       # name already known — skip page fetch
                "probe_sublink": True,
                "band_heading": heading,
            })
        if path == "/" and len(rows) >= 12:
            break   # homepage wall was rich enough

    print(f"  [logo-wall] {len(rows)} companies harvested from logo bands")
    return rows


def _probe_sitemap(domain: str, brand: str) -> list[dict]:
    """
    Discover REAL customer / case-study pages from the competitor's XML sitemap.
    Sitemaps are plain XML (no JavaScript), so this catches stories that are
    rendered client-side on listing pages — invisible to a normal HTML fetch
    (which is why niche tools like Swimm under-returned). Every URL here is a
    live, publisher-confirmed page, so results pass source validation instead
    of being dropped as 404s.
    """
    import requests as _req
    import re as _re

    headers = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
               "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")}
    # URL path segments that indicate a customer / case-study page
    segs = ("/case-studies/", "/case-study/", "/case_study/", "/customers/",
            "/customer-stories/", "/success-stories/", "/clients/")
    # sub-sitemaps worth opening (matched against the sitemap filename)
    want = ("case-study", "case_study", "casestud", "customer", "success", "client", "story", "page")

    def _get(url):
        try:
            r = _req.get(url, headers=headers, timeout=5, allow_redirects=True)
            if r.status_code == 200 and "<" in r.text:
                return r.text
        except Exception:
            pass
        return ""

    locs = []
    seen_sm = set()
    for root in (f"https://{domain}/sitemap.xml", f"https://{domain}/sitemap_index.xml"):
        xml = _get(root)
        if not xml:
            continue
        entries = _re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)
        sitemaps = [u for u in entries if u.lower().endswith(".xml")]
        if sitemaps:  # this was a sitemap INDEX → open relevant sub-sitemaps
            for sm in sitemaps:
                if sm in seen_sm:
                    continue
                seen_sm.add(sm)
                if any(w in sm.lower() for w in want):
                    locs += _re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", _get(sm))
        else:         # this was already a flat urlset
            locs += entries
        if locs:
            break

    found, seen = [], set()
    for url in locs:
        u = url.split("#")[0].split("?")[0]
        if u in seen or u.lower().endswith(".xml"):
            continue
        if any(s in u.lower() for s in segs):
            seen.add(u)
            hint = _slug_to_company_hint(u.rstrip("/").split("/")[-1])
            found.append({
                "url": u,
                "title": hint,
                "snippet": f"{brand} customer case study: {hint}",
                "group": "own_site",
                "signal_group": "own_site",
                "probe_sublink": True,   # real URL + slug hint; Claude extracts the company
            })
    print(f"  [sitemap] {len(found)} customer/case-study URLs from sitemap")
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

    # Probe logo wall + customer index pages + sitemap directly (parallel with Brave)
    with ThreadPoolExecutor(max_workers=8) as executor:
        logo_future = executor.submit(_probe_logo_wall, domain, brand)
        probe_future = executor.submit(_probe_customer_index_pages, domain, brand)
        sitemap_future = executor.submit(_probe_sitemap, domain, brand)
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

        # Prepend probed pages so they get processed first (highest priority).
        # Logo wall goes in LAST so it ends up at the very top of the list.
        for fut, label in ((sitemap_future, "Sitemap"), (probe_future, "Probe"),
                           (logo_future, "LogoWall")):
            try:
                with lock:
                    for row in fut.result():
                        if row["url"] not in seen_urls:
                            seen_urls.add(row["url"])
                            all_results.insert(0, row)  # prepend = high priority
            except Exception as e:
                print(f"{label} error: {e}")

    print(f"\nTotal URLs collected: {len(all_results)}")
    return all_results
