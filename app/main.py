import uuid
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.core.config import settings
from app.core.exceptions import global_exception_handler
from app.core.logging_config import configure_logging
from app.core.seed_data import ensure_seeded
from app.services.vector_db import VectorStore
from app.services.triage_pipeline import TriagePipelineService
from app.api import logs, knowledge_base, reports

configure_logging(logging.INFO)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.vector_store = VectorStore()
    app.state.pipeline_service = TriagePipelineService(
        vector_store=app.state.vector_store
    )

    # Best-effort: also re-checked before every triage request, since
    # ChromaDB (no persistent disk) can lose its data on its own restart
    # cycle independently of this process. See app/core/seed_data.py.
    ensure_seeded(app.state.vector_store)

    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Asynchronous pipeline for triaging and diagnosing "
        "transaction failure logs."
    ),
    lifespan=lifespan,
)

templates = Jinja2Templates(directory="app/templates")


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


app.add_exception_handler(Exception, global_exception_handler)

app.include_router(logs.router)
app.include_router(knowledge_base.router)
app.include_router(reports.router)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Serves the frontend dashboard."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health_check(request: Request):
    """Liveness and dependency probe.

    Runs a real similarity query (not just get_or_create_collection) so
    this genuinely exercises the same path a triage request takes,
    including ChromaDB's embedding function. A bare connection can
    succeed - and did, in practice - while an actual query still fails on
    a cold instance that hasn't finished loading its embedding model yet;
    checking only the connection made this endpoint (and the dashboard's
    "Wake up ChromaDB" button, which polls it) report "ok" before triage
    requests could reliably go through.
    """
    db_status = "ok"
    try:
        vector_store = request.app.state.vector_store
        ensure_seeded(vector_store)
        vector_store.search_similar_errors("health check", n_results=1)
    except Exception:
        db_status = "unavailable"
    overall = "ok" if db_status == "ok" else "degraded"
    return {
        "status": overall,
        "environment": settings.ENVIRONMENT,
        "dependencies": {"chromadb": db_status},
    }
