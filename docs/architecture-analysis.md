# ROC Litigation Verification System: Architecture Analysis

Prepared for Abhishek, 4 October 2026. Answers section 42 ("First Task") of the master prompt.
Status: **proposal, awaiting approval before Phase 1.** No application code has been written yet.

---

## 0. Executive summary

The overall design is sound: a deterministic, explainable, human-in-the-loop pipeline with a pluggable ROC provider is the right shape for this problem. Most of the system (around 85%) can be built and fully tested offline against mock data.

The parts that need to change are concentrated in four places:

1. **MCA access is the biggest unknown, not a solved step.** The "log in once, then let the app run 50 searches" flow depends on (a) MCA's terms allowing automated queries from a logged-in account, and (b) MCA not requiring a CAPTCHA per search. Neither can be assumed. The design should treat automated MCA lookup as an *optional, feature-flagged* mode, and make a **human-assisted lookup mode** the default MCA path, with an **offline bulk-data provider** as a third option.
2. **A headed browser launched by the server opens on the server, not on the lawyer's screen.** This only works while the app runs on the lawyer's own PC. The MCA browser therefore belongs in a small local "MCA agent" process, which keeps the prototype honest and makes a later server deployment possible.
3. **Several rules would produce false "high risk" flags on legitimate cases** (proprietorships that are not in MCA at all, name changes, relocations, predecessor businesses, company status that changed after the events in the case). The rules need gating, softer wording, and a separate **coverage score** so that "we couldn't check" never looks like "low risk".
4. **Celery is not supported on Windows.** A Postgres-backed job queue removes Redis and Celery entirely and is simpler to run and debug.

I also recommend reordering the phases so there is a usable UI and the synthetic test set early, with security and tests running continuously rather than in phases 16 and 17.

---

## 1. Analysis of the proposed architecture

### What is right and should be kept

- Decision support, not verdicts. Language such as "verification mismatch" and "requires human review" throughout.
- Deterministic rule engine first, ML later, with configurable weights.
- `ROCProvider` interface with `MockROCProvider`. This is the single most important design decision in the prompt; it lets everything except one adapter be built offline.
- Field-level provenance (`source`, `value`, `retrieved_at`) for every external fact.
- Cheap extractors first (regex, dateparser), LLM only for hard cases.
- Separating factual mismatch from legal conclusion in the timeline engine.
- No credentials stored, logged, or sent to an LLM.

### What is over-specified for a prototype

- **pdfplumber alongside PyMuPDF.** PyMuPDF already gives text with word-level bounding boxes and is much faster. pdfplumber is only worth adding if we later need table extraction. Recommendation: PyMuPDF only.
- **Celery + Redis.** See section 2.9. A Postgres job table does everything this app needs.
- **Concurrency against MCA.** With one human session there is effectively one browser and one lookup at a time. `MCA_MAX_CONCURRENCY` should default to 1; the bigger win is caching (the same company often appears in many cases).

---

## 2. Technical problems and unrealistic assumptions

Ordered by impact.

### 2.1 MCA terms of use and automated access (blocking for Phase 15 only)

The prompt correctly says "only where permitted", but the whole user experience in section 41 assumes it *is* permitted. Before any automated MCA lookup is built, someone at the company (ideally their own legal team, since they are an IP law firm) needs to read the current MCA portal terms of use and confirm whether automated queries from a logged-in user account are allowed. I have not verified MCA's current terms and the design should not depend on the answer.

Practical risks even if technically possible:

- The account used belongs to a real person (often a lawyer). Automated use that violates terms could get that account suspended.
- Portal layout changes break DOM-based automation without warning, often silently returning wrong data. That is a correctness risk, not just an availability risk.

**Change:** `MCA_AUTOMATION_ENABLED=false` by default. The system is fully useful without it (see 2.2).

### 2.2 "Authenticate once, process the batch" may not hold

The flow assumes the CAPTCHA is only at login. On government portals it is common to have a CAPTCHA on the search form itself, short idle timeouts, or per-session query limits. If MCA puts a CAPTCHA on each company lookup, the batch cannot run unattended, and we must not try to make it.

**Change:** design three MCA lookup modes behind the same provider interface:

| Mode | How it works | Needs |
|---|---|---|
| **Assisted (default)** | App queues lookups. For each unique company, it opens the MCA page in the agent's browser and shows the lawyer "Look up CIN U12345GJ2018PTC123456". The lawyer completes the search (and any CAPTCHA). The app reads the result page that the human brought up, parses it, and saves a snapshot. Then it moves to the next one. | Human present; no automation of the search itself |
| **Automated (optional)** | After human login, the app performs searches itself within the session, at low rate, pausing for re-auth or whenever a CAPTCHA appears. | Legal sign-off; no per-search CAPTCHA |
| **Manual entry (fallback)** | Lawyer pastes or types the master-data fields (or uploads an MCA printout PDF) into a form. Marked `source = MCA (manually entered by <user>)`. | Nothing |

Assisted mode still delivers most of the value: the lawyer does one click-and-CAPTCHA per unique company, and the app does all extraction, comparison, scoring, and reporting. Deduplication matters here: 50 cases often involve 15 unique companies.

### 2.3 Where the browser runs

Playwright with a headed browser opens a window **on the machine running the Python process**. For a prototype running on Abhishek's or a lawyer's PC, that is fine. If the backend is later deployed to a server, the lawyer would never see the login window.

**Change:** isolate all browser code into a separate **MCA agent** process (same repo, `backend/app/mca_agent/`). It talks to the backend through the job table / a small internal API, never through the frontend. For the prototype it runs on the same PC. For deployment it becomes a small app the lawyer runs on their own machine, which polls the server for lookup jobs. This keeps session cookies on the lawyer's machine and off the server entirely, which is also the safest place for them.

### 2.4 Session storage

A Playwright *persistent* context writes cookies and local storage to a profile directory on disk indefinitely. For an authenticated government session that is more than we need.

**Change:** use an ephemeral browser context held in memory by the agent for the session's lifetime, with a temporary profile directory deleted on disconnect, app exit, or expiry. Only session *status* (connected / expired / disconnected, timestamps, which app user) goes into the database. No cookies, tokens, or HTML containing credentials are stored, logged, or returned by any API.

"Detecting authenticated state" must be based on a positive, narrow signal (for example, a logged-in-only element is present on a known page), with the detector selectors in config so they can be updated without code changes.

### 2.5 "Company does not exist" is not a safe inference

- A failed search is not evidence of non-existence. Name search is fuzzy and spelling-sensitive, and the portal may simply be failing.
- Many trademark litigants in India are **sole proprietorships and partnership firms**, which are not registered with MCA at all. Absence from MCA is expected for them.
- LLPs (LLPIN), foreign companies (FCRN), and societies/trusts have different identifiers or registries.

**Change:** split RULE-001 into:

- `CIN_NOT_FOUND`: document gives a structurally valid CIN and MCA returns no company for it. Strong signal. (+40)
- `NAME_NOT_FOUND`: no CIN given, name search returns nothing close. Weak signal, and only fires if the document itself describes the entity as a company ("Private Limited", "Limited", "incorporated under the Companies Act"). (+15, configurable)
- `NOT_MCA_ENTITY`: entity is described as a proprietorship/partnership/trust. No score; shown as "not verifiable against ROC".

### 2.6 Current ROC data vs historical claims

MCA master data shows the company **as it is today**: current name, current registered office, current status. Litigation documents often describe the company at an earlier date.

- **Name changes** are common. A mismatch against the current name may be a legitimate former name.
- **Registered office changes** (relocation, even between states) are common. The CIN changes when the state changes, but the incorporation year and serial in the CIN persist.
- **Status**: a company struck off in 2024 may have been perfectly active during the 2019 events in the case. "Struck off" is only a strong signal if the document presents the company as currently active, or the claimed activity is after the strike-off date (which master data may not give).

**Change:** every rule has a `requires_human_context` note in its explanation, and the explanation text says what the possible innocent explanations are ("may reflect a change of registered office; check MCA filing history"). RULE-005 is reworded to "Company status is not Active" with sub-weights per status.

### 2.7 Timeline rules and business succession

"Operating since 2015" for a company incorporated in 2018 is very often a predecessor proprietorship or partnership that was converted into a company, or a business acquired with its goodwill. Trademark use by a predecessor-in-title is legally relevant use. The prompt already handles RULE-008 carefully; RULE-007 needs the same treatment.

**Change:** both rules produce `POTENTIAL_TIMELINE_INCONSISTENCY` with an explanation that lists predecessor business / assignment / conversion as possible explanations. The extractor also looks for succession language ("formerly known as", "predecessor", "converted from", "assignment deed") and, if found, lowers the rule weight and attaches the evidence.

Date granularity matters too: "since 2018" vs incorporation on 2018-08-14 is a `partial_match` (same year), not a mismatch. All dates carry a granularity (`day`, `month`, `year`).

### 2.8 The score needs a coverage companion

An additive score with "unavailable" contributing 0 means a case where MCA could not be reached scores **LOW RISK**. That is exactly the misreading the prompt is trying to avoid.

**Change:** every assessment stores two numbers:

- **Risk score (0–100):** sum of fired rule weights, capped at 100, with rule gating (e.g. if `CIN_NOT_FOUND` fires, address/date rules don't run because there's nothing to compare).
- **Verification coverage (0–100%):** share of applicable checks that could actually run.

The UI and report show a level only when coverage is above a configurable threshold (default 60%); otherwise the level is **"INCOMPLETE: verification unavailable"**. The rule set is versioned so a score can always be reproduced and explained later, even after weights change.

### 2.9 Celery on Windows

Celery dropped official Windows support years ago; it needs workarounds (`--pool=solo`) and Redis needs Docker or WSL. That's a lot of moving parts for a queue that processes tens of documents.

**Change:** a `jobs` table in Postgres, claimed with `SELECT ... FOR UPDATE SKIP LOCKED`, and a plain Python worker process (`python -m app.workers.run`). Benefits: no Redis, one fewer service, job state is queryable with SQL and visible in the dashboard, retries and backoff are simple columns. If the system ever needs real scale, swapping to a broker later is contained inside `app/workers/`.

### 2.10 Extraction realism

- **spaCy's general English models** do not know Indian legal structure. Company names are better found with suffix patterns ("Private Limited", "Pvt. Ltd.", "LLP", "Limited") plus parsing the cause-title block ("... Plaintiff / VERSUS / ... Defendant"). spaCy is still useful for sentence segmentation and the dependency parse that links a date to its claim. An Indian-legal NER model (OpenNyAI's InLegalNER) may be worth evaluating in Phase 6, but should not be a dependency.
- **CIN is a goldmine for offline checks.** A CIN is 21 characters: listing status (L/U) + 5-digit industry code + 2-letter state + 4-digit incorporation year + 3-letter company type (PTC, PLC, ...) + 6-digit number. Without touching MCA we can check that the document's own claims agree with its CIN: incorporation year, state, private vs public, listed vs unlisted. This gives real value in mock-free offline mode. Note there is no checksum, so "invalid CIN" can only mean structurally invalid.
- **Multiple companies** (test case 10): verify every corporate party, and mark which one is the "subject" (the counter-party, by default) based on cause-title roles. The lawyer can change the subject in the UI.

### 2.11 OCR on Windows and on real documents

- Tesseract is a separate Windows installer (the UB Mannheim build) plus a PATH entry. Doable; I'll give exact steps in Phase 5.
- Court filings include stamp paper, seals, signatures, and sometimes Hindi or regional-language text. Tesseract's `hin` data can be added; OCR confidence per word is stored so low-confidence extractions are flagged for review rather than trusted.
- Mixed PDFs (some pages text, some scanned) are common. Detection is per page, not per document.

### 2.12 Confidentiality and the optional LLM

Litigation documents are client-confidential. Sending them to any hosted LLM is a client-data decision, not just a technical one.

**Change:** LLM disabled by default (`LLM_ENABLED=false`), behind an interface, used only for (a) claim extraction from sentences the rules couldn't resolve and (b) explanation phrasing. It never receives ROC data to "fill in" and never produces facts that bypass the comparison engine. When enabled, only the relevant sentences are sent, not the whole document.

### 2.13 Phase order

Frontend at Phase 12 means eleven phases with no visible product. Security at 16 and testing at 17 means retrofitting both. See section 9 for a reordered plan.

### 2.14 Smaller points

- Store an **evidence snapshot** for each ROC lookup (rendered page saved as PDF/HTML, with SHA-256) so a reviewer can see exactly what MCA showed at the time.
- **Cache** ROC lookups by CIN with a configurable TTL (default 7 days), so repeated companies in a batch hit MCA once.
- Uploaded PDFs: validate magic bytes (not just extension), cap size and page count, open with PyMuPDF in the worker (not the API process), and serve them back with `Content-Disposition` and a strict CSP. Never render PDF content as HTML.
- App auth via **httpOnly, SameSite cookie sessions + CSRF token** rather than JWT in localStorage (the prompt forbids sensitive data in local storage, and this is the simplest way to comply).

---

## 3. What depends on MCA/ROC access

Only these pieces need live MCA:

- `MCAROCProvider` (assisted and automated modes): navigating, reading the result page, parsing master data into the normalized ROC schema.
- The MCA agent process: browser lifecycle, auth-state detection, session expiry detection, rate limiting and backoff.
- The "Connect to MCA" panel's live behaviour.
- Calibrating the parser against real MCA field labels and status values.
- Real-world tuning of rule weights (needs real cases).

**Things I need from you before Phase 15 (not before Phase 1):** confirmation of what the MCA terms permit, a test account you are allowed to use, and a few saved MCA result pages (save-as HTML or printouts) for companies whose data isn't sensitive, so the parser can be built against fixtures and tested offline.

---

## 4. What can be built completely offline

Everything else:

- Project setup, database, migrations, app user auth and roles
- Upload, case IDs, file validation, storage
- Text extraction, OCR, bounding boxes, document viewer with highlights
- Entity and claim extraction, CIN structural checks, date-claim linking
- Normalization (names, addresses, states, PIN codes, dates)
- `ROCProvider` interface, `MockROCProvider`, `ManualEntryROCProvider`, caching
- Verification, timeline, and risk engines, coverage score, rule config
- Job queue, batch progress, pause/resume semantics (tested with a mock provider that simulates "session expired")
- Human review, audit log
- PDF/Excel/CSV reports and exports
- Full frontend
- Synthetic dataset (all 10+ cases, including scanned ones) and the full integration test suite
- Even the MCA agent's queue/pause/resume logic, using a fake browser driver

A further offline option worth having: **`BulkDatasetROCProvider`**, which imports a CSV of company master data. The Government of India has historically published state-wise company master data on data.gov.in; if a current dataset is available and its licence allows this use, it gives legitimate, automation-free verification of existence, CIN, incorporation date, status, and address for a large set of companies. I'd confirm availability and freshness before relying on it.

---

## 5. Proposed technology architecture

### 5.1 Components

```
┌──────────────────────┐        ┌────────────────────────────────────┐
│ React SPA (Vite)     │ HTTPS  │ FastAPI app (API process)          │
│ TS + Tailwind        │◄──────►│  auth, cases, review, reports,     │
│ TanStack Query       │ cookie │  rules config, MCA session status  │
└──────────────────────┘ session└──────────────┬─────────────────────┘
                                               │ SQLAlchemy
                                      ┌────────▼────────┐
                                      │ PostgreSQL      │
                                      │ data + job queue│
                                      └───┬─────────┬───┘
                     claims jobs (SKIP    │         │  claims MCA lookup jobs
                     LOCKED)              │         │
                     ┌────────────────────▼──┐  ┌───▼─────────────────────┐
                     │ Worker process        │  │ MCA agent process       │
                     │ extract, OCR, verify, │  │ Playwright, headed,     │
                     │ score, report         │  │ ephemeral context,      │
                     │ (uses ROCProvider)    │  │ rate-limited, local     │
                     └───────────────────────┘  │ to the lawyer's PC      │
                                                └─────────────────────────┘
        File storage: ./data/uploads, ./data/evidence, ./data/reports (local disk for prototype)
```

Three Python processes from one codebase, plus Postgres and the frontend dev server. No Redis.

### 5.2 Stack (final)

| Layer | Choice | Why |
|---|---|---|
| API | **FastAPI** + Pydantic v2 | Typed request/response models, auto-generated docs at `/docs` |
| DB | **PostgreSQL 16** + SQLAlchemy 2.0 + **Alembic** migrations | Alembic versions the schema the way Git versions code |
| Queue | Postgres `jobs` table + worker process | No Redis/Celery; works natively on Windows |
| PDF | **PyMuPDF** | Text, word boxes, page rendering for OCR |
| OCR | **Tesseract** via pytesseract (eng, optional hin) | Free, local, gives word boxes and confidence |
| NLP | Regex + **dateparser** + **spaCy** (`en_core_web_sm`) | Rules first; spaCy for sentences and date-claim linking |
| Matching | **RapidFuzz** | Fast fuzzy string similarity |
| Browser | **Playwright** (Python), MCA agent only | Drives a real browser the human logs into |
| Reports | **ReportLab** (PDF), **openpyxl** (Excel), csv | As specified |
| Frontend | **React 18 + TypeScript + Vite + Tailwind**, TanStack Query, React Router, react-pdf | Vite is the fast dev server/bundler; TanStack Query handles fetching and polling |
| Tests | pytest, httpx test client, Vitest, Playwright (UI e2e later) | |
| Quality | ruff (lint+format), mypy (optional), ESLint, Prettier, pre-commit | |

### 5.3 Running it on Windows 11

- Python 3.12 in a venv, Node 20 LTS, Git.
- Postgres via **Docker Desktop** (`docker compose up -d db`) is the least fiddly; a native Postgres installer also works. The app itself runs natively for fast iteration; full Docker for all services comes in the deployment phase.
- Tesseract via the Windows installer (Phase 5).
- I'll give PowerShell commands throughout.

### 5.4 Provider interface

```python
class ROCProvider(Protocol):
    name: str
    async def lookup_by_cin(self, cin: str) -> ROCLookupResult: ...
    async def search_by_name(self, name: str) -> list[ROCCandidate]: ...

# ROCLookupResult.status: FOUND | NOT_FOUND | UNAVAILABLE | NEEDS_HUMAN
# Each field: {value, source, retrieved_at, retrieved_by, evidence_id}
```

Implementations: `MockROCProvider` (JSON fixtures, can simulate latency, outages, session expiry), `ManualEntryROCProvider`, `BulkDatasetROCProvider` (optional), `MCAROCProvider` (assisted/automated via the agent). A `CachingROCProvider` wraps any of them. Selected by `ROC_PROVIDER=mock|manual|bulk|mca`.

---

## 6. Proposed database schema

All tables have `id` (UUID), `created_at`, `updated_at` unless noted. Human-readable case IDs (`CASE-0001`) come from a Postgres sequence.

**Identity and audit**

- `users`: email, full_name, password_hash (argon2), role (`admin` | `analyst` | `reviewer`), is_active, last_login_at
- `audit_logs` (append-only; no updates/deletes granted): actor_user_id, action, entity_type, entity_id, details (JSONB, scrubbed of secrets), ip, created_at

**Intake**

- `batches`: name, created_by, status, total_cases, completed_cases
- `cases`: case_code (`CASE-0001`), batch_id, status (enum below), subject_entity_id, current_assessment_id, review_status, assigned_reviewer_id
- `documents`: case_id, original_filename, stored_path, sha256, mime_type, size_bytes, page_count, uploaded_by
- `document_pages`: document_id, page_no, extraction_method (`text` | `ocr`), text, ocr_mean_confidence, words (JSONB: text, bbox, conf)

Case status: `queued → extracting → extracted → awaiting_mca → verifying → scoring → requires_review → reviewed`, plus `failed`. (The prompt's `comparing` is folded into `verifying`; `completed` becomes `reviewed`, since a case isn't done until a human has looked at it if it was flagged. Low-risk, high-coverage cases can be auto-marked `completed_no_flags`.)

**Extraction**

- `extracted_entities`: case_id, entity_kind (`company` | `llp` | `firm` | `person` | `court`), role (`plaintiff` | `defendant` | `petitioner` | `respondent` | `other`), raw_name, normalized_name, cin, is_subject, source_spans (JSONB: page, bbox, text)
- `extracted_claims`: case_id, entity_id, claim_type (`incorporation_date`, `company_operation`, `trademark_use`, `registered_address`, `company_status`, `company_type`, `trademark_number`, `case_number`, `filing_date`, ...), raw_text, value_text, value_date, date_granularity, normalized_value (JSONB), extractor (`regex` | `dateparser` | `spacy` | `llm` | `manual`), confidence, source_span (JSONB)

**ROC**

- `roc_lookups`: entity_id, provider, mode (`mock` | `manual` | `bulk` | `mca_assisted` | `mca_automated`), query_type, query_value, status (`found` | `not_found` | `unavailable` | `needs_human`), retrieved_at, retrieved_by, evidence_path, evidence_sha256, error
- `roc_company_records`: lookup_id, cin, company_name, status, company_type, category, sub_category, incorporation_date, registered_address, state, pin, roc_office, directors (JSONB), raw (JSONB), cached_until
- `mca_sessions`: started_by, status (`connecting` | `connected` | `expired` | `disconnected`), connected_at, last_activity_at, ended_at, agent_host. **No cookies, tokens, usernames, or passwords.**

**Verification and risk**

- `field_comparisons`: case_id, entity_id, field, document_value, roc_value, method (`exact` | `normalized` | `fuzzy` | `cin_structure` | `date`), similarity, result (`match` | `close_match` | `partial_match` | `mismatch` | `unavailable` | `not_applicable`), claim_id, roc_record_id
- `timeline_events`: case_id, entity_id, event_type, date, granularity, source (`document` | `roc`), claim_id / roc_record_id
- `risk_rule_sets`: version, is_active, thresholds (JSONB: level bands, min coverage), created_by
- `risk_rules`: rule_set_id, code (`RULE-001`...), name, description, weight, enabled, params (JSONB), explanation_template, innocent_explanations
- `risk_assessments`: case_id, rule_set_id, score, level, coverage, computed_at, inputs_hash
- `risk_flags`: assessment_id, rule_id, weight_applied, title, explanation, evidence (JSONB: comparison ids, spans, ROC fields), category (`factual_mismatch` | `potential_timeline_inconsistency` | `internal_inconsistency`)

**Review, outputs, jobs**

- `flag_reviews`: flag_id, reviewer_id, decision (`confirmed` | `false_positive` | `needs_investigation` | `unable_to_verify`), note
- `case_reviews`: case_id, reviewer_id, overall_decision, summary_note, completed_at
- `reports`: case_id (or batch_id), format (`pdf` | `xlsx` | `csv`), path, generated_by, generated_at, assessment_id
- `jobs`: type (`extract` | `verify` | `mca_lookup` | `score` | `report`), payload (JSONB), status (`pending` | `running` | `done` | `failed` | `paused`), attempts, max_attempts, run_after, locked_by, locked_at, last_error

The `flag_reviews` table, joined to `field_comparisons` and `risk_flags`, is exactly the labelled dataset the future ML phase needs (section 33 of the prompt), so no extra design is required for it now.

---

## 7. Proposed API architecture

All under `/api/v1`. JSON in and out. Cookie session auth; CSRF token header on state-changing requests. Long work always returns `202 Accepted` with a job or batch reference; the UI polls (every 2 s while a batch is active). Server-Sent Events can replace polling later if needed.

**Auth**
- `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`

**Batches and cases**
- `POST /batches` (multipart, many files) → creates batch + one case per file, queues extraction
- `GET /batches`, `GET /batches/{id}` (progress counts)
- `POST /batches/{id}/verify` → queues verification for all cases ready for it
- `GET /cases?status=&risk_level=&review_status=&q=&page=` (list, filters, search)
- `GET /cases/{case_code}` (summary, entities, claims, comparisons, assessment, flags)
- `PATCH /cases/{case_code}` (set subject entity, assign reviewer)
- `POST /cases/{case_code}/reprocess` (re-run a stage)
- `GET /cases/{case_code}/document` (streams the PDF), `GET /cases/{case_code}/pages/{n}` (text + word boxes)
- `PUT /cases/{case_code}/claims/{id}` (analyst corrects an extraction; audited)

**ROC / MCA**
- `GET /mca/session` (status only), `POST /mca/session/connect`, `POST /mca/session/disconnect`
- `GET /mca/lookups/pending` (the assisted-mode queue the lawyer works through)
- `POST /roc/manual-entry/{entity_id}` (manual fallback)
- `GET /roc/lookups/{id}/evidence` (snapshot file)

**Review**
- `POST /cases/{case_code}/flags/{flag_id}/review`
- `POST /cases/{case_code}/review` (overall decision + note)

**Reports and exports**
- `POST /cases/{case_code}/reports` (format) → job; `GET /reports/{id}` (download)
- `GET /exports/cases.xlsx?filters…`, `GET /exports/cases.csv?filters…`

**Admin and dashboard**
- `GET /dashboard/summary` (counts by status, level, review state)
- `GET /rules`, `POST /rules/sets` (new version), `POST /rules/sets/{id}/activate`
- `GET /audit-logs` (admin)
- `GET /health`

Changes from the prompt's list: batch-first upload (single file is just a batch of one), verification triggered per batch, and separate endpoints for MCA session status vs ROC lookups so session state never travels with data.

---

## 8. Proposed frontend architecture

**Stack:** Vite + React + TypeScript + Tailwind, React Router, TanStack Query (server state and polling), react-pdf (pdf.js) for the viewer with highlight overlays, a small in-house component set (Tailwind + Headless UI primitives) for tables, badges, dialogs. No auth tokens in local storage: the browser holds an httpOnly cookie the JS cannot read.

**Structure**

```
frontend/src/
  app/            router, layout shell, providers, auth guard
  api/            typed client (fetch wrapper with CSRF), endpoint modules
  types/          shared TS types mirroring API schemas
  components/     ui primitives (Button, Badge, Table, Dialog, Tabs, EmptyState)
                  RiskBadge, CoverageMeter, StatusPill, ProgressBar
  features/
    dashboard/    KPI cards, risk distribution, recent cases
    batches/      UploadDropzone, BatchProgress
    cases/        CasesTable (filters, search, sort), CaseHeader
    case-detail/  DocumentViewer (highlights), ExtractedPanel,
                  ComparisonView (document vs ROC side by side),
                  TimelineView, RiskBreakdown (flags + weights + why)
    review/       FlagReviewControls, ReviewNotes, ReviewQueue
    mca/          McaConnectionBadge (always in header),
                  McaPanel (connect/disconnect, assisted lookup queue)
    reports/      ReportActions, ExportDialog
    admin/        RulesEditor, UsersList, AuditLog
  hooks/          useCase, useBatchProgress, useMcaSession
```

**Key screens**

1. **Dashboard:** totals, pending, by risk level, requires review, coverage warnings; click-through to filtered case list.
2. **Upload:** drag-and-drop many PDFs, per-file validation, then live batch progress ("17 / 25 extracted").
3. **Cases:** table with case code, subject company, CIN, status, risk badge, coverage, review status; filters and search.
4. **Case detail:** split screen. Left: PDF with highlighted source spans (click a field to jump to where it came from). Right: tabs for Comparison (side-by-side table with ⚠ badges), Timeline (document vs ROC events on one axis), Risk (score, coverage, each flag with weight and explanation), Review.
5. **MCA panel:** connection status, connect button, and in assisted mode a "next lookup" card that walks the lawyer through each unique company.
6. **Rules (admin):** edit weights and thresholds as a new versioned rule set.

---

## 9. Proposed development phases

Each phase ends with something runnable, its tests passing, and Windows run instructions. Security practices (validation, no secrets in code, audit logging) and tests are written in every phase; phases 16–17 become a hardening review and an end-to-end evaluation rather than first contact.

| # | Phase | Runnable result at the end |
|---|---|---|
| 1 | **Project setup** | Repo skeleton, FastAPI `/health`, Vite app shell, Postgres in Docker, `.env.example`, ruff/pytest/pre-commit, README with Windows steps |
| 2 | **Database + app auth** | SQLAlchemy models, Alembic migration, seed admin user, login/logout with cookie session + CSRF, audit log |
| 3 | **Upload + cases (thin UI)** | Batch drag-and-drop upload, file validation, case codes, case list page |
| 4 | **Text extraction + synthetic dataset v1** | PyMuPDF per-page text and word boxes; generator script for the 10 synthetic litigation PDFs; document viewer |
| 5 | **OCR** | Per-page scanned detection, Tesseract with boxes and confidence; scanned variants added to the dataset |
| 6 | **Entity and claim extraction** | Cause-title parsing, company/CIN/date/address/trademark extraction, date-claim linking, CIN structural checks; extracted panel with source highlights |
| 7 | **Normalization** | Name, address, state, PIN, date normalization with unit tests |
| 8 | **ROC provider layer** | `ROCProvider`, Mock, Manual entry, caching; mock fixtures matching the dataset |
| 9 | **Verification + timeline engines** | Field comparisons, timeline events, comparison and timeline views |
| 10 | **Risk engine + explanations** | Versioned rule sets in DB, gating, coverage score, risk tab, rules editor |
| 11 | **Job queue + batch processing** | Postgres job queue, worker, retries/backoff, pause/resume, live progress |
| 12 | **Dashboard + UI polish** | Full dashboard, filters, search, enterprise styling |
| 13 | **Human review** | Flag decisions, notes, review queue, audit |
| 14 | **Reports + exports** | PDF report (with disclaimer), Excel, CSV |
| 15 | **MCA agent** (after terms are confirmed) | Agent process, connect panel, assisted mode; automated mode behind flag only if permitted; parser tested on saved fixtures |
| 16 | **Security hardening review** | Threat-model checklist, headers/CSP, rate limits, dependency audit, upload fuzzing |
| 17 | **End-to-end evaluation** | Full workflow tests, extraction accuracy on the synthetic set, UI e2e |
| 18 | **Deployment** | Docker Compose for all services, HTTPS reverse proxy, backup notes, agent packaging |

Main differences from the original order: UI starts in Phase 3 and grows each phase; the synthetic dataset arrives in Phase 4 so extraction is developed against it; job queue comes after the engines are proven synchronously; reports move after review so they can include review decisions.

---

## 10. Summary of recommended changes

| # | Change | Reason |
|---|---|---|
| 1 | MCA automation off by default; **assisted lookup** as the default MCA mode; manual entry fallback | Terms and per-search CAPTCHA are unknowns; design must work without automation |
| 2 | Separate **MCA agent** process on the lawyer's machine | A server-launched headed browser is invisible to remote users; keeps session cookies off the server |
| 3 | Ephemeral browser context, nothing session-related persisted except status | Least sensitive data at rest |
| 4 | Split "company does not exist" into CIN-not-found / name-not-found / not-an-MCA-entity | Proprietorships and partnerships are not in MCA; failed search ≠ non-existence |
| 5 | Treat ROC data as current-state; add innocent explanations to every flag | Name changes, relocations, later strike-offs are common |
| 6 | Timeline rules detect succession language; date granularity aware | Predecessor businesses and year-only claims |
| 7 | **Coverage score** alongside risk score; "INCOMPLETE" level when coverage is low | Unavailable checks must not look like low risk |
| 8 | Versioned rule sets in the DB | Reproducible, auditable scores after weights change |
| 9 | Postgres job queue instead of Celery + Redis | Celery unsupported on Windows; fewer services |
| 10 | PyMuPDF only (drop pdfplumber initially) | One library covers text and boxes |
| 11 | Offline CIN structural cross-checks | Real signal without any MCA access |
| 12 | Evidence snapshots + ROC lookup cache | Defensible reports; fewer MCA requests |
| 13 | LLM disabled by default, sentence-level only when enabled | Client confidentiality |
| 14 | Cookie sessions + CSRF instead of tokens in local storage | Matches the security requirements simply |
| 15 | Reordered phases; security and tests continuous | Visible progress early; no retrofit |

---

## 11. Decisions needed from you

1. **Approve this architecture** (or tell me which parts to change).
2. **Postgres job queue instead of Celery + Redis.** Recommended: yes.
3. **Where the code lives.** Recommended: I create a private GitHub repo under your account and push each phase there, so you `git pull` on Windows instead of copying files from chat. Alternatively I can work in a folder on your PC.
4. **MCA terms check** (needed only before Phase 15): can someone confirm what the MCA portal terms allow for automated lookups from a logged-in account?

Nothing beyond this document has been built yet.
