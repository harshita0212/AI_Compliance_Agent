# AI Compliance Agent

An AI-powered legal-review system that automates marketing-compliance checking. Given a campaign - its content, the channel it will be sent on, and the audience it targets - the system checks it against Indian advertising regulations, data-privacy law, and customer-consent records, then returns a structured verdict (**APPROVED**, **FLAGGED**, or **REJECTED**) with the exact legal citation behind every decision.

The system acts as an automated legal gatekeeper: it reads the content, validates that the targeted audience has consented, matches every claim against a versioned rule corpus, and produces an auditable compliance report - reducing a review that traditionally takes three to five days to a verdict in seconds.

> **Status:** Feature-complete prototype. Gemini reasoning runs live alongside a deterministic keyword matcher; the rule corpus (`2026.06.1`) is a curated starter set pending verification against source regulations (see [Current limitations](#current-limitations)).

---

## Table of contents

- [Key features](#key-features)
- [Architecture](#architecture)
- [Technology stack](#technology-stack)
- [Project structure](#project-structure)
- [Getting started](#getting-started)
- [How it works](#how-it-works)
- [The rule corpus](#the-rule-corpus)
- [API reference](#api-reference)
- [Current limitations](#current-limitations)
- [Roadmap](#roadmap)

---

## Key features

- **Context-aware AI reasoning** - Google Gemini reads each campaign against the rule corpus and judges meaning, catching implied claims (e.g. "no rival can match") that literal keyword matching would miss.
- **Dual-detector design** - Gemini runs alongside a fast keyword matcher and the results are merged, so the system catches both literal and contextual violations and degrades gracefully to keyword-only if Gemini is unavailable.
- **Multi-regulator coverage** - checks against four independent bodies of law (DPDP Act 2023, ASCI, TRAI/TCCCPR, BIS/BEE) in one pass.
- **Fail-safe by design** - any degraded condition (missing consent data, an unavailable rule source, an unexpected error) results in a `FLAGGED` verdict for human review, never a silent approval.
- **Legally defensible** - every verdict carries an exact clause citation and records the rule-corpus version that was active. Citations come only from the corpus, so the model cannot fabricate a legal reference.
- **Immutable audit log** - every verdict is persisted to an append-only record; reviewer decisions are stored as separate records alongside the original verdict, never overwriting it.
- **Human-in-the-loop review** - an Approval Inbox lets a reviewer override, reject, or send back flagged campaigns, with a justification required for overrides.
- **Filtering and export** - the audit log is filterable and searchable, with one-click CSV export for a regulator-ready report.
- **SQL-powered analytics** - the dashboard runs DuckDB queries over the audit log for verdict mix, approval rate, top violations, channel breakdowns, and check volume over time.
- **Privacy by design** - personal data (email, phone, Aadhaar, PAN) is redacted from campaign text before it is sent to the external AI, so no PII leaves the system; the redaction is noted on the verdict for auditability.
- **Decoupled frontend** - the Streamlit UI talks to the engine over HTTP only, so it can be replaced with a production frontend without changing the backend.

---

## Architecture

The system is split into two independently deployable halves that communicate over HTTP:

```
+--------------------------+         HTTP          +-------------------------------+
|   Streamlit frontend     |  ------------------->  |      FastAPI backend           |
|   (port 8501)            |                        |      (port 8000)               |
|                          |  <-------------------  |                                |
|  - Check Campaign        |     JSON verdict       |  Pipeline:                     |
|  - Approval Inbox        |                        |   1. Content analysis          |
|  - Audit Log             |                        |   2. Consent validation        |
|  - Dashboard             |                        |   3. Rule matching (keyword)   |
+--------------------------+                        |   3b. Gemini detection         |
                                                    |   4. Citation generation       |
                                                    |   5. Verdict engine            |
                                                    |   6. Audit log (SQLite)        |
                                                    +-------------------------------+
```

The request lifecycle for a single compliance check:

```
Campaign input
   -> Validation (Pydantic gateway)
   -> Content analysis      (extract claims, comparisons, urgency phrases)
   -> Consent validation    (look up audience consent rate)
   -> Rule matching         (keyword detection across DPDP / ASCI / TRAI / BIS, concurrently)
   -> Gemini detection      (contextual reasoning over the corpus; merged with keyword hits)
   -> Citation generation   (attach exact law + suggested fix to each hit)
   -> Verdict engine        (severity weighting -> APPROVED / FLAGGED / REJECTED)
   -> Audit log             (append-only persisted record)
   -> Verdict returned
```

If Gemini is unavailable (no key, quota, or blocked network), the pipeline falls back to keyword-only detection and records a note on the verdict, rather than failing.

---

## Technology stack

| Layer | Technology | Role |
|-------|-----------|------|
| Backend API | FastAPI + Uvicorn | Serves the compliance engine; async support, automatic OpenAPI docs |
| Validation | Pydantic | Strict request/response schemas; rejects malformed input at the gateway |
| AI reasoning | Google Gemini (`google-genai`, gemini-2.5-flash) | Context-aware violation detection over the corpus |
| Frontend | Streamlit | Multi-page dashboard for business users |
| Audit log | SQLite | Append-only verdict + review record (designed to migrate to PostgreSQL) |
| Analytics | DuckDB | In-process SQL analytics over the audit log |
| Language | Python 3.11 | - |

All components are free and open source at prototype scale; Gemini uses the free API tier.

---

## Project structure

```
compliance_agent/
|-- app/                         # Backend (the engine)
|   |-- main.py                  # FastAPI app, endpoints, global fail-safe handler
|   |-- config.py                # Environment-based settings (loads .env)
|   |-- core/
|   |   |-- orchestrator.py      # Sequences the pipeline; merges detectors; fail-safe logic
|   |   |-- corpus.py            # Loads and indexes the rule corpus
|   |   |-- exceptions.py        # Domain exceptions
|   |-- models/
|   |   |-- schemas.py           # Pydantic models (the API contract)
|   |-- services/
|   |   |-- content_analysis.py  # Claim / comparison / urgency extraction
|   |   |-- consent_validation.py# Audience consent lookup
|   |   |-- rule_matching.py     # Keyword detection across the four corpora (async)
|   |   |-- gemini_matching.py   # Gemini contextual detection
|   |   |-- citation_generator.py# Attaches legal citation + fix to each hit
|   |   |-- verdict_engine.py    # Severity weighting and final decision
|   |   |-- audit_log.py         # Append-only SQLite audit log + reviews
|   |-- data/
|       |-- rules/
|           |-- corpus.json      # Versioned rule corpus (DPDP, ASCI, TRAI, BIS)
|-- frontend/                    # Streamlit UI
|   |-- app.py                   # Home page + backend health check
|   |-- api_client.py            # HTTP client to the backend
|   |-- requirements.txt
|   |-- pages/
|       |-- 1_Check_Campaign.py  # Submit a campaign, view the verdict
|       |-- 2_Approval_Inbox.py  # Human-in-the-loop review of flagged campaigns
|       |-- 3_Audit_Log.py       # Filter, search, and export the verdict record
|       |-- 4_Dashboard.py       # DuckDB-powered compliance analytics
|-- requirements.txt             # Backend dependencies
|-- run.py                       # Backend launcher
|-- .env.example                 # Configuration template
```

---

## Getting started

### Prerequisites

- Python 3.11
- Two terminals (one for the backend, one for the frontend)
- A Gemini API key from https://aistudio.google.com/apikey (optional - the system runs keyword-only without one)

### 1. Set up the environment

```bash
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate
```

### 2. Run the backend

```bash
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
# Edit .env and paste your Gemini API key (optional)
python run.py
```

The API is now live at `http://127.0.0.1:8000`. Interactive documentation is available at `http://127.0.0.1:8000/docs`.

### 3. Run the frontend

In a second terminal (with the virtual environment activated):

```bash
pip install -r frontend/requirements.txt
streamlit run frontend/app.py
```

The dashboard opens at `http://localhost:8501`.

> **Note for restricted networks:** if `pip` fails with an SSL certificate error behind a corporate proxy, append `--trusted-host pypi.org --trusted-host files.pythonhosted.org` to the install commands.

### Configuration

Settings are read from `.env` (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | (empty) | Gemini key; when present, Gemini runs alongside keyword matching |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model to use |
| `RULE_CORPUS_VERSION` | `2026.06.1` | Recorded with every verdict for auditability |
| `CONFIDENCE_THRESHOLD` | `0.70` | Below this, a verdict is flagged for review |
| `MIN_CONSENT_RATE` | `1.0` | Minimum audience consent rate before a campaign is rejected |
| `AUDIT_DB_PATH` | `audit_log.db` | SQLite database path |

---

## How it works

### Detection

Two detectors run for every check and their results are merged (union, de-duplicated):

- **Keyword matching** - fast regex detection of literal trigger terms across the four corpora.
- **Gemini reasoning** - the campaign text and the corpus (as plain-English rule descriptions) are sent to Gemini, which returns the rule IDs it judges to be violated, reasoning about meaning and context. Citations are then looked up from the corpus by rule ID, so the model never fabricates a legal reference.

### Verdict calculation

Two independent factors drive every decision:

**1. Content** - each rule that fires carries a severity. Their weights are summed, and the confidence score is `1.0 - (total weighted load)`.

| Severity | Weight |
|----------|--------|
| Critical | 1.0 |
| High | 0.6 |
| Medium | 0.3 |
| Low | 0.1 |

**2. Consent** - if the audience's consent rate falls below `MIN_CONSENT_RATE`, that alone is treated as a Critical DPDP (Section 6) violation. The system never assumes consent.

**The decision rule:**

| Condition | Verdict |
|-----------|---------|
| Any Critical violation, or consent shortfall | **REJECTED** |
| Any other violation, or confidence below threshold | **FLAGGED** |
| No violations and full consent | **APPROVED** |

A consequence worth noting: identical content can yield different verdicts depending on the audience. Clean copy sent to a low-consent segment is rejected on the consent failure alone, while the same copy sent to a fully-consented segment is approved.

---

## The rule corpus

All legal rules live in a single versioned file: `app/data/rules/corpus.json`. Each rule is a self-contained object specifying a detection pattern, a severity, the legal citation to display, a plain-English explanation, and a suggested fix.

The corpus currently contains six content rules plus one consent rule generated by the verdict engine:

| Source | Detects | Severity | Citation |
|--------|---------|----------|----------|
| ASCI | Unsubstantiated superlatives ("best", "no.1", "world's") | Critical | ASCI Code Chapter I, Clause 1.4 |
| ASCI | Absolute guarantees ("100%", "guaranteed", "risk-free") | High | ASCI Code Chapter I, Clause 1.1 |
| TRAI | False urgency ("now", "hurry", "last chance") | High | CCPA Misleading Ads Guidelines 2022 / TCCCPR 2018 |
| BIS | Energy/certification claims without a valid reference | Medium | BIS / BEE energy-rating rules |
| DPDP | Data-sharing language without a consent notice | High | DPDP Act 2023, Section 5 (Notice) |
| DPDP | Implied or pre-ticked consent | Critical | DPDP Act 2023, Section 6 (Consent) |
| DPDP *(engine)* | Audience consent rate below threshold | Critical | DPDP Act 2023, Section 6 (Consent) |

Keeping each rule as a versioned, self-contained entry means a rule can be updated, replaced, or extended without touching the engine code, and the system always records which version of the law was active when a decision was made.

---

## API reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service status, active rule-corpus version, and Gemini status |
| `POST` | `/check` | Submit a campaign; returns a compliance verdict |
| `GET` | `/audit` | List all logged verdicts, newest first |
| `GET` | `/audit/{audit_reference}` | Retrieve a single verdict (with its review history) |
| `POST` | `/audit/{audit_reference}/review` | Record a human review action (override / reject / send back) |

Example request to `POST /check`:

```json
{
  "content": "Havells fans - the BEST in India! 100% safe. Buy NOW!",
  "channel": "email",
  "audience_segment": "low_consent_segment"
}
```

---

## Access control

The backend enforces role-based access. Two roles exist:

| Role | Can submit & read | Can review / override |
|------|:---:|:---:|
| `marketer` | yes | no |
| `compliance_officer` | yes | yes |

The frontend has a "Signed in as" switch in the sidebar (a demo stand-in for company single sign-on). Only a compliance officer can act on flagged campaigns, and the reviewer's identity is taken from their login - not a typed-in name - so the audit trail cannot be spoofed. In production the demo users are replaced by an identity provider (SSO/SAML) and a secrets store; only `app/core/auth.py` changes.

## Current limitations

This is a prototype. The following are known and intentional at this stage:

- **Demonstration rule set** - the corpus is a curated starter set. The clause references are realistic but should be verified against the source regulations before any production or external use.
- **Gemini free tier** - the free API tier has rate limits; when a limit is hit, the system falls back to keyword-only detection for that check and records a note.
- **Mock consent store** - consent data is simulated in-memory; the lookup interface is designed to be replaced by a live CRM (e.g. Salesforce) integration.
- **Names not redacted** - structured PII (email, phone, Aadhaar, PAN) is redacted before the AI call, but personal names have no reliable pattern and are not removed.
- **Text-only analysis** - the system analyses text content; claims embedded in images are out of scope for the prototype.
- **India-focused corpus** - only Indian regulations are covered; international frameworks (GDPR, UAE PDPL) are future work.
- **Local deployment** - the system runs locally; cloud deployment is planned.

---

## Roadmap

- [x] Backend compliance pipeline (content analysis -> consent -> rule matching -> citation -> verdict)
- [x] Immutable SQLite audit log with read endpoints
- [x] Streamlit multi-page frontend (Check Campaign, Approval Inbox, Audit Log, Dashboard)
- [x] Wire Approval Inbox review actions to a backend endpoint (logged alongside the original verdict)
- [x] Rich audit-log filtering, search, and CSV export
- [x] DuckDB-backed analytics on the dashboard
- [x] Integrate Gemini for context-aware reasoning (runs alongside keyword matching)
- [ ] Expand and verify the rule corpus against source regulations
- [ ] Live CRM (Salesforce) consent integration
- [ ] Cloud deployment

---

## Authors

Niharika Lathish, Harshita Lalwani, Aryaman Harlikar

Developed as a proof-of-concept during an internship engagement.
