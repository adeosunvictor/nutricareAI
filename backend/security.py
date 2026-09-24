"""Synthetic-only demo boundaries. These checks do not establish clinical safety.

No authentication, durable storage or verified clinician identity is provided. Never
use this public demonstration with identifiable real-patient records.
"""
from __future__ import annotations
import hashlib
import os
import re
import time
from collections import defaultdict, deque
from typing import Any
from fastapi import HTTPException, Request

MAX_UPLOAD_BYTES = 3 * 1024 * 1024
MAX_PATIENTS = 25
MAX_QUESTION_CHARS = 800
MAX_PATIENT_TEXT = 28_000
MAX_CHUNKS = 100
ALLOWED_EXTENSIONS = {'.pdf', '.csv', '.xlsx', '.docx'}
_TIMES: dict[str, deque[float]] = defaultdict(deque)


def demo_required(confirmed: bool) -> None:
    if not confirmed:
        raise HTTPException(400, 'Only synthetic or fictional records are permitted. Confirm demo-only use.')


def validate_filename(filename: str) -> str:
    safe = os.path.basename(filename or '')
    if not safe or os.path.splitext(safe)[1].lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, 'Supported file formats: PDF, CSV, XLSX, DOCX.')
    return safe[:160]


def validate_file_signature(filename: str, contents: bytes) -> None:
    suffix = os.path.splitext(filename)[1].lower()
    if not contents or len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, 'File must be nonempty and no larger than 3 MB.')
    if suffix == '.pdf' and not contents.startswith(b'%PDF-'):
        raise HTTPException(400, 'This is not a valid PDF file.')
    if suffix in {'.docx', '.xlsx'} and not contents.startswith(b'PK\x03\x04'):
        raise HTTPException(400, 'This file does not appear to be a valid Office document.')


def enforce_rate_limit(request: Request, limit: int = 45, window: int = 60) -> None:
    """Best-effort in-memory limiter. Add an edge limiter for a public deployment."""
    address = request.client.host if request.client else 'unknown'
    token = hashlib.sha256(address.encode()).hexdigest()[:24]
    now = time.monotonic()
    bucket = _TIMES[token]
    while bucket and bucket[0] < now - window:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(429, 'Too many requests. Please wait a moment.')
    bucket.append(now)


def normalize_text(value: Any, max_length: int = MAX_PATIENT_TEXT) -> str:
    text = str(value if value is not None else '')
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', text).strip()[:max_length]


def safe_patient_id(value: str) -> str:
    result = re.sub(r'[^A-Za-z0-9_-]', '', str(value or ''))[:45]
    if not result:
        raise HTTPException(400, 'Missing or invalid patient identifier.')
    return result


def safe_filename(name: str, patient_id: str) -> str:
    name = re.sub(r'[^A-Za-z0-9]+', '_', str(name))[:46].strip('_') or 'Patient'
    return f'{name}_Recommendation.pdf'


def validate_patient(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise HTTPException(422, 'Invalid patient payload.')
    patient_id = safe_patient_id(payload.get('id', ''))
    name = normalize_text(payload.get('name', ''), 110)
    if not name:
        raise HTTPException(422, 'Patient name is required.')
    fields, chunks = payload.get('fields', {}), payload.get('chunks', [])
    if not isinstance(fields, dict) or not isinstance(chunks, list) or len(chunks) > MAX_CHUNKS:
        raise HTTPException(422, 'Invalid patient evidence.')
    clean_chunks, total, identifiers = [], 0, set()
    for item in chunks:
        if not isinstance(item, dict):
            continue
        text = normalize_text(item.get('text', ''), 1800)
        total += len(text)
        if total > MAX_PATIENT_TEXT:
            raise HTTPException(413, 'Patient evidence exceeds the demo context limit.')
        identifier = normalize_text(item.get('id', ''), 75)
        if text and identifier and identifier not in identifiers:
            identifiers.add(identifier)
            clean_chunks.append({'id': identifier, 'text': text,
                'source': normalize_text(item.get('source', ''), 130),
                'location': normalize_text(item.get('location', ''), 100)})
    return {'id': patient_id, 'name': name, 'fields': {
        str(k)[:80]: normalize_text(v, 2500) for k, v in list(fields.items())[:65]
    }, 'chunks': clean_chunks}


def validate_citation_ids(ids: Any, retrieved: list[dict]) -> list[str]:
    allowed = {item['id'] for item in retrieved}
    if not isinstance(ids, list):
        return []
    return list(dict.fromkeys(item for item in ids if isinstance(item, str) and item in allowed))[:10]


# Simple deterministic tripwires, not an allergen classifier or clinical validator.
FINANCIAL = re.compile(r'\b(?:budgets?|affordab(?:le|ility)|financial|finances?|costs?|prices?|'
                       r'expenditure|income|cheap(?:er|est)?|shopping list|ngn|naira)\b|₦', re.I)
UNSUPPORTED_TARGET = re.compile(r'\b(?:\d{3,4}\s*kcal|\d+\s*g(?:rams?)?\s+(?:carbohydrate|protein|fat)\s*(?:per|/)?\s*day)\b', re.I)
ABSOLUTE_MEDICATION = re.compile(r'\b(?:stop|discontinue|reduce|increase|change)\s+(?:taking\s+)?(?:your\s+)?(?:metformin|amlodipine|atorvastatin|insulin|medication|medicine|prescription)\b', re.I)


def validate_patient_facing_text(text: str, allergies: str = '') -> None:
    """Reject some explicit conflicts; a clinician must still review *every* claim."""
    if FINANCIAL.search(text):
        raise HTTPException(502, 'AI output included an unsupported financial planning topic.')
    # Negative precautionary instructions such as 'Do not stop your medicine'
    # must not be mistaken for advice to stop medication.
    medication_check = re.sub(
        r"\b(?:do\s+not|don't|never)\s+(?:stop|discontinue|reduce|increase|change)\b",
        'continue', text, flags=re.I)
    if UNSUPPORTED_TARGET.search(text) or ABSOLUTE_MEDICATION.search(medication_check):
        raise HTTPException(502, 'AI output included an unapproved prescription or medication change.')
    if re.search(r'\bwhole.grain\s+yam\b', text, re.I):
        raise HTTPException(502, 'AI output contains an incorrect food classification.')
    if re.search(r'\b(?:peanut|groundnut)\b', allergies, re.I):
        if re.search(r'\b(?:eat|consume|add|include|try|choose|serve)\s+(?:some\s+)?(?:peanuts?|groundnuts?|peanut\s+butter)\b', text, re.I):
            raise HTTPException(502, 'AI recommendation conflicts with a documented food restriction.')


def validate_edit(current_plan: str, old_text: str, new_text: str, allergies: str = '') -> None:
    """Require an exact, unique quotation so only one intended passage changes."""
    if (not old_text.strip() or not new_text.strip() or len(old_text) > 1500
            or len(new_text) > 2000 or current_plan.count(old_text) != 1):
        raise HTTPException(422, 'Proposed revision did not identify one exact passage in the current plan.')
    validate_patient_facing_text(new_text, allergies)


def guardrail_note() -> str:
    return 'Demo with synthetic data only. AI output is an unverified draft, not a diagnosis or treatment order.'
