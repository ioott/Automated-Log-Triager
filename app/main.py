import uuid
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.core.config import settings
from app.core.exceptions import global_exception_handler
from app.core.seed_data import KNOWN_ERROR_ENTRIES
from app.models.schemas import KnownErrorManualEntry
from app.services.vector_db import VectorStore
from app.services.triage_pipeline import TriagePipelineService
from app.api import logs, knowledge_base, reports

logging.basicConfig(
    level=logging.INFO,
    format=(
        '{"time": "%(asctime)s", "level": "%(levelname)s",'
        ' "message": "%(message)s"}'
    ),
)

logger = logging.getLogger(__name__)


def _auto_seed_if_empty(vector_store: VectorStore) -> None:
    """
    Populates the knowledge base on startup if it's empty.

    The ChromaDB deployment backing this app runs on a free, ephemeral
    instance with no persistent disk, so the collection is wiped on every
    restart (including automatic spin-downs from inactivity). Without this,
    the RAG pipeline would silently run against an empty knowledge base
    until someone remembered to run scripts/seed.py by hand.

    This only writes data when the collection is empty, so it's safe to
    run on every startup - it will never duplicate entries once seeded.
    """
    try:
        if vector_store.count_entries() > 0:
            logger.info("Knowledge base already populated; skipping auto-seed.")
            return

        entries = [KnownErrorManualEntry(**e) for e in KNOWN_ERROR_ENTRIES]
        inserted = vector_store.ingest_entries(entries)
        logger.info(f"Knowledge base was empty; auto-seeded {inserted} entries.")
    except Exception as e:
        # Don't crash the whole app if ChromaDB isn't reachable yet at
        # startup - the app already treats the vector store as a lazily
        # connected dependency (see /health), so we log and move on.
        logger.error(f"Auto-seed check failed, continuing startup without seeding: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.vector_store = VectorStore()
    app.state.pipeline_service = TriagePipelineService(
        vector_store=app.state.vector_store
    )

    _auto_seed_if_empty(app.state.vector_store)

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
    """Liveness and dependency probe."""
    db_status = "ok"
    try:
        request.app.state.vector_store._get_collection()
    except Exception:
        db_status = "unavailable"
    overall = "ok" if db_status == "ok" else "degraded"
    return {
        "status": overall,
        "environment": settings.ENVIRONMENT,
        "dependencies": {"chromadb": db_status},
    }
