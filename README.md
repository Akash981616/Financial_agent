# Financial Reconciliation Multi-Agent System (LangGraph + Python)

An enterprise-grade, event-driven financial reconciliation agent built with **LangGraph**, **FastAPI**, **Pydantic v2**, and **Docling** principles. The system reconciles third-party financial audit reports (Excel) against vendor invoices, credit card statements, and receipts stored in Google Drive (PDFs and images) to pinpoint missing bills, calculation errors, duplicate submissions, and unbilled expenses.

---

## 1. Industry Standard Frameworks in Python

When building stateful, event-driven multi-agent AI systems in production Python environments, the industry standard stack consists of:

| Framework | Role in Industry | Why It Is Used Here |
|---|---|---|
| **LangGraph** (`langgraph` >= 0.2) | Stateful Multi-Agent Orchestration | Provides cyclic graphs (`StateGraph`), persistent checkpointing (`MemorySaver` / `PostgresSaver`), fine-grained state schemas (`TypedDict`), conditional branching, and native human-in-the-loop interrupts (`interrupt()`). |
| **FastAPI** | High-Performance API & Streaming | The industry de facto standard for deploying AI agent backends. Powers Server-Sent Events (SSE) via `StreamingResponse` so web dashboards receive live execution events. |
| **Pydantic v2** | Strict Typing & Financial Validation | Enforces rigid data models (`CanonicalRecord`, `AuditEntry`, `ReconciliationMatch`, `ReconciliationEvent`) preventing schema drift and hallucinated fields. |
| **Docling** | High-Fidelity Table Extraction | Solves table structure loss in PDFs by exporting complex tabular invoices into structured DataFrames/Markdown rather than flattening them with basic OCR. |

---

## 2. Event-Driven Architecture

The pipeline emits structured lifecycle events at every stage of execution:

```
[1_Ingestion]           ──► INGESTION_STARTED / FILE_INGESTED / DUPLICATE_FILE_DETECTED
[2_DataExtraction]      ──► EXTRACTION_ROUTED / RECORD_EXTRACTED (Docling/OCR/Sheet)
[3_ValidationAndDedup]  ──► CANONICAL_LINK_ESTABLISHED / DUPLICATE_INVOICE_FLAGGED
[4_DeterministicMatcher]──► DETERMINISTIC_MATCH_FOUND (Exact ID & Amount)
[5_LLMReconciliation]   ──► LLM_EVALUATING_ENTRY / LLM_MATCH_ACCEPTED / DISCREPANCY_MISSING_BILL
[6_DecisionValidation]  ──► HUMAN_REVIEW_QUEUED (Arithmetic/Confidence check)
[7_HumanReview]         ──► HUMAN_REVIEW_STARTED / HUMAN_REVIEW_RESOLVED
[8_ReportGenerator]     ──► REPORT_GENERATED / F1_METRICS_EVALUATED
```

Events are dispatched via:
1. **LangGraph Custom Events:** Integrated with `dispatch_custom_event` for LangGraph streaming.
2. **Server-Sent Events (SSE):** Streamed over HTTP (`GET /api/reconcile/stream`) in real time.
3. **Rich Console Streamer:** Beautiful color-coded terminal alerts during execution.

---

## 3. Core Architectural Highlights

### A. 3-Layer Deduplication Strategy
1. **Layer 1 (File Level):** SHA-256 cryptographic content hashing at ingestion. Identical re-uploaded files are immediately tagged, reusing cached extractions.
2. **Layer 2 (Invoice / Transaction Level):** Multi-field comparison `(Normalized Vendor + Invoice Number + Normalized Amount + Currency)`.
3. **Canonical Expense Linking:** A credit card statement line item and a standalone vendor invoice are **not** treated as duplicate expenses; the system links both to a single canonical expense record.

### B. Controlled Workflow vs. Naive Multi-Agent
Rather than allowing an LLM to freely route every step (which introduces latency, hallucinations, and high cost), the orchestrator follows a controlled pattern:
- **Deterministic Code Boundaries:** Exact invoice IDs, amounts, dates, and mathematical checks are handled 100% deterministically with zero LLM hallucination risk.
- **LLM Reasoning Agent:** Reserved strictly for ambiguous cases (prior-month credit card charges, fuzzy vendor names, VAT/sales tax discrepancies).

### C. Persistent Skill Store & Iterative Learning Loop
Recurring edge cases and resolutions are codified in a versioned skill file (`data/skill_file.json`):
- `RULE_001_PRIOR_MONTH_STATEMENT`: Expands date window to 35 days for credit card statement entries.
- `RULE_002_TRANSFER_VS_EXPENSE`: Prevents misclassifying SaaS subscriptions (e.g. AWS, GitHub) as internal bank transfers.
- `RULE_003_TAX_INCLUSION`: Reconciles invoices showing subtotal + VAT against audit reports listing total amount.
- `RULE_004_CANONICAL_LINKING`: Merges dual-source records into a single financial transaction.

### D. F1 Evaluation Benchmark Framework
Rather than relying on vague overall accuracy, performance is measured across 4 independent stages:
- **OCR / Table Extraction F1:** Evaluates table cell and field extraction fidelity.
- **Transaction Classification F1:** Evaluates expense vs transfer classification precision/recall.
- **Bill-to-Audit Matching F1:** Measures correct entry pair linking.
- **Anomaly Detection F1:** Evaluates precision and recall in flagging missing bills and discrepancies.

---

## 4. Project Structure

```
D:\financial-reconciliation-agent\
├── .venv/                      # Python virtual environment
├── requirements.txt            # Project dependencies
├── server.py                   # FastAPI production server with SSE streaming
├── main.py                     # Interactive CLI runner with live event streaming
├── README.md                   # Complete architectural documentation
├── data/
│   ├── sample_data.py          # Realistic test dataset matching Perplexity scenario
│   └── skill_file.json         # Versioned domain rules and vendor aliases
└── src/
    ├── __init__.py
    ├── models.py               # Pydantic schemas (Records, Matches, Events)
    ├── events.py               # Event dispatcher & LangGraph custom event hooks
    ├── skill_store.py          # Persistent domain rules manager
    ├── graph.py                # LangGraph StateGraph & conditional routing
    ├── eval_metrics.py         # Precision, Recall, F1 evaluation engine
    └── nodes/
        ├── ingestion.py        # Layer 1 SHA-256 deduplication
        ├── extraction.py       # Docling table parsing & OCR routing
        ├── validation_dedup.py # Field normalization & canonical linking
        ├── deterministic_matcher.py # Zero-hallucination exact matches
        ├── llm_reconciliation.py    # Ambiguous reasoning & skill application
        ├── decision_validator.py    # Math constraint checks & human review routing
        ├── human_review.py     # Human-in-the-loop review resolution
        └── report_generator.py # Executive report & metrics generator
```

---

## 5. Quick Start & Execution

### 1. Run the Interactive CLI Demo (Live Event Streaming)
```powershell
cd D:\financial-reconciliation-agent
.\.venv\Scripts\python.exe main.py
```
This executes the full LangGraph graph, streaming every event with colored stage badges, ledger tables, anomaly breakdowns, and the F1 evaluation report.

### 2. Start the FastAPI Production Server (with SSE)
```powershell
cd D:\financial-reconciliation-agent
.\.venv\Scripts\python.exe server.py
```
- **API Documentation:** `http://localhost:8000/docs`
- **Live Event Stream:** `GET http://localhost:8000/api/reconcile/stream` (Connect via EventSource or curl)
- **Synchronous Execution:** `POST http://localhost:8000/api/reconcile/run`
- **Resolve Review Case:** `POST http://localhost:8000/api/review/resolve`
- **View / Update Skill File:** `GET /api/skill-file`
