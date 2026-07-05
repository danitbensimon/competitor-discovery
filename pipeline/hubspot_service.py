# hubspot_service.py — HubSpot CRM integration for CompetitorIQ
import os
import json
import logging
import urllib.request
import urllib.error
import urllib.parse

log = logging.getLogger(__name__)

HUBSPOT_TOKEN = os.environ.get("HUBSPOT_TOKEN", "")
BASE_URL = "https://api.hubapi.com"


def _headers():
    return {
        "Authorization": f"Bearer {HUBSPOT_TOKEN}",
        "Content-Type": "application/json",
    }


def _post(url: str, payload: dict) -> dict | None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        log.error(f"[hubspot] POST {url} → HTTP {e.code}: {body[:300]}")
        return None
    except Exception as e:
        log.error(f"[hubspot] POST {url} error: {e}")
        return None


def _patch(url: str, payload: dict) -> dict | None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=_headers(), method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        log.error(f"[hubspot] PATCH {url} → HTTP {e.code}: {body[:300]}")
        return None
    except Exception as e:
        log.error(f"[hubspot] PATCH {url} error: {e}")
        return None


def upsert_contact(email: str, competitor_domain: str = "", preview_count: int = 0) -> bool:
    """
    Create or update a HubSpot contact when a user submits their email on CompetitorIQ.
    Also logs a Note with the competitor they searched for.
    Returns True on success.
    """
    if not HUBSPOT_TOKEN:
        log.warning("[hubspot] HUBSPOT_TOKEN not set — skipping")
        return False

    # 1. Create contact (POST /crm/v3/objects/contacts with idProperty=email acts as upsert)
    contact_url = f"{BASE_URL}/crm/v3/objects/contacts"
    properties = {
        "email": email,
        "hs_lead_status": "NEW",
        "leadsource": "CompetitorIQ",
    }
    result = _post(contact_url, {"properties": properties})

    # If contact already exists (409), fetch it by email instead
    contact_id = None
    if result:
        contact_id = result.get("id")
        log.info(f"[hubspot] contact created: {email} id={contact_id}")
    else:
        # Try to fetch existing contact by email
        search_url = f"{BASE_URL}/crm/v3/objects/contacts/search"
        search_payload = {
            "filterGroups": [{"filters": [{"propertyName": "email", "operator": "EQ", "value": email}]}],
            "properties": ["email", "hs_lead_status"],
            "limit": 1,
        }
        search_result = _post(search_url, search_payload)
        if search_result and search_result.get("results"):
            contact_id = search_result["results"][0]["id"]
            log.info(f"[hubspot] existing contact found: {email} id={contact_id}")
            # Update lead status
            _patch(f"{BASE_URL}/crm/v3/objects/contacts/{contact_id}", {"properties": properties})

    if not contact_id:
        log.error(f"[hubspot] could not create or find contact for {email}")
        return False

    # 2. Log a Note on the contact with the competitor search info
    if competitor_domain:
        note_body = (
            f"CompetitorIQ search\n"
            f"Competitor: {competitor_domain}\n"
            f"Companies found: {preview_count}\n"
            f"Status: Email captured, awaiting payment"
        )
        note_url = f"{BASE_URL}/crm/v3/objects/notes"
        note_payload = {
            "properties": {
                "hs_note_body": note_body,
                "hs_timestamp": str(int(__import__('time').time() * 1000)),
            },
            "associations": [
                {
                    "to": {"id": int(contact_id)},
                    "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}],
                }
            ],
        }
        note_result = _post(note_url, note_payload)
        if note_result:
            log.info(f"[hubspot] note logged for contact {contact_id}")

    return True


def mark_contact_paid(email: str, competitor_domain: str = "") -> bool:
    """Update contact status to OPEN (customer) after successful payment."""
    if not HUBSPOT_TOKEN:
        return False

    search_url = f"{BASE_URL}/crm/v3/objects/contacts/search"
    search_payload = {
        "filterGroups": [{"filters": [{"propertyName": "email", "operator": "EQ", "value": email}]}],
        "properties": ["email"],
        "limit": 1,
    }
    result = _post(search_url, search_payload)
    if not result or not result.get("results"):
        log.warning(f"[hubspot] contact not found for paid update: {email}")
        return False

    contact_id = result["results"][0]["id"]
    patch_payload = {
        "properties": {
            "hs_lead_status": "OPEN",
            "leadsource": "CompetitorIQ",
        }
    }
    updated = _patch(f"{BASE_URL}/crm/v3/objects/contacts/{contact_id}", patch_payload)

    if updated and competitor_domain:
        note_body = f"CompetitorIQ — PURCHASE COMPLETED\nCompetitor: {competitor_domain}"
        note_url = f"{BASE_URL}/crm/v3/objects/notes"
        note_payload = {
            "properties": {
                "hs_note_body": note_body,
                "hs_timestamp": str(int(__import__('time').time() * 1000)),
            },
            "associations": [
                {
                    "to": {"id": int(contact_id)},
                    "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}],
                }
            ],
        }
        _post(note_url, note_payload)
        log.info(f"[hubspot] contact marked paid: {email}")

    return bool(updated)
