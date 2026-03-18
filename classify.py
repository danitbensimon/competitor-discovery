# classify.py — Batch ICP classification
import json
import logging
import anthropic

log = logging.getLogger(__name__)
client = anthropic.Anthropic()

BATCH_SIZE = 20


def classify_companies(companies, competitor_domain="", user_value_prop=""):
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
                "snippet": (c.get("snippet") or c.get("description") or "")[:300],
                "signal_group": c.get("signal_group", ""),
            }
            order.append(domain)

    results = {}
    for i in range(0, len(order), BATCH_SIZE):
        batch_domains = order[i : i + BATCH_SIZE]
        batch = [unique[d] for d in batch_domains]
        log.info(f"[classify] batch {i//BATCH_SIZE + 1} — {len(batch)} companies")
        results.update(_classify_batch(batch, competitor_domain))

    enriched = []
    for c in companies:
        domain = (c.get("domain") or c.get("company_domain") or "").lower().strip()
        r = results.get(domain, {})
        row = dict(c)
        row["icp_fit"] = r.get("icp_fit", "LOW")
        row["reason"]  = r.get("reason", "")
        enriched.append(row)

    return enriched


def _classify_batch(companies: list, competitor_domain: str) -> dict:
    lines = []
    for i, c in enumerate(companies, 1):
        lines.append(
            f"{i}. {c['name']} ({c['domain']})\n"
            f"   Signal: {c.get('signal_group', '')}\n"
            f"   Context: {c.get('snippet', '')}"
        )

    prompt = f"""You are a B2B sales analyst. These companies are customers of {competitor_domain or 'a SaaS competitor'}.

For EACH company, classify how strong a prospect it is for competitor customer poaching.

Return a JSON array. Each object must have:
- "index": number (1-based)
- "icp_fit": "HIGH" | "MEDIUM" | "LOW"
  HIGH = clear B2B company, strong signal they use the competitor, good prospect
  MEDIUM = likely B2B but weaker signal or niche fit
  LOW = unclear, B2C, or poor fit
- "reason": one short sentence

Companies:
{chr(10).join(lines)}

Return ONLY a valid JSON array. No markdown, no explanation.
[{{"index":1,"icp_fit":"HIGH","reason":"..."}}, ...]"""

    result_map = {}
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        for item in json.loads(text):
            idx = int(item.get("index", 0)) - 1
            if 0 <= idx < len(companies):
                result_map[companies[idx]["domain"]] = {
                    "icp_fit": item.get("icp_fit", "LOW"),
                    "reason":  item.get("reason", ""),
                }
    except Exception as e:
        log.error(f"[classify_batch] error: {e}")
        for c in companies:
            result_map[c["domain"]] = {"icp_fit": "LOW", "reason": "classification failed"}

    return result_map
