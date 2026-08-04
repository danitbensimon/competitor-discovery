"""
Domain verification for extracted companies.

The extractor asks Claude to *infer* each company's domain from its name and the
source page (see extract.py: "Use the source URL to help identify the company's
domain when possible"). That guess is never checked, so "Arsi Care Group LLC"
becomes "arsicaregroup.com" whether or not that site is real, reachable, or even
the right company — and the UI then links it as `https://<domain>`, producing
dead, broken-TLS, or wrong links.

Note the asymmetry this fixes: the SOURCE column is hardened in extract.py
(`_snap_source` drops any URL the model didn't actually fetch), but the DOMAIN
column has no such check. This module gives DOMAIN the same "verify or drop"
treatment: each guessed domain must actually serve a page over HTTPS (the scheme
the UI links) or it is blanked, so the row falls back to its verified source
link instead of a fabricated website link.
"""

from concurrent.futures import ThreadPoolExecutor

import requests

# Fields that may hold a company's website domain across the different producers
# (extract.py uses company_domain/domain; run_search sources use company_domain).
DOMAIN_KEYS = ("company_domain", "domain")

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Codes that mean "the site is really there, it just blocks bots" — keep these.
_ALIVE_BUT_BLOCKED = {401, 403, 405, 406, 429}


def _normalize(domain: str) -> str:
    if not domain:
        return ""
    d = str(domain).strip().lower()
    d = d.replace("https://", "").replace("http://", "").replace("www.", "")
    d = d.split("/")[0].strip()
    return d


def _looks_like_domain(domain: str) -> bool:
    # a bare host with a dot and no spaces; rejects "unknown", "n/a", emails, etc.
    return bool(domain) and "." in domain and " " not in domain and "@" not in domain


def _is_live(domain: str, timeout: float = 6.0) -> bool:
    """True if https://<domain> serves a real page over HTTPS — the exact scheme
    the UI links (`https://<domain>`). A domain that only answers on http, fails
    TLS, 404s, or errors out counts as dead, because the link the user clicks is
    always https."""
    if not _looks_like_domain(domain):
        return False
    try:
        r = requests.get(
            f"https://{domain}",
            headers={"User-Agent": _UA, "Accept": "*/*"},
            timeout=timeout,
            allow_redirects=True,
            stream=True,  # don't download the body, we only need the status
        )
        code = r.status_code
        r.close()
    except requests.RequestException:
        return False  # DNS failure, TLS error, connection refused, timeout, ...
    if code in _ALIVE_BUT_BLOCKED:
        return True
    if code in (404, 410) or code >= 500:
        return False
    return code < 400


def verify_domains(companies: list, max_workers: int = 12) -> list:
    """Verify each company's guessed domain resolves over HTTPS. Unverified
    domains are blanked (the guess is preserved under `domain_unverified` for
    debugging) so the UI shows "—" and the verified source link instead of a
    fabricated website link. Each unique domain is checked once. Mutates and
    returns the same list."""
    if not companies:
        return companies

    # One network check per unique domain, run concurrently.
    unique: dict[str, bool] = {}
    for c in companies:
        for k in DOMAIN_KEYS:
            dom = _normalize(c.get(k, ""))
            if dom:
                unique.setdefault(dom, False)

    if unique:
        doms = list(unique.keys())
        with ThreadPoolExecutor(max_workers=min(max_workers, len(doms))) as ex:
            for dom, ok in zip(doms, ex.map(_is_live, doms)):
                unique[dom] = ok

    live = blanked = 0
    for c in companies:
        primary = _normalize(c.get("company_domain") or c.get("domain"))
        if primary and unique.get(primary):
            live += 1
        elif primary:
            blanked += 1
        for k in DOMAIN_KEYS:
            dom = _normalize(c.get(k, ""))
            if dom and not unique.get(dom):
                c.setdefault("domain_unverified", c.get(k, ""))
                c[k] = ""

    print(f"  [verify] {live} domains live, {blanked} blanked (unverified guess)")
    return companies
