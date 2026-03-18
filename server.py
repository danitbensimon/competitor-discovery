# server.py — FastAPI backend for Competitor Customer Discovery
import os
import sys
import uuid
import json
import logging
from datetime import datetime
from typing import Optional

import config  # loads .env via load_dotenv()

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Pipeline imports
from cache import load_cache, save_cache
from search import search_customer_mentions, brand_from_domain
from rank import rank_candidates
from extract import extract_companies
from classify import classify_companies
from score import aggregate_company_records
from enrich import enrich_companies
from pricing import apply_tier_limit

# New: persistence, payments, email, csv
import database as db
from sumit_service import build_payment_url, verify_webhook, extract_webhook_data
from email_service import send_full_results_email
from csv_utils import companies_to_csv

# Logging
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(title="Competitor Customer Discovery")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialise DB on startup
db.init_db()

# In-memory job store (maps job_id → job state while running)
jobs: dict = {}


# ── Request / Response models ─────────────────────────────────────────────────

class SearchRequest(BaseModel):
    domain: str
    tier: str = "lite"
    mode: str = "live"
    icp_industries: list = []
    icp_size: str = ""
    icp_region: str = ""


class ExportRequest(BaseModel):
    job_id: str
    tier: str = "lite"


class EmailRequest(BaseModel):
    email: str


# ── ICP filter ────────────────────────────────────────────────────────────────

def filter_by_icp(companies: list, icp_industries: list, icp_size: str, icp_region: str) -> list:
    if not icp_industries and not icp_size and not icp_region:
        return companies
    filtered = []
    for c in companies:
        if icp_industries and c.get("industry", "Unknown") not in icp_industries:
            continue
        if icp_region and c.get("region", "Unknown") != icp_region:
            continue
        if icp_size and c.get("company_size", "Unknown") != icp_size:
            continue
        filtered.append(c)
    return filtered


# ── Pipeline ──────────────────────────────────────────────────────────────────

def run_pipeline(domain: str, brand: str, mode: str, tier: str) -> list:
    """Run the full discovery pipeline."""
    log.info(f"[pipeline] start | domain={domain} brand={brand} mode={mode} tier={tier}")

    pages = search_customer_mentions(domain, brand, mode=mode, tier=tier)
    log.info(f"[pipeline] pages found: {len(pages)}")

    if not pages:
        return []

    # Test mode fast path
    if mode == "test":
        fake_rows = [
            {
                "company_name": "Acme Corp",
                "company_domain": "acme.com",
                "source_url": "https://example.com/acme-case-study",
                "signal_group": "own_site",
                "confidence": "high",
                "evidence_count": 3,
                "score": 92,
                "grade": "A",
                "title": f"Acme uses {brand} for global hiring",
                "snippet": f"Acme explains how it uses {brand} to manage international hiring and payroll.",
            },
            {
                "company_name": "StartupX",
                "company_domain": "startupx.io",
                "source_url": "https://example.com/startupx-case",
                "signal_group": "customer_signals",
                "confidence": "high",
                "evidence_count": 2,
                "score": 80,
                "grade": "A",
                "title": f"How StartupX scaled globally with {brand}",
                "snippet": f"StartupX switched to {brand} and reduced contractor onboarding time by 60%.",
            },
            {
                "company_name": "GlobalTeam Ltd",
                "company_domain": "globalteam.com",
                "source_url": "https://g2.com/review/globalteam",
                "signal_group": "review_sites",
                "confidence": "medium",
                "evidence_count": 1,
                "score": 65,
                "grade": "B",
                "title": f"{brand} review by GlobalTeam",
                "snippet": "Great tool for managing remote teams across 12 countries.",
            },
            {
                "company_name": "TechFlow",
                "company_domain": "techflow.dev",
                "source_url": "https://example.com/techflow",
                "signal_group": "blog_press",
                "confidence": "medium",
                "evidence_count": 1,
                "score": 58,
                "grade": "B",
                "title": f"TechFlow selects {brand} for payroll",
                "snippet": "TechFlow announced it has selected a new global payroll provider.",
            },
            {
                "company_name": "NovaSoft",
                "company_domain": "novasoft.com",
                "source_url": "https://example.com/nova",
                "signal_group": "customer_signals",
                "confidence": "medium",
                "evidence_count": 1,
                "score": 54,
                "grade": "B",
                "title": f"NovaSoft implements {brand}",
                "snippet": "NovaSoft began using the platform for their 200+ remote contractors.",
            },
            {
                "company_name": "BrightPath",
                "company_domain": "brightpath.co",
                "source_url": "https://example.com/brightpath",
                "signal_group": "own_site",
                "confidence": "low",
                "evidence_count": 1,
                "score": 40,
                "grade": "C",
                "title": f"BrightPath and {brand}",
                "snippet": "BrightPath mentioned using multiple global HR tools.",
            },
            {
                "company_name": "Horizon Labs",
                "company_domain": "horizonlabs.io",
                "source_url": "https://example.com/horizon",
                "signal_group": "blog_press",
                "confidence": "low",
                "evidence_count": 1,
                "score": 37,
                "grade": "C",
                "title": "Horizon Labs global expansion",
                "snippet": "The company expanded internationally using various HR platforms.",
            },
            {
                "company_name": "PulseHR",
                "company_domain": "pulsehr.com",
                "source_url": "https://example.com/pulsehr",
                "signal_group": "review_sites",
                "confidence": "low",
                "evidence_count": 1,
                "score": 32,
                "grade": "C",
                "title": "PulseHR review",
                "snippet": "User mentions switching from legacy payroll tools.",
            },
        ]
        scored = aggregate_company_records(fake_rows)
        classified = classify_companies(scored, competitor_domain=domain)
        enriched = enrich_companies(classified)
        return enriched

    ranked = rank_candidates(pages, brand, tier=tier)
    normalized = []
    for page in ranked:
        p = dict(page)
        if "url" not in p:
            if "link" in p:
                p["url"] = p["link"]
            else:
                continue
        normalized.append(p)

    if not normalized:
        return []

    extracted = extract_companies(normalized, brand=brand)
    if not extracted:
        return []

    classified = classify_companies(extracted, competitor_domain=domain)
    if not classified:
        return []

    scored = aggregate_company_records(classified)
    enriched = enrich_companies(scored)
    return enriched


# ── Background job runner ─────────────────────────────────────────────────────

def _run_job(job_id: str, result_id: str, domain: str, tier: str, mode: str,
             icp_industries: list, icp_size: str, icp_region: str):
    """Background task: runs pipeline, enriches, filters by ICP, persists to DB."""
    try:
        brand = brand_from_domain(domain)

        if mode == "live":
            cached = load_cache(domain)
            if cached and cached.get("companies"):
                log.info(f"[job {job_id}] cache hit for {domain}")
                companies = cached["companies"]
                filtered = filter_by_icp(companies, icp_industries, icp_size, icp_region)
                preview = filtered[:5]
                db.save_companies(result_id, preview=preview, full=filtered)
                jobs[job_id].update({
                    "companies": companies,
                    "filtered": filtered,
                    "status": "done",
                    "from_cache": True,
                })
                return

        companies = run_pipeline(domain, brand, mode, tier)

        if companies and mode == "live":
            save_cache(domain, companies, tier=tier)

        filtered = filter_by_icp(companies, icp_industries, icp_size, icp_region)
        preview = filtered[:5]

        # Persist to DB
        db.save_companies(result_id, preview=preview, full=filtered)

        jobs[job_id].update({
            "companies": companies,
            "filtered": filtered,
            "status": "done",
            "total": len(filtered),
        })
        log.info(f"[job {job_id}] done — {len(companies)} total, {len(filtered)} after ICP filter")

    except Exception as e:
        log.error(f"[job {job_id}] error: {e}")
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)


# ── API endpoints ─────────────────────────────────────────────────────────────

@app.post("/api/search")
async def start_search(req: SearchRequest, background_tasks: BackgroundTasks):
    """Start a competitor search job. Returns result_id and job_id immediately."""
    domain = (req.domain.strip().lower()
              .replace("https://", "").replace("http://", "")
              .replace("www.", "").split("/")[0])

    if not domain:
        raise HTTPException(status_code=400, detail="Domain is required")

    job_id = str(uuid.uuid4())
    result_id = str(uuid.uuid4())

    icp_filters = {
        "industries": req.icp_industries,
        "size": req.icp_size,
        "region": req.icp_region,
    }

    # Persist the search record immediately
    db.create_result(result_id, competitor_domain=domain, icp_filters=icp_filters)

    jobs[job_id] = {
        "id": job_id,
        "result_id": result_id,
        "domain": domain,
        "status": "running",
        "created_at": datetime.utcnow().isoformat(),
        "companies": [],
        "filtered": [],
        "unlocked": False,
        "error": None,
        "icp_industries": req.icp_industries,
        "icp_size": req.icp_size,
        "icp_region": req.icp_region,
    }

    background_tasks.add_task(
        _run_job, job_id, result_id, domain, req.tier, req.mode,
        req.icp_industries, req.icp_size, req.icp_region,
    )

    return {"job_id": job_id, "result_id": result_id, "status": "running"}


@app.get("/api/results/{job_id}")
async def get_results(job_id: str):
    """Poll for job results. Returns top 5 free + locked count, or all if paid."""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] == "running":
        return {"status": "running", "job_id": job_id}

    if job["status"] == "error":
        return {"status": "error", "error": job.get("error", "Unknown error")}

    result_id = job.get("result_id", job_id)

    # Check DB for payment status
    db_record = db.get_result(result_id)
    is_paid = db_record and db_record.get("payment_status") == "paid"

    companies = job.get("filtered") or job.get("companies", [])
    total = len(companies)
    unlocked = job.get("unlocked", False) or is_paid

    visible = companies if (unlocked or total <= 5) else companies[:5]
    locked_count = 0 if (unlocked or total <= 5) else max(0, total - 5)

    def clean(c):
        return {
            "company_name":  c.get("company_name", ""),
            "company_domain": c.get("company_domain", ""),
            "industry":      c.get("industry", "Unknown"),
            "region":        c.get("region", "Unknown"),
            "company_size":  c.get("company_size", "Unknown"),
            "grade":         c.get("grade", "-"),
            "icp_fit":       c.get("icp_fit", "LOW"),
            "score":         c.get("score", 0),
            "confidence":    c.get("confidence", ""),
            "signal_group":  c.get("signal_group", ""),
            "snippet":       c.get("snippet", ""),
            "source_url":    c.get("source_url", ""),
        }

    return {
        "status": "done",
        "job_id": job_id,
        "result_id": result_id,
        "domain": job["domain"],
        "total": total,
        "preview": [clean(c) for c in visible],
        "locked": locked_count,
        "unlocked": unlocked,
        "from_cache": job.get("from_cache", False),
    }


@app.post("/api/results/{result_id}/email")
async def save_email(result_id: str, req: EmailRequest):
    """Capture email address before payment."""
    record = db.get_result(result_id)
    if not record:
        raise HTTPException(status_code=404, detail="Result not found")
    db.update_email(result_id, req.email.strip().lower())
    return {"success": True}


@app.post("/api/results/{result_id}/create-payment")
async def create_payment(result_id: str):
    """Return a SUMIT payment URL with the result_id embedded as reference."""
    record = db.get_result(result_id)
    if not record:
        raise HTTPException(status_code=404, detail="Result not found")

    if record.get("payment_status") == "paid":
        return {"already_paid": True, "unlock_token": record.get("unlock_token")}

    payment_url = build_payment_url(
        result_id=result_id,
        amount=69.0,
        description=f"CompetitorIQ results for {record['competitor_domain']}",
    )

    log.info(f"[payment] created payment URL for result_id={result_id}")
    return {"payment_url": payment_url, "result_id": result_id}


@app.post("/api/payments/sumit/webhook")
async def sumit_webhook(request: Request):
    """
    SUMIT payment webhook — called by SUMIT when a payment completes.
    Marks the result as paid and sends the full results email.
    """
    raw_body = await request.body()

    # TODO: update header name to match what SUMIT actually sends
    signature = request.headers.get("X-Sumit-Signature", "")

    if not verify_webhook(raw_body, signature):
        log.warning("[webhook] signature verification failed")
        raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    data = extract_webhook_data(payload)
    log.info(f"[webhook] received | result_id={data['result_id']} status={data['status']}")

    if data["status"] != "paid":
        log.info(f"[webhook] non-paid status ({data['status']}) — ignoring")
        return {"received": True}

    result_id = data["result_id"]
    if not result_id:
        log.error("[webhook] no result_id in payload")
        return {"received": True}

    record = db.get_result(result_id)
    if not record:
        log.error(f"[webhook] result_id={result_id} not found in DB")
        return {"received": True}

    # Generate unlock token
    unlock_token = str(uuid.uuid4())
    db.mark_paid(result_id, payment_reference=data["payment_reference"], unlock_token=unlock_token)
    log.info(f"[webhook] marked paid | result_id={result_id} token={unlock_token}")

    # Send email if we have an address
    email = record.get("email")
    if email:
        try:
            full_companies = json.loads(record.get("full_companies", "[]"))
            sent = send_full_results_email(
                to_email=email,
                competitor_domain=record["competitor_domain"],
                companies=full_companies,
                unlock_token=unlock_token,
            )
            if sent:
                db.mark_email_sent(result_id)
        except Exception as e:
            log.error(f"[webhook] email failed: {e}")

    return {"received": True, "unlock_token": unlock_token}


@app.get("/api/results/{result_id}/status")
async def check_payment_status(result_id: str):
    """Let the frontend poll payment status after returning from payment page."""
    record = db.get_result(result_id)
    if not record:
        raise HTTPException(status_code=404, detail="Result not found")

    is_paid = record.get("payment_status") == "paid"
    return {
        "result_id": result_id,
        "paid": is_paid,
        "unlock_token": record.get("unlock_token") if is_paid else None,
    }


@app.post("/api/unlock/{job_id}")
async def unlock_results(job_id: str):
    """
    Dev/demo: instantly unlock results without payment.
    Remove or guard this endpoint before going to production!
    """
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job["unlocked"] = True
    log.info(f"[unlock] job {job_id} unlocked (dev mode)")
    return {"success": True, "job_id": job_id}


@app.get("/api/results/{result_id}/csv")
async def download_csv(result_id: str, token: str = ""):
    """Download CSV for a paid result. Requires unlock token."""
    record = db.get_result(result_id)
    if not record:
        raise HTTPException(status_code=404, detail="Result not found")

    # Verify either token matches or payment is confirmed
    stored_token = record.get("unlock_token") or ""
    is_paid = record.get("payment_status") == "paid"

    if not is_paid or (stored_token and token != stored_token):
        raise HTTPException(status_code=403, detail="Payment required")

    companies = json.loads(record.get("full_companies", "[]"))
    csv_content = companies_to_csv(companies)

    domain_slug = record["competitor_domain"].replace(".", "_")
    filename = f"{domain_slug}_customers.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/r/{unlock_token}")
async def token_access(unlock_token: str):
    """
    Secure link sent in email — returns full results for a paid record.
    Redirects to the frontend with the token embedded.
    """
    record = db.get_result_by_token(unlock_token)
    if not record:
        raise HTTPException(status_code=404, detail="Invalid or expired link")

    # Redirect to frontend with token so JS can fetch the full data
    app_url = os.environ.get("APP_URL", "")
    redirect_url = f"{app_url}/?token={unlock_token}"
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=redirect_url)


@app.get("/api/token/{unlock_token}")
async def get_results_by_token(unlock_token: str):
    """Return full results JSON for a valid unlock token."""
    record = db.get_result_by_token(unlock_token)
    if not record:
        raise HTTPException(status_code=404, detail="Invalid or expired token")

    companies = json.loads(record.get("full_companies", "[]"))

    def clean(c):
        return {
            "company_name":  c.get("company_name", ""),
            "company_domain": c.get("company_domain", ""),
            "industry":      c.get("industry", "Unknown"),
            "region":        c.get("region", "Unknown"),
            "company_size":  c.get("company_size", "Unknown"),
            "grade":         c.get("grade", "-"),
            "icp_fit":       c.get("icp_fit", "LOW"),
            "score":         c.get("score", 0),
            "confidence":    c.get("confidence", ""),
            "signal_group":  c.get("signal_group", ""),
            "snippet":       c.get("snippet", ""),
            "source_url":    c.get("source_url", ""),
        }

    return {
        "status": "done",
        "domain": record["competitor_domain"],
        "total": len(companies),
        "preview": [clean(c) for c in companies],
        "locked": 0,
        "unlocked": True,
    }


@app.post("/api/export")
async def export_results(req: ExportRequest):
    """Export full results as CSV (legacy endpoint for dev use)."""
    job = jobs.get(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "done":
        raise HTTPException(status_code=400, detail="Job not complete")

    companies = job.get("filtered") or job.get("companies", [])
    companies = apply_tier_limit(companies, req.tier)
    csv_content = companies_to_csv(companies)

    domain_slug = job["domain"].replace(".", "_")
    filename = f"{domain_slug}_customers_{datetime.now().strftime('%Y%m%d')}.csv"

    return JSONResponse(content={"csv": csv_content, "filename": filename, "count": len(companies)})


@app.get("/api/health")
async def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


# Serve frontend (must be last)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
