# classify.py — Classifies each company on three criteria using Claude.
# Adds: is_b2b, targets_marketing, targets_b2b_saas (each True/False)

import anthropic

client = anthropic.Anthropic()

def classify_companies(companies: list[dict]) -> list[dict]:
    """
    For each company, asks Claude to classify it on three criteria.
    Adds classification fields to each company dict.
    """
    for i, company in enumerate(companies):
        print(f"  Classifying {i+1}/{len(companies)}: {company['name']}")
        companies[i] = classify_one(company)
    return companies

def classify_one(company: dict) -> dict:
    prompt = f"""You are a B2B market analyst. Based on the company name and domain below, classify it.

Company: {company['name']}
Domain: {company['domain']}

Answer each question with only YES or NO:
1. Is this a B2B company (sells to businesses, not consumers)?
2. Does this company target marketing teams?
3. Does this company target B2B tech or SaaS companies?

Respond in this exact format:
IS_B2B: <YES or NO>
TARGETS_MARKETING: <YES or NO>
TARGETS_B2B_SAAS: <YES or NO>
"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        print(f"  Warning: Claude API error for {company['name']}: {e}. Skipping classification.")
        company["is_b2b"] = False
        company["targets_marketing"] = False
        company["targets_b2b_saas"] = False
        return company

    raw = message.content[0].text
    company["is_b2b"] = _parse_flag(raw, "IS_B2B")
    company["targets_marketing"] = _parse_flag(raw, "TARGETS_MARKETING")
    company["targets_b2b_saas"] = _parse_flag(raw, "TARGETS_B2B_SAAS")
    return company

def _parse_flag(text: str, key: str) -> bool:
    for line in text.splitlines():
        if line.startswith(key + ":"):
            value = line.split(":", 1)[1].strip().upper()
            return value == "YES"
    return False
