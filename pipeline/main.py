    export_to_csv(export_companies)from preview import show_preview
import sys

from cache import load_cache, save_cache
from search import search_customer_mentions
from rank import rank_candidates
from extract import extract_companies
from classify import classify_companies
from score import aggregate_company_records
from export import export_to_csv
from enrich import enrich_companies
from pricing import apply_tier_limit


def parse_args():
    if len(sys.argv) < 5:
        print("Usage: python3 main.py <competitor_domain> <competitor_name> <mode> <tier>")
        sys.exit(1)

    competitor = sys.argv[1]
    competitor_name = sys.argv[2]
    mode = sys.argv[3].lower()
    tier = sys.argv[4].lower()

    return competitor, competitor_name, mode, tier


def run_pipeline(domain, brand, mode, tier):
    print("[stage] search")
    pages = search_customer_mentions(domain, brand, mode=mode, tier=tier)

    print(f"[debug] pages found: {len(pages)}")

    if not pages:
        print("[info] no pages found → stopping pipeline early")
        return []

    print("[stage] rank")
    ranked = rank_candidates(pages, brand, tier=tier)

    normalized = []
    for page in ranked:
        p = dict(page)

        if "url" not in p:
            if "link" in p:
                p["url"] = p["link"]
            else:
                print("[warn] page missing url → skipping")
                continue

        normalized.append(p)

    if not normalized:
        print("[info] no valid pages after normalization")
        return []

    if mode == "test":
        print("[test mode] Skipping Claude extraction/classification")
        fake_rows = [
            {
                "company_name": "Acme",
                "company_domain": "acme.com",
                "source_url": "https://example.com/acme-case-study",
                "signal_group": "own_site",
                "confidence": "high",
                "evidence_count": 3,
                "score": 90,
                "grade": "A",
                "title": "Acme uses Deel for global hiring",
                "snippet": "Acme explains how it uses Deel to manage international hiring and payroll.",
            },
            {
                "company_name": "StartupX",
                "company_domain": "startupx.com",
                "source_url": "https://example.com/startup-switched",
                "signal_group": "customer_signals",
                "confidence": "medium",
                "evidence_count": 2,
                "score": 75,
                "grade": "B",
                "title": "Startup switched to Deel",
                "snippet": "The company switched to Deel and improved contractor onboarding.",
            },
        ]

        print("[stage] score")
        scored = aggregate_company_records(fake_rows)

        print("[stage] enrich")
        enriched = enrich_companies(scored)

        print("[debug] first enriched company:")
        if enriched:
            print(enriched[0])

        return enriched

    print("[stage] extract")
    extracted = extract_companies(normalized, brand=brand)

    if not extracted:
        print("[info] no companies extracted")
        return []

    print("[stage] classify")
    classified = classify_companies(extracted)

    if not classified:
        print("[info] no classified companies")
        return []

    print("[stage] score")
    scored = aggregate_company_records(classified)

    print("[stage] enrich")
    enriched = enrich_companies(scored)

    print("[debug] first enriched company:")
    if enriched:
        print(enriched[0])

    return enriched


def main():
    competitor, competitor_name, mode, tier = parse_args()

    print("==== Competitor Discovery ====")
    print("competitor:", competitor)
    print("mode:", mode)
    print("tier:", tier)

    use_cache = mode == "live"

    if use_cache:
        cached = load_cache(competitor)

        if cached and cached.get("companies"):
            print("[cache] using cached results")
            companies = cached["companies"]
        else:
            print("[cache] no cache → running pipeline")
            companies = run_pipeline(competitor, competitor_name, mode, tier)

            if companies:
                save_cache(competitor, companies, tier=tier)
            else:
                print("[cache] skip saving empty results")
    else:
        print("[cache] skipped")
        companies = run_pipeline(competitor, competitor_name, mode, tier)

    if not companies:
        print("[info] no companies found")
        export_companies = []
    else:
        show_preview(companies, limit=5)
        export_companies = apply_tier_limit(companies, tier)

    print("[export]")
    export_to_csv(export_companies, competitor=competitor, tier=tier)
    print("DONE. total companies found:", len(companies))
    print("DONE. companies exported:", len(export_companies))


if __name__ == "__main__":
    main()