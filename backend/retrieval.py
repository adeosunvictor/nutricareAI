"""Patient-scoped lexical retrieval with optional Workers AI hybrid reranking.

For a fast free MVP lexical retrieval is the default. Set RETRIEVAL_MODE=hybrid
for a bounded embedding pass over the top lexical candidates. This is an
in-request index, not a persistent vector DB or institution-wide knowledge base.
"""
from __future__ import annotations
import math
import os
import re
from collections import Counter
import httpx
from .security import normalize_text

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"the", "and", "that", "for", "with", "what", "does", "have", "this", "from", "their", "patient", "about", "would", "could", "into", "your", "which"}


def terms(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if len(w) > 1 and w not in _STOP]


def lexical_retrieve(query: str, chunks: list[dict], k: int = 5) -> list[dict]:
    if not chunks:
        return []
    words = terms(query)
    if not words:
        return []
    docs = [Counter(terms(c["text"])) for c in chunks]
    avg_length = max(1, sum(sum(d.values()) for d in docs) / len(docs))
    doc_freq = Counter(word for doc in docs for word in doc)
    ranked = []
    for chunk, freqs in zip(chunks, docs):
        score = 0.0
        length = sum(freqs.values())
        for word in words:
            tf = freqs.get(word, 0)
            if not tf:
                continue
            idf = math.log(1 + (len(docs) - doc_freq[word] + .5) / (doc_freq[word] + .5))
            score += idf * tf * 2.2 / (tf + 1.2 * (.25 + .75 * length / avg_length))
        if score > 0:
            ranked.append((score, chunk))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [{**chunk, "retrieval_score": round(score, 4)} for score, chunk in ranked[:k]]


def _cosine(one: list[float], two: list[float]) -> float:
    dot = sum(a * b for a, b in zip(one, two))
    denominator = math.sqrt(sum(x*x for x in one) * sum(x*x for x in two))
    return dot / denominator if denominator else 0.0


async def retrieve(query: str, patient: dict, k: int = 5) -> list[dict]:
    """Only operate on chunks already scoped to the active patient by caller."""
    chunks = patient.get("chunks", [])
    selected = lexical_retrieve(query, chunks, k=max(k, 9))
    # A general request may lack useful lexical matches; show a small overview.
    if not selected and chunks:
        selected = [{**chunk, "retrieval_score": 0.0} for chunk in chunks[:k]]
    if os.getenv("RETRIEVAL_MODE", "lexical") != "hybrid" or len(selected) < 2:
        return selected[:k]
    account = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    if not account or not token:
        return selected[:k]
    # The docs for BGE small specify a maximum of 512 input tokens. Trim
    # text conservatively and batch embeddings in a single provider request.
    inputs = [normalize_text(query, 500)] + [normalize_text(x["text"], 900) for x in selected]
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/v1/embeddings"
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.post(url, headers={"Authorization": f"Bearer {token}"},
                json={"model": os.getenv("EMBEDDING_MODEL", "@cf/baai/bge-small-en-v1.5"), "input": inputs})
            response.raise_for_status()
            vectors = [entry["embedding"] for entry in sorted(response.json()["data"], key=lambda x: x["index"])]
            if len(vectors) != len(inputs):
                return selected[:k]
        maximum = max(x["retrieval_score"] for x in selected) or 1
        for item, vector in zip(selected, vectors[1:]):
            item["retrieval_score"] = round(.65 * item["retrieval_score"] / maximum + .35 * _cosine(vectors[0], vector), 4)
        selected.sort(key=lambda item: item["retrieval_score"], reverse=True)
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
        # Retrieval still works if optional embedding inference is unavailable.
        pass
    return selected[:k]


# A full assessment has several evidence domains. One broad keyword query can
# over-select the same page and omit medication, trend, or allergy information.
# This deterministic source selection makes one fast lexical pass per domain;
# it does not run embeddings or send additional requests to the LLM.
def assessment_evidence(patient: dict, k: int = 12) -> list[dict]:
    chunks = patient.get("chunks", [])
    if not chunks:
        return []
    domain_queries = (
        "name age reason referral medical history diagnoses symptoms",
        "height weight previous weight involuntary changes anthropometrics",
        "current historical medication drugs doses adherence allergies intolerance",
        "laboratory results HbA1c glucose cholesterol renal previous dated",
        "diet meal recall breakfast lunch dinner beverage preference ingredients",
        "work schedule lifestyle clinical follow up missing information",
    )
    chosen: dict[str, dict] = {}
    for query in domain_queries:
        for chunk in lexical_retrieve(query, chunks, k=2):
            if chunk["id"] not in chosen and len(chosen) < k:
                chosen[chunk["id"]] = chunk
    # Supplement with other relevant evidence when multiple domains share a chunk.
    for chunk in lexical_retrieve("nutrition assessment clinical medication diet history", chunks, k=k):
        if len(chosen) >= k:
            break
        chosen.setdefault(chunk["id"], chunk)
    return list(chosen.values())[:k]
