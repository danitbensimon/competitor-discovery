# email_service.py — Resend transactional email for CompetitorIQ
import os
import io
import csv
import logging
from typing import Optional

log = logging.getLogger(__name__)

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "results@competitoriq.app")
APP_URL = os.environ.get("APP_URL", "https://competitoriq.onrender.com")


def _build_csv_attachment(companies: list) -> str:
    """Return CSV string of full company list."""
    fields = [
        "company_name", "company_domain", "industry", "region", "company_size",
        "b2b_flag", "grade", "score", "confidence", "signal_group",
        "evidence_count", "source_url", "snippet",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for c in companies:
        writer.writerow(c)
    return output.getvalue()


def _build_results_html(companies: list, competitor_domain: str, unlock_url: str) -> str:
    """Build the HTML body for the results email."""
    rows_html = ""
    for i, c in enumerate(companies[:20], 1):   # include first 20 in email preview
        grade_colour = {
            "A": "#22c55e",
            "B": "#f59e0b",
            "C": "#94a3b8",
        }.get(c.get("grade", "-"), "#94a3b8")

        rows_html += f"""
        <tr style="border-bottom:1px solid #1e293b;">
          <td style="padding:10px 8px;color:#94a3b8;font-size:13px;">{i}</td>
          <td style="padding:10px 8px;">
            <strong style="color:#f1f5f9;font-size:14px;">{c.get('company_name','—')}</strong><br>
            <span style="color:#64748b;font-size:12px;">{c.get('company_domain','')}</span>
          </td>
          <td style="padding:10px 8px;color:#94a3b8;font-size:13px;">{c.get('industry','—')}</td>
          <td style="padding:10px 8px;color:#94a3b8;font-size:13px;">{c.get('region','—')}</td>
          <td style="padding:10px 8px;">
            <span style="background:{grade_colour}22;color:{grade_colour};
                         padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600;">
              {c.get('grade','-')}
            </span>
          </td>
        </tr>
        """

    total = len(companies)
    more_note = f"<p style='color:#64748b;font-size:13px;margin-top:8px;'>+ {total - 20} more companies in the attached CSV.</p>" if total > 20 else ""

    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background:#0a0f1a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
      <div style="max-width:680px;margin:0 auto;padding:40px 20px;">

        <!-- Header -->
        <div style="margin-bottom:32px;">
          <h1 style="margin:0;font-size:22px;color:#f1f5f9;font-weight:700;">
            🎯 Your CompetitorIQ results are ready
          </h1>
          <p style="margin:8px 0 0;color:#64748b;font-size:14px;">
            Companies using <strong style="color:#3b82f6;">{competitor_domain}</strong>
            &nbsp;·&nbsp; {total} companies found
          </p>
        </div>

        <!-- CTA -->
        <div style="margin-bottom:32px;">
          <a href="{unlock_url}"
             style="display:inline-block;background:#3b82f6;color:#fff;padding:14px 28px;
                    border-radius:8px;font-size:15px;font-weight:600;text-decoration:none;">
            View Full Results Online →
          </a>
        </div>

        <!-- Table preview -->
        <table style="width:100%;border-collapse:collapse;margin-bottom:8px;">
          <thead>
            <tr style="border-bottom:1px solid #1e293b;">
              <th style="padding:8px;text-align:left;color:#475569;font-size:12px;font-weight:500;">#</th>
              <th style="padding:8px;text-align:left;color:#475569;font-size:12px;font-weight:500;">Company</th>
              <th style="padding:8px;text-align:left;color:#475569;font-size:12px;font-weight:500;">Industry</th>
              <th style="padding:8px;text-align:left;color:#475569;font-size:12px;font-weight:500;">Region</th>
              <th style="padding:8px;text-align:left;color:#475569;font-size:12px;font-weight:500;">Grade</th>
            </tr>
          </thead>
          <tbody>
            {rows_html}
          </tbody>
        </table>
        {more_note}

        <!-- CSV note -->
        <div style="margin-top:24px;padding:16px;background:#0f172a;border-radius:8px;border:1px solid #1e293b;">
          <p style="margin:0;color:#94a3b8;font-size:13px;">
            📎 Full CSV with all {total} companies (including source URLs and snippets) is attached to this email.
          </p>
        </div>

        <!-- Footer -->
        <p style="margin-top:32px;color:#334155;font-size:12px;">
          CompetitorIQ · You received this because you purchased full results for {competitor_domain}.
        </p>
      </div>
    </body>
    </html>
    """


def send_full_results_email(
    to_email: str,
    competitor_domain: str,
    companies: list,
    unlock_token: str,
) -> bool:
    """
    Send the full results email via Resend with a CSV attachment.
    Returns True on success, False on failure.
    """
    if not RESEND_API_KEY:
        log.error("[email] RESEND_API_KEY not set — cannot send email")
        return False

    try:
        import resend
        resend.api_key = RESEND_API_KEY

        unlock_url = f"{APP_URL}/r/{unlock_token}"
        html_body = _build_results_html(companies, competitor_domain, unlock_url)
        csv_content = _build_csv_attachment(companies)

        params = {
            "from": FROM_EMAIL,
            "to": [to_email],
            "subject": f"Your CompetitorIQ results: {len(companies)} companies using {competitor_domain}",
            "html": html_body,
            "attachments": [
                {
                    "filename": f"{competitor_domain.replace('.', '_')}_customers.csv",
                    "content": csv_content.encode("utf-8"),
                }
            ],
        }

        response = resend.Emails.send(params)
        log.info(f"[email] sent to {to_email} | id={response.get('id','?')}")
        return True

    except Exception as e:
        log.error(f"[email] failed to send to {to_email}: {e}")
        return False
