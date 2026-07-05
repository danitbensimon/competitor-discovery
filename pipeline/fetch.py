# fetch.py — Downloads page content and returns clean plain text.
# Falls back gracefully if the page is blocked or unreachable.

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
MAX_CHARS = 4000  # Truncate to keep Claude prompts manageable


def fetch_page_text(url: str, timeout: int = 3) -> str:
    """
    Downloads a URL and returns clean plain text.
    Returns an empty string if the page is unreachable or blocked.
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            return ""

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove noise
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)
        return text[:MAX_CHARS]

    except Exception:
        return ""
