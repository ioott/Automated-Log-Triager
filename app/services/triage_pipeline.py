import logging
from app.models.schemas import IncomingLogPayload
from app.services.masking import DataMaskingService
from app.services.vector_db import VectorStore
from app.services.agents import DiagnosticAgent

logger = logging.getLogger(__name__)

class TriagePipelineService:
    """
    Main orchestration service for the Log Triage pipeline.
    Connects Masking, RAG (VectorStore), and AI Agents.
    """
    
    def __init__(self, vector_store: VectorStore):
        self.masker = DataMaskingService()
        self.vector_store = vector_store
        self.agent = DiagnosticAgent()

    async def process_log(self, payload: IncomingLogPayload):
        """
        Executes the full pipeline for an incoming log.
        """
        transaction_id = payload.transaction_id
        try:
            logger.info(f"Starting triage pipeline for transaction: {transaction_id}")
            
            # 1. Data Masking
            masked_log = self.masker.mask_log(payload.model_dump())
            logger.info(f"Log masked successfully for {transaction_id}")
            
            # 2. RAG (Search Knowledge Base)
            # We search based on the error message or code
            search_query = f"{payload.error_payload.error_code} {payload.error_payload.message}"
            rag_results = self.vector_store.search_similar_errors(search_query)
            
            rag_context = "No direct match found in Knowledge Base."
            if rag_results and rag_results['documents']:
                rag_context = rag_results['documents'][0][0]
            
            logger.info(f"RAG context retrieved for {transaction_id}")
            
            # 3. AI Agent Diagnosis
            diagnosis = await self.agent.run_diagnosis(masked_log, rag_context)
            
            # Final output structured for SRE (as advisors)
            final_report = {
                "transaction_id": transaction_id,
                "status": "DIAGNOSED",
                "diagnosis": diagnosis,
                "rag_match": rag_context[:200] + "..." # Truncated for summary
            }
            
            logger.info(f"Triage complete for {transaction_id}. Root cause: {diagnosis.get('root_cause')}")
            
            # TODO: In Phase 4, we will push this to a DB/WebSocket for the dashboard
            return final_report

        except Exception as e:
            logger.error(f"PIPELINE FAILURE for {transaction_id}: {str(e)}", exc_info=True)
            # Fallback Strategy: Never lose the log
            failed_report = {
                "transaction_id": transaction_id,
                "status": "[AI_DIAGNOSIS_FAILED]",
                "raw_payload": payload.model_dump(),
                "error": str(e)
            }
            # Log the failure clearly
            logger.warning(f"Forwarding raw log for {transaction_id} due to diagnosis failure.")
            return failed_report
