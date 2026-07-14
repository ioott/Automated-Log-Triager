import logging
from app.models.schemas import IncomingLogPayload
from app.services import masking, storage
from app.services.vector_db import VectorStore
from app.services.agents import DiagnosticAgent
from app.core.exceptions import classify_error
from app.core.seed_data import ensure_seeded

logger = logging.getLogger(__name__)


class TriagePipelineService:
    """Orchestrates the 4-stage log triage pipeline."""

    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        self.agent = DiagnosticAgent()

    async def process_log(self, payload: IncomingLogPayload):
        transaction_id = payload.transaction_id
        try:
            logger.info(
                f"Starting triage pipeline for transaction: {transaction_id}"
            )

            masked_log = masking.mask_log(payload.model_dump())
            logger.info(f"Log masked successfully for {transaction_id}")

            # ChromaDB has no persistent disk and can lose its data on its
            # own restart cycle, independent of this process. Re-check
            # before every RAG lookup rather than relying solely on the
            # startup seed (see app/core/seed_data.py for why).
            ensure_seeded(self.vector_store)

            query = (
                f"{payload.error_payload.error_code} "
                f"{payload.error_payload.message}"
            )
            rag_results = self.vector_store.search_similar_errors(query)

            rag_context = "No direct match found in Knowledge Base."
            documents = (rag_results or {}).get("documents") or []
            if documents and documents[0]:
                rag_context = documents[0][0]
                metadatas = rag_results.get("metadatas") or [[]]
                if metadatas and metadatas[0]:
                    known_risk_level = metadatas[0][0].get("risk_level")
                    if known_risk_level:
                        rag_context += (
                            f"\nKnown Risk Level (from manual): "
                            f"{known_risk_level}"
                        )

            logger.info(f"RAG context retrieved for {transaction_id}")

            diagnosis = await self.agent.run_diagnosis(
                masked_log, rag_context
            )

            final_report = {
                "transaction_id": transaction_id,
                "status": "DIAGNOSED",
                "diagnosis": diagnosis,
                "rag_match": rag_context[:200] + "...",
                "timestamp": payload.timestamp.isoformat(),
            }

            logger.info(
                f"Triage complete for {transaction_id}. "
                f"Root cause: {diagnosis.get('root_cause')}"
            )

            storage.add_report(final_report)
            return final_report

        except Exception as e:
            # Log the full, untouched exception for debugging...
            logger.error(
                f"PIPELINE FAILURE for {transaction_id}: {str(e)}",
                exc_info=True,
            )
            # ...but only ever store/display a short, classified message.
            # Upstream HTTP clients (notably ChromaDB's, when the
            # free-tier instance is asleep) can surface a raw HTML error
            # page as the exception text, which would otherwise get
            # rendered verbatim in the dashboard. `error_type` lets the
            # frontend explain *why* it failed and decide whether to
            # auto-retry (see classify_error's docstring).
            classification = classify_error(e)
            failed_report = {
                "transaction_id": transaction_id,
                "status": "[AI_DIAGNOSIS_FAILED]",
                "raw_payload": payload.model_dump(),
                "error": classification["message"],
                "error_type": classification["type"],
                "timestamp": payload.timestamp.isoformat(),
            }
            storage.add_report(failed_report)
            return failed_report
