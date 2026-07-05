TIER_LIMITS = {
    "free": 5,
    "lite": 25,
    "pro": None,
}


def get_tier_limit(tier):
    tier = (tier or "").strip().lower()
    return TIER_LIMITS.get(tier, 5)


def apply_tier_limit(companies, tier):
    if not companies:
        return []

    limit = get_tier_limit(tier)

    if limit is None:
        return companies

    return companies[:limit]