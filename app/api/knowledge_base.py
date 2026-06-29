import logging
from typing import List
from fastapi import APIRouter, Depends
from app.models.schemas import KnownErrorManualEntry
from app.services.vector_db import VectorStore
from app.core.dependencies import get_vector_store
from app.core.exceptions import TriagePipelineException

router = APIRouter(prefix="/api/v1/knowledge-base", tags=["knowledge-base"])
logger = logging.getLogger(__name__)


@router.post("/ingest", status_code=201)
async def ingest_knowledge_base(
    entries: List[KnownErrorManualEntry],
    vector_store: VectorStore = Depends(get_vector_store),
):
    """Ingests Known Error Manual entries into the Vector DB for RAG."""
    try:
        count = vector_store.ingest_entries(entries)
        return {"status": "success", "inserted_count": count}
    except Exception as e:
        logger.error(f"Knowledge base ingestion failed: {e}")
        raise TriagePipelineException(
            message=f"Ingestion failed: {str(e)}", status_code=500
        )
