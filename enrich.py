import re


INDUSTRY_KEYWORDS = {
    "HRTech": [
        "hiring", "payroll", "employee", "employees", "contractor", "contractors",
        "recruiting", "talent", "hr", "workforce", "onboarding"
    ],
    "Fintech": [
        "payment", "payments", "invoice", "invoicing", "billing", "bank", "fintech",
        "expense", "expenses", "financial"
    ],
    "MarTech": [
        "marketing", "campaign", "campaigns", "crm", "lead", "leads", "advertising",
        "ads", "attribution", "demand gen"
    ],
    "DevTools": [
        "developer", "developers", "api", "sdk", "engineering", "cloud",
        "infrastructure", "devops", "platform"
    ],
    "Ecommerce": [
        "store", "shop", "checkout", "retail", "ecommerce", "commerce", "merchant"
    ],
    "Cybersecurity": [
        "security", "cyber", "fraud", "identity", "compliance", "risk", "threat"
    ],
}


REGION_KEYWORDS = {
    "US": [
        "usa", "united states", "new york", "san francisco", "california",
        "texas", "austin", "boston", "chicago"
    ],
    "Europe": [
        "uk", "united kingdom", "london", "berlin", "paris", "amsterdam",
        "germany", "france", "spain", "europe"
    ],
    "Israel": [
        "israel", "tel aviv", "jerusalem", "herzliya"
    ],
}


B2B_KEYWORDS = [
    "enterprise", "businesses", "companies", "platform", "software", "solution",
    "solutions", "b2b", "teams", "organization", "organizations"
]

B2C_KEYWORDS = [
    "consumers", "consumer", "shoppers", "shop", "marketplace", "buyers", "b2c"
]

SIZE_KEYWORDS = {
    "Startup": ["startup", "early-stage", "seed", "bootstrap", "pre-series", "small team", "founding team"],
    "SMB": ["smb", "small business", "series a", "growing team", "50 employees", "100 employees"],
    "Mid-Market": ["mid-market", "midsize", "series b", "series c", "500 employees", "scaling", "hundreds of"],
    "Enterprise": ["enterprise", "fortune 500", "fortune500", "multinational", "thousands of employees", "global company", "large organization"],
}


def clean_text(value):
    if not value:
        return ""
    return str(value).strip().lower()


def combine_company_text(company):
    parts = [
        company.get("company_name", ""),
        company.get("company_domain", ""),
        company.get("title", ""),
        company.get("snippet", ""),
        company.get("description", ""),
        company.get("evidence", ""),
        company.get("evidence_text", ""),
        company.get("source_url", ""),
        company.get("signal_group", ""),
    ]
    return " ".join([clean_text(p) for p in parts if p])


def detect_industry(text):
    if not text:
        return "Unknown"

    scores = {}

    for industry, keywords in INDUSTRY_KEYWORDS.items():
        count = 0
        for kw in keywords:
            if kw in text:
                count += 1
        if count > 0:
            scores[industry] = count

    if not scores:
        return "Unknown"

    return max(scores, key=scores.get)


def detect_region(text):
    if not text:
        return "Unknown"

    for region, keywords in REGION_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return region

    return "Unknown"


def detect_company_size(text):
    if not text:
        return "Unknown"
    for size, keywords in SIZE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return size
    return "Unknown"


def detect_b2b(text):
    if not text:
        return "Unknown"

    b2b_hits = sum(1 for kw in B2B_KEYWORDS if kw in text)
    b2c_hits = sum(1 for kw in B2C_KEYWORDS if kw in text)

    if b2b_hits > b2c_hits and b2b_hits > 0:
        return "Likely B2B"

    if b2c_hits > b2b_hits and b2c_hits > 0:
        return "Likely B2C"

    return "Unknown"


def enrich_company(company):
    text = combine_company_text(company)

    company["industry"] = detect_industry(text)
    company["region"] = detect_region(text)
    company["b2b_flag"] = detect_b2b(text)
    company["company_size"] = detect_company_size(text)

    return company


def enrich_companies(companies):
    if not companies:
        return []

    return [enrich_company(company) for company in companies]