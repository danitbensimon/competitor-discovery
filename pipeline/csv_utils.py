# csv_utils.py — CSV generation utilities for CompetitorIQ
import csv
import io


EXPORT_FIELDS = [
    "company_name",
    "company_domain",
    "icp_fit",
    "grade",
    "score",
    "signal_group",
    "industry",
    "region",
    "company_size",
    "confidence",
    "source_url",
    "snippet",
]


def companies_to_csv(companies: list) -> str:
    """Convert a list of company dicts to a CSV string."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=EXPORT_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for c in companies:
        writer.writerow(c)
    return output.getvalue()


def companies_to_csv_bytes(companies: list) -> bytes:
    """Return CSV as UTF-8 bytes (for HTTP response or email attachment)."""
    return companies_to_csv(companies).encode("utf-8")
