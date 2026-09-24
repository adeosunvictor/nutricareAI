"""NutriCare AI: disposable, synthetic-only FastAPI demonstration."""
from __future__ import annotations
import io
import json
from pathlib import Path
from time import perf_counter
from typing import Literal
from urllib.parse import quote

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import agent, benchmark, evaluation, extraction, ingestion, rag, report, retrieval
from .security import (MAX_UPLOAD_BYTES, demo_required, enforce_rate_limit,
                       safe_filename, validate_file_signature, validate_filename,
                       validate_patient)

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
app = FastAPI(title="NutriCare AI", docs_url=None, redoc_url=None,
              description="Synthetic data only. Not a clinical device.")


@app.middleware("http")
async def secure_demo_response(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        enforce_rate_limit(request)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "public, max-age=120"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = ("default-src 'self'; script-src 'self'; style-src 'self'; "
             "img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; "
             "base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
    return response


@app.get("/api/health")
async def health():
    return {"status": "ok", "ai_configured": rag.configured(), "model": rag.MODEL,
            "demo_only": True, "persistent_storage": False,
            "retrieval_mode": __import__("os").getenv("RETRIEVAL_MODE", "lexical")}


@app.get("/api/metrics")
async def metrics():
    return evaluation.dashboard()


@app.get("/api/evaluation")
async def retrieval_evaluation():
    return benchmark.run_benchmark()


@app.post("/api/upload")
async def upload(file: UploadFile = File(...), mode: Literal["single", "group"] = Form(...),
                 demo_confirmed: bool = Form(False)):
    demo_required(demo_confirmed)
    start = perf_counter()
    name = validate_filename(file.filename or "")
    contents = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()
    validate_file_signature(name, contents)
    try:
        patients = ingestion.parse_file(contents, name, mode)
        for patient in patients:
            patient["evidence"] = extraction.summarize(patient)
        evaluation.record("upload", evaluation.elapsed(start), True)
        return {"patients": patients, "count": len(patients), "disclaimer": "Synthetic records only. Verify all extracted facts."}
    except Exception:
        evaluation.record("upload", evaluation.elapsed(start), False)
        raise


class PatientRequest(BaseModel):
    patient: dict
    demo_confirmed: bool = False


@app.post("/api/assess")
async def assess(payload: PatientRequest):
    demo_required(payload.demo_confirmed)
    patient = validate_patient(payload.patient)
    start = perf_counter()
    if not rag.configured():
        raise HTTPException(503, "Configure Cloudflare in .env or Vercel environment variables to generate an AI draft.")
    missing = extraction.summarize(patient)["missing"]
    found = retrieval.assessment_evidence(patient, k=12)
    # This single LLM call returns all panels of the proposed draft at once.
    try:
        draft, usage = await rag.draft_assessment(patient, found, missing)
        evaluation.record("assessment", evaluation.elapsed(start), True, usage)
        return {"draft": draft, "evidence": found, "missing": missing,
                "status": "pending_clinician_review"}
    except Exception:
        evaluation.record("assessment", evaluation.elapsed(start), False)
        raise


class ChatRequest(BaseModel):
    patient: dict
    message: str = Field(min_length=1, max_length=800)
    current_plan: str = Field(default="", max_length=12000)
    history: list[dict] = Field(default_factory=list, max_length=12)
    demo_confirmed: bool = False


@app.post("/api/chat")
async def chat(payload: ChatRequest):
    demo_required(payload.demo_confirmed)
    patient = validate_patient(payload.patient)
    start = perf_counter()
    try:
        result, usage, retrieved = await agent.chat(patient, payload.message.strip(),
                                                     payload.current_plan, payload.history)
        evaluation.record("chat", evaluation.elapsed(start), True, usage)
        return {"result": result, "sources": retrieved}
    except Exception:
        evaluation.record("chat", evaluation.elapsed(start), False)
        raise


class ReportRequest(BaseModel):
    patient: dict
    plan: str = Field(min_length=20, max_length=12000)
    reviewer: str = Field(min_length=2, max_length=90)
    approved: bool = False
    demo_confirmed: bool = False


@app.post("/api/report")
async def export_report(payload: ReportRequest):
    demo_required(payload.demo_confirmed)
    if not payload.approved:
        raise HTTPException(422, "Please review and approve the draft before exporting.")
    patient = validate_patient(payload.patient)
    pdf = report.build_pdf(patient, payload.plan, payload.reviewer.strip())
    name = safe_filename(patient["name"], patient["id"])
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}",
                             "Cache-Control": "no-store"})


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index():
    return (PUBLIC / "index.html").read_text(encoding="utf-8")


# In development these serve static files. On Vercel, /public files can be CDN-served.
app.mount("/", StaticFiles(directory=str(PUBLIC)), name="public")
