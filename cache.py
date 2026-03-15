# cache.py
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional


def competitor_to_filename(competitor: str) -> str:
    safe = competitor.strip().lower().replace("https://", "").replace("http://", "")
    safe = safe.replace("www.", "")
    safe = safe.replace("/", "_")
    safe = safe.replace(".", "_")
    return f"{safe}.json"


def get_cache_path(competitor: str) -> str:
    os.makedirs("data", exist_ok=True)
    return os.path.join("data", competitor_to_filename(competitor))


def load_cache(competitor: str) -> Optional[Dict[str, Any]]:
    path = get_cache_path(competitor)

    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return None

        if "competitor" not in data:
            return None

        if "companies" not in data:
            return None

        if not isinstance(data["companies"], list):
            return None

        return data

    except Exception as e:
        print(f"[cache] Failed to load cache from {path}: {e}")
        return None


def save_cache(
    competitor: str,
    companies: List[Dict[str, Any]],
    tier: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    path = get_cache_path(competitor)

    payload = {
        "competitor": competitor,
        "saved_at": datetime.utcnow().isoformat() + "Z",
        "tier": tier,
        "company_count": len(companies),
        "companies": companies,
        "metadata": metadata or {},
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[cache] Saved {len(companies)} companies to {path}")
    return path