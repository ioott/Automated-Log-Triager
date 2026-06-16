from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import logging
from typing import List
from app.core.config import settings
from app.core.exceptions import TriagePipelineException, global_exception_handler, triage_exception_handler
from app.models.schemas import IncomingLogPayload, KnownErrorManualEntry
from app.services.vector_db import VectorStore
from app.services.triage_pipeline import TriagePipelineService
from app.services.storage import ReportStorage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'
)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Asynchronous pipeline for triaging and diagnosing transaction failure logs."
)

templates = Jinja2Templates(directory="app/templates")

# Register exception handlers
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(TriagePipelineException, triage_exception_handler)

# Initialize external services
vector_store = VectorStore()
pipeline_service = TriagePipelineService(vector_store=vector_store)

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Serves the frontend dashboard."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/v1/reports")
async def get_reports():
    """Returns all diagnosed reports for the dashboard."""
    return ReportStorage.get_all()

@app.post("/api/v1/knowledge-base/ingest", status_code=201)
async def ingest_knowledge_base(entries: List[KnownErrorManualEntry]):
    """Ingests Known Error Manual entries into the Vector DB for RAG."""
    try:
        count = vector_store.ingest_entries(entries)
        return {"status": "success", "inserted_count": count}
    except Exception as e:
        logging.error(f"Knowledge base ingestion failed: {e}")
        raise TriagePipelineException(message=f"Ingestion failed: {str(e)}", status_code=500)

@app.post("/api/v1/logs/triage", status_code=202)
async def ingest_log(payload: IncomingLogPayload, background_tasks: BackgroundTasks):
    """Ingests a raw transaction failure log and triggers the diagnostic pipeline."""
    logging.info(f"Received log for transaction {payload.transaction_id} from {payload.service}")
    background_tasks.add_task(pipeline_service.process_log, payload)
    return {
        "status": "accepted",
        "transaction_id": payload.transaction_id,
        "message": "Log accepted for asynchronous triage."
    }

@app.get("/health", status_code=200)
async def health_check():
    """Liveness probe for infrastructure monitoring."""
    return {"status": "ok", "environment": settings.ENVIRONMENT}
