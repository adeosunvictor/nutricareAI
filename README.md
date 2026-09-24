# NutriCare AI

A clean, disposable **synthetic-data-only** nutrition assessment workspace. Upload one fictional patient or a group, inspect document evidence, discuss the case with a Cloudflare Workers AI copilot, review an editable ADIME-organized nutrition care draft, mark it reviewed in the fictional demo, and export one PDF per patient.

> **Not for clinical use. Do not upload real patient information.** This public MVP has no authentication, encrypted storage, durable access control, licensed clinical guideline library, medical-device assessment, or validated clinical accuracy. It is an engineering and UI demonstration, not a diagnostic or treatment application. Any Cloudflare-connected file content is sent to the model provider for inference. Check your vendor data-processing and logging settings before considering any future sensitive-data application.

## Capabilities

- Responsive, three-section UI: **patient evidence**, **editable plan draft**, and **patient-specific chat**, plus a collapsible workspace on small screens.
- Single PDF/DOCX or a single patient CSV/XLSX. Group CSV/XLSX uses `patient_id` and `patient_name`. Group PDF/DOCX sections require a new line `PATIENT ID: UNIQUE_ID` followed by `PATIENT NAME: Fictional Name`.
- Factual extraction and source excerpts, clickable patient switcher, visible gaps, human verification, approval and PDF export `Patient_Name_ID_Recommendation.pdf`.
- Cloudflare Workers AI Qwen3 for three-call ADIME-organized draft generation and tool-bounded chat. A draft covers **A**ssessment with source IDs, **D**iagnosis as an unconfirmed PES candidate, **I**ntervention as discussion options with the individual prescription pending, and **M/E** monitoring and evaluation. Original source extracts remain available for review.
- Domain-diverse lexical source selection for the initial assessment; chat retains patient-scoped lexical retrieval with optional Cloudflare embedding reranking via `RETRIEVAL_MODE=hybrid`. This is not a curated clinical guideline retrieval system.
- Financial and food cost planning have been removed from the care-plan workflow and the patient evidence summary UI. Uploaded source documents remain unmodified, and can still contain original financial details in the Sources tab. No budget pricing, household expenditure or shopping-list estimates are generated.
- `backend/security.py`: format checks, bounded input size, basic request throttling, scoped tool context and citation checks. `backend/evaluation.py`: privacy-minimal latency/token counters and offline retrieval scoring helpers; `backend/benchmark.py` exposes a reproducible, five-query retrieval fixture.
- No cookies, no localStorage, no server session/database and no persistent record storage. All active evidence and drafts live only in the current browser page and are sent with each API call. Reloading clears the workspace.

## Run locally

Requires Python 3.12+ (3.11 is also supported by the code) and Node.js only if you wish to run the optional JavaScript syntax check.

```bash
cd nutricare-ai
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# On Windows, copy .env.example .env
# Fill in Cloudflare account ID and API token to enable AI.
python -m uvicorn app:app --reload
```

Open **http://127.0.0.1:8000**. Select **Try sample patients** for three fictional patient records. Upload/verification/manual edit/PDF export work without Cloudflare credentials. AI draft generation and chat display a clear unavailable state until Cloudflare is configured.

## Cloudflare configuration

Set these environment variables in `.env` locally, and in the Vercel project's **Environment Variables** for the deployed app:

```text
CLOUDFLARE_ACCOUNT_ID=your_account_id
CLOUDFLARE_API_TOKEN=your_token
CLOUDFLARE_MODEL=@cf/qwen/qwen3-30b-a3b-fp8
RETRIEVAL_MODE=lexical
```

Create an account-scoped Cloudflare API token with appropriate Workers AI permission. Keep it server-side; never put it in a client JavaScript bundle. The app calls the [official Workers AI OpenAI-compatible endpoint](https://developers.cloudflare.com/workers-ai/configuration/open-ai-compatibility/). For advanced Cloudflare AI Gateway use, optionally set `CLOUDFLARE_AI_BASE_URL` to your approved Workers AI-compatible gateway base URL (the program appends `/chat/completions`). Verify gateway routes and data-logging settings separately. **Gateway rate limiting and guardrails are not automatically enabled simply because the account has AI Gateway.**

`RETRIEVAL_MODE=lexical` prioritizes low latency and makes no embedding inference calls. The initial ADIME assessment uses deterministic domain-diverse lexical source selection to cover multiple record sections with one clinical-draft model call followed by two patient-language calls. For chat, `hybrid` submits one batch of the query and top lexical candidates to Cloudflare's BGE-small model for reranking. This is a small bounded per-request index. There is **no persistent vector database** or curated clinical guideline knowledge base in this MVP. Do not describe it as an accredited clinical RAG system.

## Free Vercel deployment

The root `app.py` exports `backend.main.app`; `vercel.json` sets the Python function duration. The static frontend is under `public/`, which Vercel can serve from its CDN. Import this directory as a Vercel project, use the Python-compatible preset / Other framework if prompted, and supply credentials under Environment Variables. Deploy. No paid database is needed for the disposable synthetic demo.

**Limits:** This MVP deliberately limits uploads to 3 MB and 25 patients; Vercel Functions have a [4.5 MB request payload limit](https://vercel.com/docs/functions/limitations). Scanned PDF OCR, Excel formula evaluation, complex document tables, durable uploads, batch jobs and patient data persistence are *not* implemented. Processing/group assessment runs within request and serverless execution limits. Free quotas, timeouts and cold starts still apply. The provided structure is not a production hospital deployment.

## Files

```text
nutricare-ai/
  public/
    index.html          UI and dialogs
    style.css           responsive visual system
    app.js              browser state, patient switcher, interactions
    demo-patients.csv   sample fictional group upload
  backend/
    __init__.py         Python package marker
    main.py             FastAPI routes
    ingestion.py        parsing + patient segmentation
    extraction.py       evidence sections / missing-field checks
    retrieval.py        lexical / optional hybrid retrieval
    rag.py              Cloudflare inference + structured draft
    agent.py            bounded patient-specific chat and revisions
    security.py         demo guardrails, bounded inputs, validations
    evaluation.py       operational and offline retrieval metrics
    report.py           approved demo PDF export
  tests/test_core.py    existing regression tests
  tests/test_care_plan.py  ADIME draft schema, safe output and API tests
  app.py                Vercel entrypoint
  requirements.txt      Python dependencies
  vercel.json           deployment configuration
  .env.example          environment template
  .gitignore            excludes credentials / generated files
  README.md             this file
```

Copy `.env.example` to `.env`; the real `.env` is **not included** in the ZIP. The backend package marker is kept so the imports work consistently on Vercel and locally.

## Evaluation and testing

```bash
pip install pytest
python -m pytest -q
node --check public/app.js
```

`/api/metrics` returns only in-memory aggregates: upload/chat/assessment counts, p50/p95 processing time and model token counts if provided. Metrics reset on cold starts and are not shared across instances; no patient text is intentionally logged. `backend/benchmark.py` exposes a reproducible five-question fictional lexical retrieval fixture in the UI and via `/api/evaluation` (see `EVALUATION.md`). `backend/evaluation.py` includes Precision@K, Recall@K, reciprocal rank, citation accuracy, patient-leakage checks, and annotated-case answer relevance / groundedness scores. Clinical correctness, groundedness, faithfulness, model hallucination rates and robustness to novel prompt injection need additional *clinician-reviewed golden datasets* and red-team exercises. The ADIME draft validator checks output structure, length, source-ID existence, exclusion of financial planning, the pending-prescription placeholder and two narrow food safety checks. It cannot establish that a cited passage actually supports a clinical claim or that a nutrition intervention is safe. Passing tests is not a claim of clinical safety.

## What "standard" means here

The draft follows the four-step Nutrition Care Process (NCP) documentation sequence, commonly expressed in ADIME. See the [Academy's NCP overview](https://www.eatrightpro.org/practice/nutrition-care-process/ncp-overview). This is **a structure for professional review**, not a claim of NCP Terminology licensing, guideline integration, regulatory clearance, or validated nutrition care.

The initial draft has no verified professional nutrition diagnosis, clinical nutrition prescription, individualized targets, authorized clinician identity or evidence-based guideline library. Its PES statement is a candidate when adequately supported, otherwise it is left blank. A professional must independently inspect source content, approve appropriate terminology and interventions, and decide on monitoring indicators and follow-up. The source links establish where text came from, **not** that a claim is medically correct.

**Cloudflare's live output has not been tested with your credentials.** If the model fails the expanded schema, the application displays an error instead of fabricating a missing assessment. See `tests/test_care_plan.py` for mocked inference and regression examples.

## Public demo safety boundaries

- Rejects upload without fictional-data confirmation, but attestation alone cannot verify anonymization. Never upload identifiable patients.
- No login means **no actual access control**. The backend processes only the active patient object submitted for that request, but a determined user could submit any object they possess. It is not a secure multi-tenant implementation.
- Text in uploaded records remains untrusted; the agent uses predeclared retrieval tools and has no autonomous database write, network browsing or code execution capability. Prompt injection is not perfectly preventable, and the system must never be granted real records until stronger controls are implemented.
- Generated answers and nutrition drafts are explicitly unverified. A fictional reviewer must inspect/edit/approve each report. The approval is a UI workflow in a public demo, not verifiable professional identity.
- No validated nutrition/medical guideline library is bundled, and the AI should not make clinical treatment claims from source records alone. Use a qualified professional for real cases.

## Future engineering work

Add identity verification and patient- and tenant-scoped server-side authorization, consent and legal/privacy review, secure storage, async upload jobs, scanned PDF support, de-identification tools, clinically versioned guideline retrieval, evidence provenance at field level, independent safety validation, audit events, distributed rate limiting, and production eval datasets before handling real patient data.


## Portfolio release checklist

- [ ] Run `python -m pytest -q` and `node --check public/app.js`.
- [ ] Configure your existing Cloudflare account and token in your local `.env`; do not commit it.
- [ ] Manually assess at least two fictional patient records with the real configured model, inspect the cited evidence and all three generated sections, propose and accept/reject a copilot edit, and export/open each PDF. Automated tests mock the provider and cannot confirm live response quality.
- [ ] Open the Evaluation tab, check the transparent fixture and operational counters. Do not describe fixture retrieval scores as clinical/LLM accuracy.
- [ ] Confirm the host's free-tier function duration, payload size, model latency, and quotas against the running app; three LLM requests are made per assessment. A 60-second function timeout is not proof that every real assessment will complete.
- [ ] Add project-level usage protection before sharing a public endpoint broadly. The current in-process rate limiter is not distributed across Vercel instances and cannot reliably cap your provider spending.
- [ ] Keep the fictional-only upload restriction and professional-review status visible. Do not submit identifiable real patient records.
- [ ] Select an open-source license before publishing the repository; code being visible is not automatically licensed for reuse.
