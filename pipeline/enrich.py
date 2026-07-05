import re


INDUSTRY_KEYWORDS = {
    "SaaS / Software": [
        "saas", "software", "platform", "app", "subscription", "cloud-based", "b2b software"
    ],
    "Fintech": [
        "payment", "payments", "invoice", "invoicing", "billing", "bank", "fintech",
        "expense", "expenses", "financial", "lending", "insurance", "capital"
    ],
    "Healthcare / MedTech": [
        "health", "healthcare", "medical", "clinic", "hospital", "patient", "medtech",
        "pharma", "biotech", "wellness", "telemedicine"
    ],
    "E-commerce / Retail": [
        "store", "shop", "checkout", "retail", "ecommerce", "commerce", "merchant",
        "marketplace", "shopify", "direct-to-consumer"
    ],
    "Marketing / AdTech": [
        "marketing", "campaign", "campaigns", "crm", "lead", "leads", "advertising",
        "ads", "attribution", "demand gen", "adtech", "seo", "email marketing"
    ],
    "Cybersecurity": [
        "security", "cyber", "fraud", "identity", "compliance", "risk", "threat",
        "zero trust", "soc", "siem", "endpoint"
    ],
    "Developer Tools": [
        "developer", "developers", "api", "sdk", "engineering", "devops", "infrastructure",
        "open source", "github", "ci/cd", "deployment"
    ],
    "HR Tech": [
        "hiring", "payroll", "employee", "employees", "contractor", "contractors",
        "recruiting", "talent", "hr", "workforce", "onboarding", "hris"
    ],
    "Data & Analytics": [
        "data", "analytics", "business intelligence", "bi", "dashboard", "reporting",
        "data warehouse", "pipeline", "etl", "insights"
    ],
    "Legal Tech": [
        "legal", "law", "attorney", "contract", "compliance", "legaltech", "litigation",
        "trademark", "ip", "intellectual property"
    ],
    "Real Estate": [
        "real estate", "property", "realty", "mortgage", "proptech", "landlord",
        "tenant", "leasing", "commercial property"
    ],
    "Education / EdTech": [
        "education", "edtech", "learning", "training", "university", "school",
        "course", "e-learning", "lms", "curriculum"
    ],
    "Manufacturing": [
        "manufacturing", "factory", "supply chain", "logistics", "industrial",
        "production", "operations", "warehouse", "distribution"
    ],
    "Media & Entertainment": [
        "media", "entertainment", "content", "streaming", "publisher", "news",
        "gaming", "podcast", "video", "music"
    ],
    "Professional Services": [
        "consulting", "agency", "advisory", "accounting", "audit", "staffing",
        "outsourcing", "professional services", "managed services"
    ],
}


REGION_KEYWORDS = {
    "North America": [
        "usa", "united states", "us-based", "new york", "san francisco", "california",
        "texas", "austin", "boston", "chicago", "canada", "toronto", "north america"
    ],
    "Europe": [
        "uk", "united kingdom", "london", "berlin", "paris", "amsterdam",
        "germany", "france", "spain", "europe", "eu", "stockholm", "dublin",
        "barcelona", "milan", "warsaw", "lisbon"
    ],
    "APAC": [
        "india", "australia", "singapore", "japan", "china", "south korea",
        "apac", "asia", "pacific", "hong kong", "sydney", "bangalore", "tokyo"
    ],
    "Latin America": [
        "brazil", "mexico", "argentina", "chile", "colombia", "latam",
        "latin america", "sao paulo", "buenos aires", "bogota"
    ],
    "Middle East & Africa": [
        "dubai", "uae", "saudi", "middle east", "africa", "nigeria", "south africa",
        "kenya", "tel aviv", "israel", "egypt", "qatar"
    ],
    "Israel": [
        "israel", "tel aviv", "jerusalem", "herzliya", "israeli"
    ],
}


SIZE_KEYWORDS = {
    "1-10": ["solo", "solopreneur", "founder-led", "just the founders", "2 people", "small team of"],
    "11-50": ["startup", "early-stage", "seed", "bootstrap", "pre-series", "small team", "founding team", "series a"],
    "51-200": ["smb", "small business", "growing team", "series b", "50 employees", "100 employees", "scale-up"],
    "201-500": ["mid-market", "midsize", "series c", "200 employees", "300 employees", "scaling fast"],
    "501-1000": ["series d", "500 employees", "600 employees", "800 employees", "large team", "hundreds of employees"],
    "1000+": ["enterprise", "fortune 500", "fortune500", "multinational", "thousands of employees",
              "global company", "large organization", "publicly traded", "nasdaq", "nyse"],
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
        count = sum(1 for kw in keywords if kw in text)
        if count > 0:
            scores[industry] = count
    return max(scores, key=scores.get) if scores else "Unknown"


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
    b2b_kw = ["enterprise", "businesses", "companies", "platform", "software",
               "solution", "solutions", "b2b", "teams", "organization", "organizations"]
    b2c_kw = ["consumers", "consumer", "shoppers", "shop", "marketplace", "buyers", "b2c"]
    b2b_hits = sum(1 for kw in b2b_kw if kw in text)
    b2c_hits = sum(1 for kw in b2c_kw if kw in text)
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
