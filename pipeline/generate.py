# generate.py — Generates a short email opener and LinkedIn note per company.
# Only runs for companies that pass classification filters.

import anthropic

client = anthropic.Anthropic()

def generate_outreach(companies: list[dict]) -> list[dict]:
    """
    For each company that is B2B and targets marketing or B2B SaaS,
    generate a short email opener and LinkedIn connection note.
    """
    qualified = [c for c in companies if c.get("is_b2b") and (
        c.get("targets_marketing") or c.get("targets_b2b_saas")
    )]
    print(f"  {len(qualified)} of {len(companies)} companies qualify for outreach.")

    for company in companies:
        if company in qualified:
            company = generate_one(company)
        else:
            company["email_opener"] = ""
            company["linkedin_note"] = ""
    return companies

def generate_one(company: dict) -> dict:
    prompt = f"""You are a friendly, concise B2B sales rep.

Write outreach for this company:
- Name: {company['name']}
- Domain: {company['domain']}
- Targets marketing teams: {company['targets_marketing']}
- Targets B2B SaaS: {company['targets_b2b_saas']}

Generate two things:

EMAIL_OPENER: A 1–2 sentence cold email opener. Warm, specific, no fluff.
LINKEDIN_NOTE: A 1-sentence LinkedIn connection request note. Casual and human.

Respond in this exact format:
EMAIL_OPENER: <text>
LINKEDIN_NOTE: <text>
"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        print(f"  Warning: Claude API error generating outreach for {company['name']}: {e}")
        company["email_opener"] = ""
        company["linkedin_note"] = ""
        return company

    raw = message.content[0].text
    company["email_opener"] = _parse_field(raw, "EMAIL_OPENER")
    company["linkedin_note"] = _parse_field(raw, "LINKEDIN_NOTE")
    return company

def _parse_field(text: str, key: str) -> str:
    for line in text.splitlines():
        if line.startswith(key + ":"):
            return line.split(":", 1)[1].strip()
    return ""
