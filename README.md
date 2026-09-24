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


