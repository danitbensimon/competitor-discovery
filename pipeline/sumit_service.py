# sumit_service.py — SUMIT payment integration for CompetitorIQ
import os
import hmac
import hashlib
import json
import logging

log = logging.getLogger(__name__)

# ── Environment config ─────────────────────────────────────────────────────────
SUMIT_PAYMENT_URL = os.environ.get("SUMIT_PAYMENT_URL", "https://pay.sumit.co.il/hwosrn/sscaj9/sscaja/payment/")
SUMIT_WEBHOOK_SECRET = os.environ.get("SUMIT_WEBHOOK_SECRET", "")  # Set this in Render env vars


# ── Payment URL builder ────────────────────────────────────────────────────────

def build_payment_url(result_id: str, amount: float = 69.0, description: str = "CompetitorIQ Full Results") -> str:
    """
    Build the redirect URL for SUMIT hosted payment page.

    SUMIT hosted payment pages typically accept query parameters to pre-fill
    the payment form and attach metadata. Check your SUMIT dashboard for the
    exact supported parameter names and update the TODOs below.

    Returns a URL string the frontend can redirect to.
    """
    from urllib.parse import urlencode

    params = build_sumit_payment_payload(
        result_id=result_id,
        amount=amount,
        description=description,
    )

    # Build URL with query string
    if params:
        return f"{SUMIT_PAYMENT_URL}?{urlencode(params)}"
    else:
        # If SUMIT doesn't accept query params, return base URL
        # The result_id must be passed via a different mechanism (see TODOs)
        return SUMIT_PAYMENT_URL


def build_sumit_payment_payload(result_id: str, amount: float, description: str) -> dict:
    """
    Build the query-parameter dict (or POST body) for a SUMIT payment session.

    TODO: Replace the placeholder keys below with the actual SUMIT parameter names.
          Log into your SUMIT dashboard → Developer / API docs to find:
            - The parameter name for the order/reference ID  (currently: "reference")
            - The parameter name for the amount              (currently: "amount")
            - The parameter name for the item description    (currently: "description")
            - Whether SUMIT accepts GET params or needs a POST to create a session

    The result_id is the most important field — it lets the webhook handler
    match the payment back to the right search result.
    """
    payload = {
        # TODO: replace "reference" with SUMIT's actual reference/order-id param name
        "reference": result_id,

        # TODO: replace "amount" with SUMIT's actual amount param name
        "amount": str(int(amount)),   # SUMIT may expect integer (agorot) — check docs

        # TODO: replace "description" with SUMIT's actual item/description param name
        "description": description,
    }

    log.info(f"[sumit] built payment payload for result_id={result_id}")
    return payload


# ── Webhook verification ───────────────────────────────────────────────────────

def verify_webhook(raw_body: bytes, signature_header: str) -> bool:
    """
    Verify that the webhook POST came from SUMIT, not a spoofed request.

    TODO: Replace this with SUMIT's actual signature verification method.
          Common patterns:
            1. HMAC-SHA256 of raw body using webhook secret
            2. A shared API key passed in a header
            3. IP allowlist (less secure, but some processors use it)

          Check your SUMIT dashboard → Webhooks / Notifications for the
          signature scheme and the header name that carries the signature.

    Returns True if signature is valid (or if no secret is configured, skips check).
    """
    if not SUMIT_WEBHOOK_SECRET:
        log.warning("[sumit] SUMIT_WEBHOOK_SECRET not set — skipping webhook verification (insecure!)")
        return True  # TODO: remove this bypass once secret is configured

    # TODO: adapt to SUMIT's actual signing scheme
    # Example for HMAC-SHA256:
    expected = hmac.new(
        SUMIT_WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    # TODO: replace "X-Sumit-Signature" with the actual header name SUMIT sends
    is_valid = hmac.compare_digest(expected, signature_header or "")

    if not is_valid:
        log.warning("[sumit] webhook signature mismatch — possible spoofed request")

    return is_valid


# ── Webhook data extractor ─────────────────────────────────────────────────────

def extract_webhook_data(payload: dict) -> dict:
    """
    Parse a SUMIT webhook payload and return a normalised dict with:
      - result_id:  the reference we passed when building the payment URL
      - status:     "paid" | "failed" | "refunded" | "unknown"
      - reference:  SUMIT's own transaction / payment reference
      - amount:     amount charged (float)
      - raw:        original payload for debugging

    TODO: Replace the placeholder keys below with the actual field names
          that SUMIT sends in its webhook POST body.
          Check your SUMIT dashboard → Webhooks for an example payload.
    """
    log.info(f"[sumit] raw webhook payload: {json.dumps(payload, ensure_ascii=False)[:500]}")

    # TODO: replace "reference" with the field SUMIT sends back for the order reference
    result_id = (
        payload.get("reference")
        or payload.get("orderId")
        or payload.get("order_id")
        or payload.get("externalId")
        or ""
    )

    # TODO: replace with SUMIT's actual status field + success value
    raw_status = (
        payload.get("status")
        or payload.get("paymentStatus")
        or payload.get("Status")
        or ""
    )
    # TODO: confirm what SUMIT sends for a successful payment (e.g. "paid", "success", "completed")
    if str(raw_status).lower() in ("paid", "success", "completed", "approved", "1", "true"):
        status = "paid"
    elif str(raw_status).lower() in ("failed", "declined", "error", "rejected", "0", "false"):
        status = "failed"
    else:
        status = "unknown"
        log.warning(f"[sumit] unrecognised payment status: {raw_status!r}")

    # TODO: replace "transactionId" with SUMIT's actual transaction reference field
    payment_reference = (
        payload.get("transactionId")
        or payload.get("transaction_id")
        or payload.get("paymentId")
        or payload.get("Id")
        or ""
    )

    # TODO: replace "amount" with SUMIT's actual amount field
    try:
        amount = float(payload.get("amount") or payload.get("totalAmount") or 0)
    except (TypeError, ValueError):
        amount = 0.0

    return {
        "result_id": result_id,
        "status": status,
        "payment_reference": str(payment_reference),
        "amount": amount,
        "raw": payload,
    }
