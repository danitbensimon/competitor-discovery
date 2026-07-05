from collections import defaultdict


def normalize_domain(domain):
    if not domain:
        return ""

    domain = str(domain).strip().lower()
    domain = domain.replace("http://", "").replace("https://", "")
    domain = domain.replace("www.", "")
    domain = domain.split("/")[0]
    return domain


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def to_bool(value):
    if isinstance(value, bool):
        return value

    if value is None:
        return False

    text = str(value).strip().lower()
    return text in ["true", "yes", "1", "y"]


def normalize_icp_fit(value):
    if not value:
        return "LOW"

    text = str(value).strip().upper()

    if text in ["HIGH", "STRONG", "GOOD", "YES"]:
        return "HIGH"
    if text in ["MEDIUM", "MID", "PARTIAL"]:
        return "MEDIUM"
    return "LOW"


def confidence_points(confidence_values):
    score = 0

    for confidence in confidence_values:
        c = str(confidence).strip().lower()
        if c == "high":
            score += 5
        elif c == "medium":
            score += 3

    return min(score, 15)


def evidence_points(evidence_count):
    if evidence_count >= 5:
        return 15
    if evidence_count == 4:
        return 12
    if evidence_count == 3:
        return 9
    if evidence_count == 2:
        return 6
    if evidence_count == 1:
        return 3
    return 0


def rank_score_points(max_rank_score, avg_rank_score):
    max_rank_score = safe_int(max_rank_score, 0)
    avg_rank_score = safe_int(avg_rank_score, 0)

    return min(max_rank_score * 2, 20) + min(avg_rank_score, 15)


def icp_fit_points(icp_fit, targets_marketing=False, targets_b2b_saas=False):
    icp_fit = normalize_icp_fit(icp_fit)

    score = 0

    if icp_fit == "HIGH":
        score += 30
    elif icp_fit == "MEDIUM":
        score += 15

    if to_bool(targets_marketing):
        score += 10

    if to_bool(targets_b2b_saas):
        score += 10

    return min(score, 40)


def score_band(score):
    if score >= 75:
        return "A"
    if score >= 55:
        return "B"
    if score >= 35:
        return "C"
    return "D"


def best_confidence(confidence_values):
    normalized = [str(c).strip().lower() for c in confidence_values if c]
    if "high" in normalized:
        return "high"
    if "medium" in normalized:
        return "medium"
    if "low" in normalized:
        return "low"
    return "unknown"


def aggregate_company_records(records):
    grouped = defaultdict(list)

    for record in records:
        domain = normalize_domain(
            record.get("company_domain")
            or record.get("domain")
            or record.get("website")
        )

        if not domain:
            continue

        grouped[domain].append(record)

    scored_companies = []

    for domain, items in grouped.items():
        company_name = ""
        reasons = []
        urls = []
        signal_groups = []
        rank_scores = []
        confidence_values = []

        titles = []
        snippets = []
        descriptions = []
        evidence_parts = []

        targets_marketing_found = False
        targets_b2b_saas_found = False
        high_icp_found = False
        medium_icp_found = False

        for item in items:
            if not company_name:
                company_name = item.get("company_name") or item.get("name") or domain

            reason = item.get("reason")
            if reason and reason not in reasons:
                reasons.append(str(reason))

            source_url = item.get("source_url") or item.get("url")
            if source_url and source_url not in urls:
                urls.append(str(source_url))

            signal_group = item.get("signal_group")
            if signal_group and signal_group not in signal_groups:
                signal_groups.append(str(signal_group))

            title = item.get("title")
            if title and title not in titles:
                titles.append(str(title))

            snippet = item.get("snippet")
            if snippet and snippet not in snippets:
                snippets.append(str(snippet))

            description = item.get("description")
            if description and description not in descriptions:
                descriptions.append(str(description))

            rank_score = safe_int(
                item.get("rank_score")
                or item.get("signal_score")
                or item.get("search_score")
                or item.get("score")
                or 0
            )
            rank_scores.append(rank_score)

            confidence_values.append(item.get("confidence", ""))

            if to_bool(item.get("targets_marketing")):
                targets_marketing_found = True

            if to_bool(item.get("targets_b2b_saas")):
                targets_b2b_saas_found = True

            icp = normalize_icp_fit(item.get("icp_fit"))
            if icp == "HIGH":
                high_icp_found = True
            elif icp == "MEDIUM":
                medium_icp_found = True

            for field in [
                item.get("company_name"),
                item.get("company_domain"),
                item.get("title"),
                item.get("snippet"),
                item.get("description"),
                item.get("reason"),
                item.get("signal_group"),
            ]:
                if field:
                    evidence_parts.append(str(field))

        evidence_count = len(items)
        max_rank_score = max(rank_scores) if rank_scores else 0
        avg_rank_score = round(sum(rank_scores) / len(rank_scores)) if rank_scores else 0

        if high_icp_found:
            final_icp_fit = "HIGH"
        elif medium_icp_found:
            final_icp_fit = "MEDIUM"
        else:
            final_icp_fit = "LOW"

        score_from_rank = rank_score_points(max_rank_score, avg_rank_score)
        score_from_evidence = evidence_points(evidence_count)
        score_from_confidence = confidence_points(confidence_values)
        score_from_icp = icp_fit_points(
            final_icp_fit,
            targets_marketing=targets_marketing_found,
            targets_b2b_saas=targets_b2b_saas_found,
        )

        total_score = (
            score_from_rank
            + score_from_evidence
            + score_from_confidence
            + score_from_icp
        )

        primary_title = titles[0] if titles else ""
        primary_snippet = snippets[0] if snippets else ""
        primary_description = descriptions[0] if descriptions else ""
        primary_url = urls[0] if urls else ""

        scored_companies.append({
            "company_name": company_name,
            "company_domain": domain,
            "title": primary_title,
            "snippet": primary_snippet,
            "description": primary_description,
            "source_url": primary_url,
            "confidence": best_confidence(confidence_values),
            "evidence_text": " | ".join(evidence_parts[:20]),
            "evidence_count": evidence_count,
            "signal_groups": " | ".join(signal_groups[:5]),
            "signal_group": signal_groups[0] if signal_groups else "",
            "max_rank_score": max_rank_score,
            "avg_rank_score": avg_rank_score,
            "targets_marketing": targets_marketing_found,
            "targets_b2b_saas": targets_b2b_saas_found,
            "icp_fit": final_icp_fit,
            "score_rank": score_from_rank,
            "score_evidence": score_from_evidence,
            "score_confidence": score_from_confidence,
            "score_icp": score_from_icp,
            "score": total_score,
            "grade": score_band(total_score),
            "top_reason": reasons[0] if reasons else "",
            "all_reasons": " | ".join(reasons[:5]),
            "evidence_urls": " | ".join(urls[:5]),
        })

    scored_companies.sort(
        key=lambda x: (
            x["score"],
            x["evidence_count"],
            x["max_rank_score"],
        ),
        reverse=True,
    )

    return scored_companies