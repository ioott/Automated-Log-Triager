import logging
from fastapi import APIRouter, BackgroundTasks, Depends
from app.models.schemas import IncomingLogPayload
from app.services.triage_pipeline import TriagePipelineService
from app.core.dependencies import get_pipeline_service

router = APIRouter(prefix="/api/v1/logs", tags=["logs"])
logger = logging.getLogger(__name__)


@router.post("/triage", status_code=202)
async def ingest_log(
    payload: IncomingLogPayload,
    background_tasks: BackgroundTasks,
    pipeline_service: TriagePipelineService = Depends(get_pipeline_service),
):
    """Ingests a raw transaction failure log and triggers the pipeline."""
    logger.info(
        f"Received log for transaction {payload.transaction_id}"
        f" from {payload.service}"
    )
    background_tasks.add_task(pipeline_service.process_log, payload)
    return {
        "status": "accepted",
        "transaction_id": payload.transaction_id,
        "message": "Log accepted for asynchronous triage.",
    }
