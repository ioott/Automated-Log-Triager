from fastapi import FastAPI
import logging
from typing import List
from app.core.config import settings
from app.core.exceptions import TriagePipelineException, global_exception_handler, triage_exception_handler
from app.models.schemas import IncomingLogPayload, KnownErrorManualEntry
from app.services.vector_db import VectorStore

# Configure structured JSON-like logging for production systems
logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'
)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Asynchronous pipeline for triaging and diagnosing transaction failure logs."
)

# Register exception handlers
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(TriagePipelineException, triage_exception_handler)

# Initialize external services
vector_store = VectorStore()

@app.post("/api/v1/knowledge-base/ingest", status_code=201)
async def ingest_knowledge_base(entries: List[KnownErrorManualEntry]):
    """
    Ingests Known Error Manual entries into the Vector DB for RAG.
    """
    try:
        count = vector_store.ingest_entries(entries)
        return {"status": "success", "inserted_count": count}
    except Exception as e:
        logging.error(f"Knowledge base ingestion failed: {e}")
        raise TriagePipelineException(message=f"Ingestion failed: {str(e)}", status_code=500)

@app.post("/api/v1/logs/triage", status_code=202)
async def ingest_log(payload: IncomingLogPayload):
    """
    Ingests a raw transaction failure log.
    In Phase 1, it only validates the payload structure and returns an acknowledgment.
    """
    logging.info(f"Received log for transaction {payload.transaction_id} from {payload.service}")
    # TODO: Implement BackgroundTask to pass the payload to the RAG/Agent pipeline
    return {
        "status": "accepted",
        "transaction_id": payload.transaction_id,
        "message": "Log accepted for asynchronous triage."
    }

@app.get("/health", status_code=200)
async def health_check():
    """Liveness probe for infrastructure monitoring."""
    return {"status": "ok", "environment": settings.ENVIRONMENT}
