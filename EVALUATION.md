# Evaluation and limitations

NutriCare AI exposes **two different measurement types** on the Evaluation tab.

## 1. Reproducible retrieval benchmark

The `GET /api/evaluation` endpoint calls `backend/benchmark.py` on each request. Five fixed, fictional queries have manually assigned relevant passage IDs. A six-passage fixture is ranked using `backend/retrieval.py::lexical_retrieve`. The endpoint reports macro-averaged Precision@K, Recall@K, and mean reciprocal rank, together with per-question retrieved and relevant IDs. Run `python -m pytest -q` to test the endpoint and implementation. Anyone can reproduce the numbers from the committed fixtures without a provider key.

**What these numbers do not mean:** They are not measured on real patient records, live uploads, clinical judgments, or the model's generated answers. They do not measure LLM answer relevance, semantic citation support, groundedness, or recommendation safety. Those fields explicitly return `null` until separately annotated outputs and an evaluation protocol exist. The fixture is deliberately small and easy, so the scores must not be presented as general accuracy or as an independent benchmark.

## 2. Instance-local operational counters

`GET /api/metrics` returns request counts, p50/p95 timing summaries, and any usage totals supplied by the model provider. In-memory counters can reset or differ across serverless instances. These are operational measurements, not quality benchmarks.

## 3. Safety and engineering regression tests

`python -m pytest -q` checks supported ingestion formats, patient-name extraction, report naming, citation-ID validation, pending clinical prescriptions, food-allergy conflict checks, patient-scoped retrieval, edit constraints, and API contracts. The Kemi PDF round-trip test runs when the user-provided PDF is available in the review environment. Do not publish that record without establishing that it is fictional and that you have rights to share it. The fixture is not included in the public project ZIP.

## 4. Future evaluation, explicitly not yet implemented

A larger fictional dataset with independently reviewed source spans and expected findings is needed to measure retrieval performance on realistic documents. Blind human review of generated drafts and proposed edits is needed for answer relevance, claim-level grounding, citation support, omission rate, allergy handling, and actionability. Separate results by patient record and model version; include failures, sample size, and confidence intervals where appropriate. Do not claim clinical validation or an “80% accurate” model without a defined metric and evidence.
