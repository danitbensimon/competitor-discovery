import csv


def load_offline_companies(file_path):
    rows = []

    with open(file_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for r in reader:
            rows.append({
                "company_name": r.get("company_name") or r.get("name"),
                "company_domain": r.get("company_domain") or r.get("domain"),
                "rank_score": int(r.get("rank_score", 5)),
                "confidence": r.get("confidence", "medium"),
                "signal_group": r.get("signal_group", "offline"),
                "source_url": r.get("source_url", "offline_dataset"),
            })

    print(f"Loaded {len(rows)} offline evidence rows")
    return rows