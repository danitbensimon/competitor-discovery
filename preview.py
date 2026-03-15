def show_preview(companies, limit=5):
    print("\n==== Preview ====")

    if not companies:
        print("No companies to preview")
        print("==== End Preview ====\n")
        return

    shown = companies[:limit]
    print(f"Showing top {len(shown)} of {len(companies)} companies\n")

    for idx, company in enumerate(shown, start=1):
        company_name = company.get("company_name") or "-"
        company_domain = company.get("company_domain") or "-"
        grade = company.get("grade") or "-"
        industry = company.get("industry") or "Unknown"
        confidence = company.get("confidence") or "Unknown"
        score = company.get("score", 0)

        signal = (
            company.get("signal_groups")
            or company.get("signal_group")
            or "-"
        )

        source = (
            company.get("source_url")
            or company.get("evidence_urls")
            or "-"
        )

        print(f"{idx}. {company_name} ({company_domain})")
        print(f"   Grade: {grade} | Industry: {industry} | Confidence: {confidence} | Score: {score}")
        print(f"   Signal: {signal}")
        print(f"   Source: {source}")
        print("")

    print("==== End Preview ====\n")