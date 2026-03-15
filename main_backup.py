# main.py — Entry point. Runs the full workflow end-to-end.

import sys
import config
from search import search_customer_mentions, brand_from_domain
from extract import extract_companies
from classify import classify_companies
from generate import generate_outreach
from export import export_to_csv

def run(domain: str, brand: str = None):
    config.validate()  # Fail fast if API keys are missing

    if not brand:
        brand = brand_from_domain(domain)

    print(f"\n[1/5] Searching for {brand} customer mentions")
    pages = search_customer_mentions(domain, brand=brand)

    print(f"\n[2/5] Fetching page content and extracting companies")
    companies = extract_companies(pages, brand=brand)

    if not companies:
        print("No companies extracted. Exiting.")
        return

    print(f"\n[3/5] Classifying {len(companies)} companies")
    companies = classify_companies(companies)

    print(f"\n[4/5] Generating outreach")
    companies = generate_outreach(companies)

    print(f"\n[5/5] Exporting to CSV")
    export_to_csv(companies)

    print("\nDone.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <domain> [brand name]")
        print("Example: python main.py deel.com")
        print("Example: python main.py redpoints.com 'Red Points'")
        sys.exit(1)
    domain = sys.argv[1]
    brand = sys.argv[2] if len(sys.argv) > 2 else None
    run(domain, brand)
