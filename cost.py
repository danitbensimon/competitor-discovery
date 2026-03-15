# cost.py — estimated run cost + pricing suggestions

TIER_SEARCH_QUERY_COUNT = {
    "lite": 13,
    "pro": 26,
    "advanced": 39,
}

SERPAPI_COST_PER_QUERY = 0.005
EXTRACTION_COST_PER_PAGE = 0.01
CLASSIFICATION_COST_PER_COMPANY = 0.01


def estimate_search_cost(tier="lite", test_mode=False, offline_mode=False):
    if test_mode or offline_mode:
        return 0.0

    query_count = TIER_SEARCH_QUERY_COUNT.get(tier, 13)
    return query_count * SERPAPI_COST_PER_QUERY


def estimate_extraction_cost(page_count):
    return page_count * EXTRACTION_COST_PER_PAGE


def estimate_classification_cost(unique_company_count):
    return unique_company_count * CLASSIFICATION_COST_PER_COMPANY


def count_unique_domains(rows):
    domains = set()

    for row in rows:
        domain = (
            row.get("company_domain")
            or row.get("domain")
            or ""
        ).strip().lower()

        if domain:
            domains.add(domain)

    return len(domains)


def build_price_recommendation(total_cost):
    minimum_price = max(9, round(total_cost * 4))
    safer_price = max(19, round(total_cost * 8))
    strong_margin_price = max(29, round(total_cost * 12))

    return {
        "minimum_price": minimum_price,
        "safer_price": safer_price,
        "strong_margin_price": strong_margin_price,
    }


def build_cost_summary(
    tier="lite",
    test_mode=False,
    offline_mode=False,
    page_count=0,
    classification_rows=None,
):
    if classification_rows is None:
        classification_rows = []

    unique_company_count = count_unique_domains(classification_rows)

    search_cost = estimate_search_cost(
        tier=tier,
        test_mode=test_mode,
        offline_mode=offline_mode,
    )
    extraction_cost = estimate_extraction_cost(page_count)
    classification_cost = estimate_classification_cost(unique_company_count)

    total_cost = search_cost + extraction_cost + classification_cost
    pricing = build_price_recommendation(total_cost)

    return {
        "tier": tier,
        "page_count": page_count,
        "unique_company_count": unique_company_count,
        "search_cost": round(search_cost, 4),
        "extraction_cost": round(extraction_cost, 4),
        "classification_cost": round(classification_cost, 4),
        "total_cost": round(total_cost, 4),
        "minimum_price": pricing["minimum_price"],
        "safer_price": pricing["safer_price"],
        "strong_margin_price": pricing["strong_margin_price"],
    }


def print_cost_summary(summary):
    print("\nEstimated run cost")
    print(f"  Tier: {summary['tier']}")
    print(f"  Pages processed: {summary['page_count']}")
    print(f"  Unique companies classified: {summary['unique_company_count']}")
    print(f"  Search cost: ${summary['search_cost']:.4f}")
    print(f"  Extraction cost: ${summary['extraction_cost']:.4f}")
    print(f"  Classification cost: ${summary['classification_cost']:.4f}")
    print(f"  Total cost: ${summary['total_cost']:.4f}")

    print("\nSuggested one-time pricing")
    print(f"  Minimum viable price: ${summary['minimum_price']}")
    print(f"  Safer price: ${summary['safer_price']}")
    print(f"  Strong margin price: ${summary['strong_margin_price']}")