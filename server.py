# server.py — FastAPI backend for Competitor Customer Discovery
import os
import sys
import uuid
import logging
from datetime import datetime
from typing import Optional

import config  # loads .env via load_dotenv()

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
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

# Logging
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="Competitor Customer Discovery")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store (good enough for MVP)
jobs: dict = {}


class SearchRequest(BaseModel):
    domain: str
    tier: str = "lite"
    mode: str = "live"


class ExportRequest(BaseModel):
    job_id: str
    tier: str = "lite"


def run_pipeline(domain: str, brand: str, mode: str, tier: str) -> list:
    """Run the full discovery pipeline."""
    log.info(f"[pipeline] start | domain={domain} brand={brand} mode={mode} tier={tier}")

    # Search
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
        enriched = enrich_companies(scored)
        return enriched

    # Rank
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

    # Extract
    extracted = extract_companies(normalized, brand=brand)
    if not extracted:
        return []

    # Classify
    classified = classify_companies(extracted)
    if not classified:
        return []

    # Score
    scored = aggregate_company_records(classified)

    # Enrich
    enriched = enrich_companies(scored)
    return enriched


@app.post("/api/search")
async def start_search(req: SearchRequest, background_tasks: BackgroundTasks):
    """Start a competitor search job. Returns job_id immediately."""
    domain = req.domain.strip().lower().replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]

    if not domain:
        raise HTTPException(status_code=400, detail="Domain is required")

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "id": job_id,
        "domain": domain,
        "status": "running",
        "created_at": datetime.utcnow().isoformat(),
        "companies": [],
        "error": None,
    }

    background_tasks.add_task(_run_job, job_id, domain, req.tier, req.mode)
    return {"job_id": job_id, "status": "running"}


def _run_job(job_id: str, domain: str, tier: str, mode: str):
    """Background task that runs the pipeline and stores results."""
    try:
        brand = brand_from_domain(domain)

        # Check cache first (live mode only)
        if mode == "live":
            cached = load_cache(domain)
            if cached and cached.get("companies"):
                log.info(f"[job {job_id}] cache hit for {domain}")
                jobs[job_id]["companies"] = cached["companies"]
                jobs[job_id]["status"] = "done"
                jobs[job_id]["from_cache"] = True
                return

        companies = run_pipeline(domain, brand, mode, tier)

        if companies and mode == "live":
            save_cache(domain, companies, tier=tier)

        jobs[job_id]["companies"] = companies
        jobs[job_id]["status"] = "done"
        jobs[job_id]["total"] = len(companies)
        log.info(f"[job {job_id}] done — {len(companies)} companies")

    except Exception as e:
        log.error(f"[job {job_id}] error: {e}")
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)


@app.get("/api/results/{job_id}")
async def get_results(job_id: str):
    """Poll for job results. Returns preview (top 5) + locked count."""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] == "running":
        return {"status": "running", "job_id": job_id}

    if job["status"] == "error":
        return {"status": "error", "error": job.get("error", "Unknown error")}

    companies = job.get("companies", [])
    total = len(companies)
    preview = companies[:5]

    # Clean preview data for frontend
    preview_clean = []
    for c in preview:
        preview_clean.append({
            "company_name": c.get("company_name", ""),
            "company_domain": c.get("company_domain", ""),
            "industry": c.get("industry", "Unknown"),
            "region": c.get("region", "Unknown"),
            "b2b_flag": c.get("b2b_flag", "Unknown"),
            "grade": c.get("grade", "-"),
            "score": c.get("score", 0),
            "confidence": c.get("confidence", ""),
            "signal_group": c.get("signal_group", ""),
            "snippet": c.get("snippet", ""),
        })

    return {
        "status": "done",
        "job_id": job_id,
        "domain": job["domain"],
        "total": total,
        "preview": preview_clean,
        "locked": max(0, total - 5),
        "from_cache": job.get("from_cache", False),
    }


@app.post("/api/export")
async def export_results(req: ExportRequest):
    """Export full results as CSV (for paid tiers)."""
    import csv
    import io

    job = jobs.get(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] != "done":
        raise HTTPException(status_code=400, detail="Job not complete")

    companies = apply_tier_limit(job.get("companies", []), req.tier)

    fields = [
        "company_name", "company_domain", "industry", "region", "b2b_flag",
        "grade", "score", "confidence", "signal_group", "evidence_count",
        "source_url", "snippet", "top_reason", "icp_fit",
    ]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for c in companies:
        writer.writerow(c)

    csv_content = output.getvalue()
    domain_slug = job["domain"].replace(".", "_")
    filename = f"{domain_slug}_customers_{datetime.now().strftime('%Y%m%d')}.csv"

    return JSONResponse(
        content={"csv": csv_content, "filename": filename, "count": len(companies)}
    )


@app.get("/api/health")
async def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


# Serve frontend
app.mount("/", StaticFiles(directory="static", html=True), name="static")
