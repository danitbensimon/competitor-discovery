import anthropic

client = anthropic.Anthropic()


def classify_companies(companies):
    if not companies:
        return companies

    unique = {}
    order = []

    for c in companies:
        domain = (c.get("domain") or c.get("company_domain") or "").lower().strip()
        if not domain:
            continue

        if domain not in unique:
            unique[domain] = {
                "name": c.get("name") or c.get("company_name") or domain,
                "domain": domain,
            }
            order.append(domain)

    results = {}

    for i, domain in enumerate(order):
        comp = unique[domain]
        print(f"  Classifying {i+1}/{len(order)}: {comp['name']}")
        results[domain] = classify_one(comp)

    enriched = []

    for c in companies:
        domain = (c.get("domain") or c.get("company_domain") or "").lower().strip()
        r = results.get(domain)

        row = dict(c)

        if r:
            row["icp_fit"] = r["icp_fit"]
            row["reason"] = r["reason"]
        else:
            row["icp_fit"] = "LOW"
            row["reason"] = "no domain"

        enriched.append(row)

    return enriched


def classify_one(company):
    prompt = f"""
You are a market analyst.

Company: {company['name']}
Domain: {company['domain']}

ICP = B2B SaaS companies relevant for competitor customer prospecting.

Return:

ICP_FIT: HIGH / MEDIUM / LOW
REASON: short reason
"""

    result = {
        "icp_fit": "LOW",
        "reason": ""
    }

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=120,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        print("classification error:", e)
        result["reason"] = "classification failed"
        return result

    text = msg.content[0].text

    for line in text.splitlines():
        if line.startswith("ICP_FIT"):
            val = line.split(":", 1)[1].strip().upper()
            if val in ["HIGH", "MEDIUM", "LOW"]:
                result["icp_fit"] = val

        if line.startswith("REASON"):
            result["reason"] = line.split(":", 1)[1].strip()

    return result