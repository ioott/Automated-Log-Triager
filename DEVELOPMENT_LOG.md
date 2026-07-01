# Development Log

## 1. Full Project Phases
- [x] **Phase 1: Foundation** (FastAPI, Pydantic validation, Clean Architecture setup, Docker, Background Tasks, Exception Handling)
- [x] **Phase 2: RAG & Vector Database** (Set up ChromaDB and ingest the Known Errors Manual)
- [x] **Phase 3: AI Agent Integration** (LangChain + Google Gemini Free Tier, Data Masking Service, Fallback Strategy)
- [x] **Phase 4: Simple Web Dashboard** (Vanilla HTML/JS dashboard with real-time polling)
- [x] **Phase 5: Codebase Corrections** (Completed LangChain refactor, organized routes into routers, adopted FastAPI lifespan pattern)
- [x] **Phase 6: Observability & Operational Improvements** (Real health check, Correlation ID middleware, seed script, API tests, Makefile)
- [x] **Phase 7: Risk Calibration Fix & Dashboard UX** (Fixed risk_assessment grounding, added knowledge-base listing endpoint, dashboard Clear/Paste buttons)

## 2. Architecture Summary

The application is a 4-stage async pipeline triggered by `POST /api/v1/logs/triage`:

1. **Masking** — `DataMaskingService` scrubs IPs, emails, and transaction IDs before any data reaches the LLM.
2. **RAG** — `VectorStore` queries ChromaDB (`known_errors` collection) for the closest known-error entry.
3. **AI Diagnosis** — `DiagnosticAgent` runs a `LangChain` chain (`ChatPromptTemplate | ChatGoogleGenerativeAI | JsonOutputParser`) backed by Google Gemini. Retries up to 3× on transient failures.
4. **Storage** — `ReportStorage` keeps the final report in an in-memory list (capped at 50, newest-first).

Services are initialized via FastAPI's `lifespan` context manager and injected into routes via `Depends`.

## 3. Completed Tasks (with Semantic Commits)
- `feat: initialize project structure and phase 1 foundation`
- `feat: integrate chromadb and create knowledge base ingestion endpoint`
- `feat: implement ai agent diagnostic pipeline and data masking`
- `fix: resolve NameError in masking service and add unit tests`
- `docs: add bilingual (EN/PT) README.md`
- `perf: refactor to direct LangChain to solve build bloat and implement Phase 4 dashboard`
- `fix: complete langchain refactor, organize api routers, adopt fastapi lifespan pattern`
- `refactor: replace stateless classes and custom exception with simpler primitives`
- `feat: add health check, correlation id, seed script, api tests and makefile`
- `fix: ground risk_assessment in known risk_level and add missing CRITICAL option`
- `feat: add GET /api/v1/knowledge-base listing endpoint`
- `feat: add Clear and Paste from Clipboard buttons to dashboard`
- `test: cover knowledge-base listing and risk-level grounding regression`
- `chore: move test docs/postman collection to docs/ and seed script/sample data to scripts/`
- `fix: make Makefile's test/seed targets call venv/bin/python directly so they work without manual activation`

## 4. Impediments & Applied Solutions
- **CrewAI Dependency Bloat:** Build times were >1h. **Solution:** Replaced CrewAI entirely with a native LangChain `prompt | llm | JsonOutputParser` chain, removing the dependency from `requirements.txt`. `DiagnosticAgent` is now ~60 lines with no framework overhead.
- **Incomplete Router Structure:** Routes lived in `main.py` while `app/api/` was empty. **Solution:** Created `app/api/logs.py`, `app/api/knowledge_base.py`, and `app/api/reports.py`; services are injected via `app/core/dependencies.py` using FastAPI's `Depends`.
- **Deprecated Startup Events:** Module-level service initialization was replaced with FastAPI's `lifespan` async context manager (the modern pattern since FastAPI 0.93).
- **Workspace Permissions:** Contorned by using shell redirection (`cat << EOF`) to manage files in the correct directory.
- **Serialization:** Fixed datetime serialization issue in masking service.
- **Risk Assessment Miscalibration:** Manual testing showed MEDIUM-severity errors diagnosed as HIGH, LOW as MEDIUM, and CRITICAL as HIGH. Root cause was two-fold: (1) the LLM prompt's `risk_assessment` enum only listed `HIGH, MEDIUM, LOW` — `CRITICAL` was never a valid option, silently forcing every critical known-error down to HIGH; (2) `TriagePipelineService` only forwarded the RAG-retrieved document text to the LLM, discarding the `risk_level` metadata already curated in the Known Errors Manual, so the model had to guess severity from prose alone. **Solution:** added `CRITICAL` to the prompt's enum and instructed the model to defer to the manual's risk level; `triage_pipeline.py` now appends `Known Risk Level (from manual): <level>` to the RAG context whenever a match is found. Verified against all three demo error codes after the fix (LOW/HIGH/CRITICAL all matched expectations).

## 5. Next Steps
- Record the demonstration video.
- See README.md "Future Improvements" — search endpoints for `/api/v1/reports` and `/api/v1/knowledge-base` by id/keyword.
