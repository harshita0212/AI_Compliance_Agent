# AI Compliance Agent — Backend

Modular FastAPI backend for the marketing-compliance agent. Runs end-to-end
out of the box with mocked layers (no Gemini key needed) so you can develop
the pipeline first and plug in real services incrementally.

## Setup (VS Code terminal, Windows)

```powershell
cd compliance_agent
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python run.py
```

Open http://127.0.0.1:8000/docs for the interactive Swagger UI.

## Quick test

```powershell
# health
curl http://127.0.0.1:8000/health

# a bad campaign -> REJECTED
curl -X POST http://127.0.0.1:8000/check -H "Content-Type: application/json" -d "{\"content\":\"Havells fans - the BEST in India! 100% safe. Buy NOW!\",\"channel\":\"email\",\"audience_segment\":\"low_consent_segment\"}"
```

## Architecture

```
app/
  main.py                 FastAPI app + global fail-safe exception handler
  config.py               env-based settings
  models/schemas.py       Pydantic contracts (strict channel validation)
  core/
    orchestrator.py       sequences the layers, centralises fail-safe logic
    exceptions.py         domain errors
  services/
    content_analysis.py   claim extraction (Gemini + mock)
    consent_validation.py consent store lookup (mock SQLite/Salesforce)
    rule_matching.py       async match across DPDP/ASCI/TRAI/BIS corpi
    verdict_engine.py      severity weighting -> APPROVED/FLAGGED/REJECTED
  data/rules/corpus.json  versioned rule corpus
```

## Design principles baked in

- **Fail safe** — any degraded condition (consent store down, Gemini quota,
  unhandled error) returns FLAGGED, never a silent APPROVED, never a 500.
- **Strict gateway** — Pydantic rejects invalid input (e.g. bad channel)
  before any expensive work runs.
- **Async rule matching** — all four corpi checked concurrently to stay
  under the 10-second target.
- **Decoupled** — all logic lives in services/core, so Streamlit can be
  swapped for React without touching the engine.
- **Versioned corpus** — every verdict records the rule version it used.

## Next steps (where to fill in)

1. `services/content_analysis.py::_gemini_extract` — wire the real Gemini call.
2. `services/consent_validation.py` — replace `_MOCK_STORE` with SQLite, then Salesforce.
3. `services/rule_matching.py` — add semantic (ChromaDB) matching alongside regex; populate the DPDP corpus.
4. Add the PostgreSQL audit-log writer (call it from the orchestrator after `decide`).
5. Set `USE_MOCK_LLM=false` in `.env` once Gemini is connected.
