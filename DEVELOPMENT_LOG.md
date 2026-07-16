# Development Log

## 1. Full Project Phases
- [x] **Phase 1: Foundation** (FastAPI, Pydantic validation, Clean Architecture setup, Docker, Background Tasks, Exception Handling)
- [x] **Phase 2: RAG & Vector Database** (Set up ChromaDB and ingest the Known Errors Manual)
- [x] **Phase 3: AI Agent Integration** (LangChain + Google Gemini Free Tier, Data Masking Service, Fallback Strategy)
- [x] **Phase 4: Simple Web Dashboard** (Vanilla HTML/JS dashboard with real-time polling)
- [x] **Phase 5: Codebase Corrections** (Completed LangChain refactor, organized routes into routers, adopted FastAPI lifespan pattern)
- [x] **Phase 6: Observability & Operational Improvements** (Real health check, Correlation ID middleware, seed script, API tests, Makefile)
- [x] **Phase 7: Risk Calibration Fix & Dashboard UX** (Fixed risk_assessment grounding, added knowledge-base listing endpoint, dashboard Clear/Paste buttons)
- [x] **Phase 8: Demo Video** (Recorded and compressed the 3-scene walkthrough — code, dashboard, Swagger — linked from README.md; see `docs/demo.mp4`)
- [x] **Phase 9: Vector DB Migration to Chroma Cloud** (Replaced self-hosted ChromaDB-on-Render with Chroma Cloud to eliminate cross-service cold-start compounding; fixed the client-side embedding model download that surfaced as a new, smaller cold-start failure once the bigger one was gone)

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
- `fix: found real cause of repeated wake failures - rate limiting, not cold start`
- `migrate vector DB from self-hosted ChromaDB-on-Render to Chroma Cloud`
- `fix: absorb the client-side embedding model download into the connect step`

## 4. Impediments & Applied Solutions
- **CrewAI Dependency Bloat:** Build times were >1h. **Solution:** Replaced CrewAI entirely with a native LangChain `prompt | llm | JsonOutputParser` chain, removing the dependency from `requirements.txt`. `DiagnosticAgent` is now ~60 lines with no framework overhead.
- **Incomplete Router Structure:** Routes lived in `main.py` while `app/api/` was empty. **Solution:** Created `app/api/logs.py`, `app/api/knowledge_base.py`, and `app/api/reports.py`; services are injected via `app/core/dependencies.py` using FastAPI's `Depends`.
- **Deprecated Startup Events:** Module-level service initialization was replaced with FastAPI's `lifespan` async context manager (the modern pattern since FastAPI 0.93).
- **Workspace Permissions:** Contorned by using shell redirection (`cat << EOF`) to manage files in the correct directory.
- **Serialization:** Fixed datetime serialization issue in masking service.
- **Risk Assessment Miscalibration:** Manual testing showed MEDIUM-severity errors diagnosed as HIGH, LOW as MEDIUM, and CRITICAL as HIGH. Root cause was two-fold: (1) the LLM prompt's `risk_assessment` enum only listed `HIGH, MEDIUM, LOW` — `CRITICAL` was never a valid option, silently forcing every critical known-error down to HIGH; (2) `TriagePipelineService` only forwarded the RAG-retrieved document text to the LLM, discarding the `risk_level` metadata already curated in the Known Errors Manual, so the model had to guess severity from prose alone. **Solution:** added `CRITICAL` to the prompt's enum and instructed the model to defer to the manual's risk level; `triage_pipeline.py` now appends `Known Risk Level (from manual): <level>` to the RAG context whenever a match is found. Verified against all three demo error codes after the fix (LOW/HIGH/CRITICAL all matched expectations).
- **Two-Service Cold Start Compounding (Render Free Tier):** Both the API and a self-hosted ChromaDB ran as separate Render Free services, each hibernating independently. Each attempted fix exposed a deeper one: retry/backoff for the connection hid that the `chromadb` client's `httpx` session hardcodes `timeout=None`, fixing that exposed that `get_or_create_collection()` makes 4 sequential HTTP requests per attempt, and multiplying that across retries and repeated dashboard clicks was enough request volume to trip Render/Cloudflare's free-tier rate limiting (429s), which naive retrying made worse. **Solution:** stopped treating the symptom and addressed the architecture directly — migrated ChromaDB to **Chroma Cloud** (managed, always-on, persistent storage), removing the second hibernating service entirely rather than adding another layer of client-side resilience on top of it.
- **Client-Side Embedding Model Download (post-migration):** After the Chroma Cloud migration, the first triage request following a Render cold start still occasionally failed. Root cause: `chromadb`'s default embedding function computes embeddings client-side (`onnxruntime` + a ~80MB ONNX model), downloaded fresh on every cold process since Render's Free tier has no persistent disk — a cost that existed before the migration too, but was previously masked by the much larger ChromaDB-hibernation problem. **Solution:** `VectorStore._connect_and_get_collection_once()` now runs a throwaway query immediately after connecting, forcing that one-time download to happen inside the already-retried, timeout-protected connect step instead of on a real user request. Verified locally with a cleared cache against the live Chroma Cloud account: ~20.7s cold, ~0.4s on the next call in the same process.

## 5. Next Steps
- See README.md "Future Improvements" — search endpoints for `/api/v1/reports` and `/api/v1/knowledge-base` by id/keyword.
