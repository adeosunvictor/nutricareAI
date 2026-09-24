
# NutriCare AI

### An AI-powered nutrition assessment and care-planning platform built with RAG, agentic workflows, and evaluation-driven AI engineering.

NutriCare AI is an open-source AI engineering project that transforms fictional patient records into structured nutrition assessments, evidence-informed care-plan drafts, and interactive AI-assisted recommendations.

The application combines document intelligence, patient-scoped retrieval, large language models, constrained AI editing workflows, and an evaluation framework in a responsive web application.

It demonstrates how an end-to-end AI system can be designed to retrieve relevant information, generate structured outputs, support human decision-making, and expose measurable engineering performance.

**[Live Application](YOUR_VERCEL_URL) | [GitHub Repository](https://github.com/adeosunvictor/nutricareAI) | [Evaluation Documentation](EVALUATION.md)**

> **Project scope:** NutriCare AI is a portfolio demonstration intended for fictional or synthetic patient records. It is not a clinically validated medical application. Do not upload real patient information or use its outputs as independent medical advice.

---

## 1. The Problem

Nutrition professionals often need to review information scattered across multiple documents, including:

- Patient assessment records and referral notes.
- Medical histories and medication records.
- Laboratory results and anthropometric measurements.
- Dietary histories, food diaries, and lifestyle information.
- Food allergies, dietary restrictions, and patient preferences.

Transforming this information into a coherent nutrition assessment requires extracting relevant facts, identifying missing information, connecting findings to supporting evidence, and preparing recommendations for professional review.

Traditional document-processing systems can extract information but may struggle to connect findings across documents or support interactive follow-up questions.

NutriCare AI explores how retrieval-augmented generation and AI-assisted workflows can bring these capabilities together in a single application.

---

## 2. What NutriCare AI Can Do

### Intelligent document ingestion

The application processes nutrition assessment records in multiple formats.

Supported formats:

- PDF
- DOCX
- CSV
- XLSX

It supports individual patient records and grouped patient datasets.

The ingestion pipeline extracts document content, identifies patient information, segments records, and generates source-labelled passages for downstream retrieval.

Extracted information includes patient identity, documented clinical information, dietary history, medications, laboratory results, allergies, and other available assessment data.

The system also identifies missing information that may require clarification.

### Patient-specific retrieval-augmented generation

NutriCare AI implements a patient-scoped RAG architecture.

Rather than relying exclusively on the language model's general knowledge, the application retrieves relevant information from the active patient's uploaded record.

Its retrieval pipeline supports two configurations:

**Lexical retrieval**

The default configuration uses lexical relevance scoring to retrieve source passages.

The assessment pipeline also performs domain-diverse evidence selection to improve coverage across different sections of a patient record.

**Hybrid retrieval**

An optional hybrid configuration uses Cloudflare Workers AI embeddings to rerank candidates selected through lexical retrieval.

This combines lexical relevance with embedding-based similarity.

Patient-specific retrieval is scoped to the active patient record, helping prevent information from different uploaded patient records from being mixed during retrieval.

The implementation uses a bounded, in-request evidence index rather than a persistent vector database.

### Structured AI-generated nutrition assessments

NutriCare AI uses Cloudflare Workers AI to generate structured nutrition assessment drafts from retrieved patient evidence.

The assessment follows the ADIME framework:

| Component | Purpose |
| --- | --- |
| Assessment | Organizes relevant patient findings and documented nutrition concerns. |
| Diagnosis | Proposes a nutrition-related diagnosis for professional confirmation when the evidence supports it. |
| Intervention | Develops practical nutrition education and intervention options. |
| Monitoring and Evaluation | Identifies follow-up considerations and indicators for professional review. |

The application uses a three-request generation workflow.

First, the model generates a structured clinical draft. The application then makes two parallel requests to generate the patient-facing care plan.

The resulting outputs undergo schema, citation-ID, and content validation before being presented in the interface.

The system distinguishes documented facts from information requiring further professional assessment.

### Interactive agentic nutrition copilot

NutriCare AI includes an interactive copilot that allows users to explore patient records and refine generated care plans through natural-language instructions.

The copilot can:

- Answer questions about the active patient record.
- Retrieve relevant evidence to support its responses.
- Explain information found in the uploaded documents.
- Identify uncertainty or missing information.
- Propose targeted changes to an existing nutrition care plan.
- Maintain limited conversation context during an active session.

**Human-in-the-loop editing**

The copilot does not automatically rewrite or approve an entire care plan.

When a user requests a modification, the system identifies the relevant passage and proposes a precise replacement.

The proposed edit is checked against the current plan and relevant validation rules.

The user can then review the proposed change before accepting it.

This demonstrates a constrained agentic workflow involving contextual retrieval, model reasoning, structured actions, validation, and human approval.

### Nutrition recommendation and PDF export

The application generates patient-facing nutrition care-plan drafts that organize information into accessible sections.

These include explanations of recorded findings, practical nutrition steps, meal options, relevant precautions, and follow-up considerations.

Users can review and edit generated recommendations before exporting them as PDF documents.

The PDF export workflow includes the patient's extracted name and generates a patient-specific filename.

### Multi-patient assessment workspace

NutriCare AI supports grouped fictional patient records.

Users can switch between patients, review their individual evidence, and generate patient-specific assessments.

The retrieval and generation workflows operate on the selected patient's information.

### Responsive user interface

The application provides an interactive browser-based workspace with:

- Patient information and source evidence.
- Nutrition assessment and recommendation panels.
- Interactive AI copilot.
- Review and PDF export controls.
- Evaluation and operational metrics.

The frontend uses HTML, CSS, and vanilla JavaScript.

---

## 3. AI System Architecture

NutriCare AI uses a modular Python backend with FastAPI.

The application separates document processing, retrieval, AI inference, agentic interactions, validation, evaluation, and report generation.

```text
                  NUTRICARE AI

                Browser Interface
                        |
                        v
                   FastAPI Backend
                        |
                        v
               Document Ingestion
                        |
                        v
             Patient Data Extraction
                        |
                        v
              Source-Labeled Chunks
                        |
                        v
               Patient-Scoped RAG
                        |
              +---------+---------+
              |                   |
              v                   v
        Lexical Retrieval    Optional Hybrid
              |             Embedding Reranking
              +---------+---------+
                        |
                        v
                Context Assembly
                        |
                        v
                Cloudflare Workers AI
                        |
               +--------+--------+
               |                 |
               v                 v
       Structured Assessment   AI Copilot
               |                 |
               v                 v
       Output Validation    Proposed Edits
               |                 |
               v                 v
       Care Plan Draft      Human Review
               |                 |
               +--------+--------+
                        |
                        v
                 PDF Generation
```

### Key architectural decisions

**Modular backend**

Document ingestion, retrieval, inference, evaluation, security, and report generation are implemented in separate Python modules.

**Patient-scoped context**

Retrieval operates on the active patient's source passages rather than a shared collection containing every patient's information.

**Structured generation**

Model responses are parsed and validated against expected response structures.

**Constrained agentic actions**

The copilot proposes targeted revisions instead of executing unrestricted modifications.

**Evidence traceability**

The system associates patient-specific findings with source identifiers so users can inspect the supporting document excerpts.

**Lightweight deployment architecture**

The application uses a serverless-compatible FastAPI entry point and remote model inference through Cloudflare Workers AI.

---

## 4. AI Evaluation and Performance Metrics

Evaluation is an important component of NutriCare AI.

The application includes a dedicated Evaluation interface that exposes reproducible retrieval measurements and operational performance information.

The evaluation system distinguishes retrieval quality from generated-answer quality.

### Retrieval evaluation

The application includes a fixed, manually labelled benchmark containing five fictional queries and six source passages.

The benchmark evaluates the actual lexical retrieval implementation against known relevant passage identifiers.

It calculates:

| Metric | Description |
| --- | --- |
| Precision@K | The proportion of retrieved passages that are relevant to the query. |
| Recall@K | The proportion of relevant passages successfully retrieved within the top K results. |
| Mean Reciprocal Rank (MRR) | Measures how highly the first relevant passage is ranked. |

The evaluation endpoint returns aggregate measurements and per-query results, including expected and retrieved passage identifiers.

This makes the benchmark reproducible and allows developers to inspect individual retrieval outcomes.

**Important:** These measurements apply to the fixed lexical retrieval benchmark. They are not clinical accuracy scores or measurements of live LLM-generated answers.

### Operational metrics

NutriCare AI also captures operational measurements for supported API workflows.

| Metric | Purpose |
| --- | --- |
| Request counts | Tracks recorded operations and their success or failure. |
| P50 latency | Measures median processing time. |
| P95 latency | Measures processing time at the 95th percentile. |
| Input tokens | Tracks input token usage reported by the model provider. |
| Output tokens | Tracks output token usage reported by the model provider. |

These metrics help developers investigate response times, model usage, and application behavior.

Operational counters are stored in memory and are local to the running application instance.

In serverless deployments, counters may reset or differ between instances.

### AI answer quality

Answer relevance, factual correctness, semantic groundedness, citation support, and clinical safety require separate evaluation protocols.

NutriCare AI does not currently publish independently validated scores for these outcomes.

The evaluation framework is designed to make these distinctions explicit rather than presenting unsupported accuracy percentages.

For further details, see [EVALUATION.md](EVALUATION.md).

---

## 5. AI Safety and Validation

NutriCare AI implements several application-level controls to reduce avoidable errors and constrain model behavior.

These include:

**Input validation:** File-format checks, upload-size limits, patient-record validation, and bounded user inputs.

**Output validation:** Structured response checks, source-identifier validation, and selected checks for unsupported prescriptions or conflicting recommendations.

**Prompt-injection precautions:** Uploaded documents are treated as evidence rather than trusted instructions. Model instructions explicitly prohibit following instructions embedded in patient records.

**Constrained editing:** Proposed plan revisions must identify a specific existing passage before they can be accepted.

**Human review:** Generated nutrition plans require review before PDF export.

**Server-side API credentials:** Cloudflare credentials are read from backend environment variables rather than embedded in frontend JavaScript.

These mechanisms are limited safeguards, not proof of clinical safety or complete protection against prompt injection.

The public portfolio application is restricted to fictional or synthetic patient records.

---

## 6. Technology Stack

| Category | Technologies |
| --- | --- |
| Programming language | Python |
| Backend | FastAPI, Pydantic |
| AI inference | Cloudflare Workers AI |
| Language model | Configurable Cloudflare-hosted LLM |
| Retrieval | Lexical retrieval, optional embedding reranking |
| API communication | HTTPX, REST APIs |
| Document processing | pypdf, python-docx, openpyxl |
| PDF generation | ReportLab |
| Frontend | HTML, CSS, JavaScript |
| Automated testing | pytest |
| Deployment | Vercel |
| Version control | Git and GitHub |

---

## 7. Project Structure

```text
nutricareAI/
│
├── app.py
├── requirements.txt
├── vercel.json
├── README.md
├── EVALUATION.md
├── .gitignore
│
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── ingestion.py
│   ├── extraction.py
│   ├── retrieval.py
│   ├── rag.py
│   ├── agent.py
│   ├── security.py
│   ├── evaluation.py
│   ├── benchmark.py
│   └── report.py
│
├── public/
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   └── demo-patients.csv
│
└── tests/
    ├── test_core.py
    ├── test_care_plan.py
    ├── test_benchmark_and_pdf.py
    └── test_patient_identity_regression.py
```

### Backend responsibilities

`main.py` contains the application routes and request/response contracts.

`ingestion.py` handles document parsing and patient segmentation.

`extraction.py` organizes extracted patient information.

`retrieval.py` implements patient-scoped retrieval.

`rag.py` handles model inference and structured assessment generation.

`agent.py` implements the interactive copilot and targeted editing workflow.

`security.py` implements input limits and selected application-level safeguards.

`evaluation.py` provides retrieval scoring utilities and operational metrics.

`benchmark.py` contains the reproducible retrieval benchmark.

`report.py` handles PDF generation.

---

## 8. Local Installation and Setup

### Prerequisites

You will need:

- Python 3.11 or later.
- Git.
- A Cloudflare account with access to Workers AI for live AI generation.
- A valid Cloudflare API token.

### Step 1. Clone the repository

```bash
git clone https://github.com/adeosunvictor/nutricareAI.git

cd nutricareAI
```

### Step 2. Create a virtual environment

On Windows:

```powershell
python -m venv .venv

.\.venv\Scripts\Activate.ps1
```

On macOS or Linux:

```bash
python3 -m venv .venv

source .venv/bin/activate
```

### Step 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### Step 4. Configure environment variables

Create a `.env` file in the project root.

Add the following configuration:

```dotenv
CLOUDFLARE_ACCOUNT_ID=your_cloudflare_account_id

CLOUDFLARE_API_TOKEN=your_cloudflare_api_token

CLOUDFLARE_MODEL=@cf/qwen/qwen3-30b-a3b-fp8

RETRIEVAL_MODE=lexical
```

Replace the placeholder values with your own Cloudflare credentials.

The model identifier should correspond to a model available through your Cloudflare account.

For optional embedding-based reranking, configure:

```dotenv
RETRIEVAL_MODE=hybrid
```

The application uses lexical retrieval by default.

**Security:** Never commit your `.env` file or API credentials to GitHub. Keep credentials in local environment variables or your hosting provider's server-side environment configuration.

### Step 5. Run the application

```bash
python -m uvicorn app:app --reload
```

Open:

http://127.0.0.1:8000

You can use the included fictional patient dataset to explore the application.

Live assessment generation and copilot functionality require valid Cloudflare credentials.

---

## 9. API Endpoints

NutriCare AI exposes the following FastAPI endpoints.

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/api/health` | Application health and AI configuration status. |
| POST | `/api/upload` | Document upload and patient data extraction. |
| POST | `/api/assess` | AI-generated nutrition assessment. |
| POST | `/api/chat` | Patient-specific AI copilot interactions. |
| POST | `/api/report` | PDF care-plan generation and export. |
| GET | `/api/metrics` | Operational performance measurements. |
| GET | `/api/evaluation` | Reproducible retrieval evaluation results. |

The assessment and chat endpoints require a configured AI provider.

---

## 10. Running Automated Tests

NutriCare AI includes automated regression tests covering core application functionality.

Install pytest:

```bash
python -m pip install pytest
```

Run the test suite:

```bash
python -m pytest -q
```

The tests cover selected document-ingestion behavior, patient identity extraction, retrieval, response validation, PDF naming, agentic editing constraints, and API contracts.

These tests help detect regressions, but they do not replace live model testing or independent evaluation of generated nutrition recommendations.

---





### Environment variables

Configure the following variables in Vercel:

```text
CLOUDFLARE_ACCOUNT_ID

CLOUDFLARE_API_TOKEN

CLOUDFLARE_MODEL

RETRIEVAL_MODE
```

Your Cloudflare API token must remain a server-side secret.

The repository includes a `vercel.json` configuration specifying a 60-second function duration.

Actual deployment behavior depends on Vercel execution limits, model response time, and available hosting resources.

---

## 12. Current Limitations

NutriCare AI is an applied AI engineering portfolio project and not a clinically validated healthcare system.

Its current limitations include:

- No authentication or verified professional identity.
- No secure, persistent patient-record storage.
- No independently validated clinical accuracy.
- No curated clinical guideline retrieval library.
- No durable, deployment-wide monitoring infrastructure.
- Best-effort in-memory rate limiting rather than distributed abuse protection.



These limitations are documented to distinguish the capabilities currently implemented from future production engineering requirements.

---

## 13. Future Development

Possible extensions include:

**Advanced retrieval evaluation:** A larger labelled fictional dataset for comparing lexical and hybrid retrieval performance.

**LLM evaluation:** Independent measurement of answer relevance, groundedness, factual correctness, citation support, and completeness.

**Agent evaluation:** Measurement of task completion, edit accuracy, tool-selection behavior, and human intervention requirements.

**Observability:** Persistent request tracing, model latency analysis, token usage, and failure monitoring.

**Security:** Stronger authentication, distributed rate limiting, access controls, and privacy-preserving data handling.

**Retrieval infrastructure:** Investigation of persistent vector databases and scalable document indexing where application requirements justify them.

---

## 14. Open Source and Contributions

NutriCare AI is publicly available as an AI engineering portfolio project.

Contributions, bug reports, and suggestions are welcome.

If you would like to contribute:

1. Fork the repository.
2. Create a feature branch.
3. Implement and test your changes.
4. Submit a pull request describing your contribution.



For feedback or feature requests, open a GitHub issue.

---

## License

See the LICENSE file in this repository for the applicable open-source license.

---

## Author

**Victor Adeosun**

AI Engineering | Retrieval-Augmented Generation | Agentic AI | Python Backend Development

[GitHub](https://github.com/adeosunvictor)

Built as an applied AI engineering portfolio project demonstrating the design, implementation, evaluation, and deployment of an end-to-end AI application.
