# validate.py — Verifies that every company's source_url actually resolves (HTTP 200)
# before results are shown to the user. This kills two problems at once:
#   1. Hallucinated/garbled source URLs that the extraction model invents.
#   2. Real index sub-links that 404 because they were never fetched.
#
# A source that does not return 200 is not a "verified customer" — so by default
# those rows are dropped. Set DROP_INVALID = False to keep the row but blank the
# dead link instead (the frontend then shows the company with no source link).

import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

DROP_INVALID = True          # drop companies whose source link is unreachable
TIMEOUT = 5                  # seconds per request
MAX_WORKERS = 10             # parallel validation

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def _url_ok(url: str) -> bool:
    """True only if the URL resolves to a real, non-error page (final status 200)."""
    if not url or not url.startswith("http"):
        return False
    try:
        # HEAD first (cheap). Some servers reject HEAD with 403/405 → retry with GET.
        resp = requests.head(url, headers=_HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if resp.status_code in (403, 405, 501) or resp.status_code >= 400:
            resp = requests.get(
                url, headers=_HEADERS, timeout=TIMEOUT,
                allow_redirects=True, stream=True,
            )
            resp.close()
        return resp.status_code == 200
    except Exception:
        return False


def validate_sources(companies: list[dict]) -> list[dict]:
    """
    Check each company's source_url in parallel.
    - Reachable (200)  → keep, mark source_valid=True
    - Unreachable      → drop (DROP_INVALID=True) or blank the link (False)
    De-duplicates URL checks so the same link is only fetched once.
    """
    if not companies:
        return companies

    urls = {c.get("source_url", "") for c in companies if c.get("source_url")}
    status: dict[str, bool] = {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        future_to_url = {ex.submit(_url_ok, u): u for u in urls}
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                status[url] = future.result()
            except Exception:
                status[url] = False

    kept = []
    dropped = 0
    for c in companies:
        url = c.get("source_url", "")
        ok = status.get(url, False)
        if ok:
            c["source_valid"] = True
            kept.append(c)
        else:
            if DROP_INVALID:
                dropped += 1
                continue
            c["source_valid"] = False
            c["source_url"] = ""        # don't render a broken link
            kept.append(c)

    print(f"  [validate] {len(kept)} valid / {dropped} dropped (dead source links)")
    return kept
