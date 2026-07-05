import csv
from datetime import datetime


EXPORT_FIELDS = [
    "company_name",
    "company_domain",
    "industry",
    "region",
    "b2b_flag",
    "grade",
    "score",
    "confidence",
    "signal_group",
    "signal_groups",
    "evidence_count",
    "source_url",
    "evidence_urls",
    "title",
    "snippet",
    "description",
    "top_reason",
    "all_reasons",
    "icp_fit",
    "targets_marketing",
    "targets_b2b_saas",
    "max_rank_score",
    "avg_rank_score",
    "score_rank",
    "score_evidence",
    "score_confidence",
    "score_icp",
]


def sanitize_name(value):
    if not value:
        return "unknown"
    value = str(value).strip().lower()
    value = value.replace("https://", "").replace("http://", "")
    value = value.replace("www.", "")
    value = value.replace("/", "_")
    value = value.replace(".", "_")
    value = value.replace(" ", "_")
    return value


def export_to_csv(companies, competitor=None, tier=None):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    competitor_slug = sanitize_name(competitor) if competitor else "customers"
    tier_slug = sanitize_name(tier) if tier else "unknown"

    filename = f"{competitor_slug}_{tier_slug}_{timestamp}.csv"

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=EXPORT_FIELDS, extrasaction="ignore")
        writer.writeheader()

        for company in companies:
            writer.writerow(company)

    print(f"Exported {len(companies)} CLEAN scored companies to ./{filename}")
    return filename