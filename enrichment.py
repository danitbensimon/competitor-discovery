# enrichment.py

import re

INDUSTRY_KEYWORDS = {
    "Fintech": ["payment", "billing", "fintech", "invoice", "bank"],
    "HRTech": ["hr", "payroll", "employee", "hiring", "talent"],
    "MarTech": ["marketing", "campaign", "lead", "crm", "ads"],
    "DevTools": ["developer", "api", "sdk", "platform", "cloud"],
    "Ecommerce": ["store", "shop", "commerce", "checkout", "retail"],
    "Cybersecurity": ["security", "fraud", "risk", "identity"],
}

REGION_KEYWORDS = {
    "US": ["new york", "san francisco", "california", "texas", "usa"],
    "Europe": ["london", "berlin", "paris", "amsterdam", "uk"],
    "Israel": ["tel aviv", "israel"],
}

def detect_industry(text):
    if not text:
        return "Unknown"

    text = text.lower()

    for industry, keywords in INDUSTRY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return industry

    return "Unknown"


def detect_region(text):
    if not text:
        return "Unknown"

    text = text.lower()

    for region, keywords in REGION_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return region

    return "Unknown"


def detect_b2b(text):
    if not text:
        return "Unknown"

    text = text.lower()

    if any(x in text for x in ["platform", "software", "solution", "enterprise"]):
        return "Likely B2B"

    if any(x in text for x in ["shop", "consumer", "customers buy", "marketplace"]):
        return "Likely B2C"

    return "Unknown"


def enrich_company(company):
    evidence = company.get("evidence_text", "")

    company["industry"] = detect_industry(evidence)
    company["region"] = detect_region(evidence)
    company["b2b_flag"] = detect_b2b(evidence)

    return company