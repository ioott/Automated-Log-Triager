# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Run with Docker (recommended):**
```bash
docker compose up --build -d
# API: http://localhost:8000 | Swagger: http://localhost:8000/docs | ChromaDB: http://localhost:8001
```

**Run locally:**
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then set GOOGLE_API_KEY
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Tests:**
```bash
PYTHONPATH=. pytest -v          # all tests
PYTHONPATH=. pytest tests/test_masking.py -v  # single file
```
Tests require no running server or API key.

There is no configured linter — no `.flake8`, `ruff.toml`, or `pyproject.toml`.

## Environment Variables

| Variable | Purpose |
|---|---|
| `GOOGLE_API_KEY` | Google AI Studio key — required for AI diagnosis |
| `GEMINI_MODEL_NAME` | Inference model (default: `gemini-2.5-flash`) |
| `VECTOR_DB_URL` | ChromaDB HTTP URL (default: `http://chromadb:8000`) |
| `ENVIRONMENT` | Runtime tag (default: `development`) |

## Architecture

The system is a **FastAPI service** that accepts a log payload and runs it through a 4-stage async pipeline, returning `202 Accepted` immediately while processing in a `BackgroundTask`.

### Pipeline stages (`app/services/triage_pipeline.py`)

1. **Masking** — `DataMaskingService` (`app/services/masking.py`) recursively walks the payload dict and replaces IPs, emails, and transaction IDs with `[MASKED_*]` tokens before any data reaches the LLM.
2. **RAG** — `VectorStore` (`app/services/vector_db.py`) queries ChromaDB (`known_errors` collection) with the error code + message to retrieve the closest known-error entry as grounding context.
3. **AI Diagnosis** — `DiagnosticAgent` (`app/services/agents.py`) runs a LangChain chain (`ChatPromptTemplate | ChatGoogleGenerativeAI | JsonOutputParser`) backed by Google Gemini. Returns structured JSON: `{root_cause, action_plan, risk_assessment, advisor_notes}`. Retries up to 3× on transient failures.
4. **Storage** — `ReportStorage` (`app/services/storage.py`) keeps the final report in an in-memory list (newest-first, capped at 50). **Reports are lost on restart.**

If any stage fails, a fallback report with `status: "[AI_DIAGNOSIS_FAILED]"` is always stored.

### Key endpoints

| Method | Path | Router file |
|---|---|---|
| `POST` | `/api/v1/logs/triage` | `app/api/logs.py` |
| `POST` | `/api/v1/knowledge-base/ingest` | `app/api/knowledge_base.py` |
| `GET` | `/api/v1/reports` | `app/api/reports.py` |
| `GET` | `/` | `app/main.py` (Jinja2 dashboard) |
| `GET` | `/health` | `app/main.py` (liveness probe) |

### Service initialization and dependency injection

Services (`VectorStore`, `TriagePipelineService`) are initialized in the `lifespan` async context manager in `app/main.py` and stored on `app.state`. Routes receive them via `Depends(get_vector_store)` / `Depends(get_pipeline_service)` defined in `app/core/dependencies.py`.

### Schemas and config

- All request/response shapes are Pydantic v2 models in `app/models/schemas.py`.
- Settings are loaded via `pydantic-settings` in `app/core/config.py`.
- Global exception handling (both `TriagePipelineException` and bare `Exception`) is registered in `app/core/exceptions.py` — all errors return structured JSON.
