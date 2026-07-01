import asyncio
from unittest.mock import MagicMock, AsyncMock
from app.services.triage_pipeline import TriagePipelineService
from app.models.schemas import IncomingLogPayload

VALID_LOG = IncomingLogPayload(
    **{
        "timestamp": "2026-06-09T23:15:00Z",
        "transaction_id": "tx_test_001",
        "service": "payment-gateway",
        "environment": "production",
        "error_payload": {
            "component": "EVM-Bridge",
            "http_status": 504,
            "error_code": "CW_ERR_BLOCKCHAIN_TIMEOUT",
            "message": "Gateway timeout",
            "network_details": {
                "target_host": "rpc.example.com",
                "latency_ms": 5000,
                "retries_attempted": 3,
            },
            "raw_trace": "Panic: connection reset",
        },
    }
)


def _build_pipeline(rag_results):
    mock_vector_store = MagicMock()
    mock_vector_store.search_similar_errors.return_value = rag_results

    pipeline = TriagePipelineService.__new__(TriagePipelineService)
    pipeline.vector_store = mock_vector_store
    pipeline.agent = MagicMock()
    pipeline.agent.run_diagnosis = AsyncMock(
        return_value={
            "root_cause": "root cause",
            "action_plan": ["step"],
            "risk_assessment": "CRITICAL",
            "advisor_notes": "notes",
        }
    )
    return pipeline


def test_known_risk_level_is_forwarded_to_agent():
    pipeline = _build_pipeline(
        {
            "documents": [["Known error description."]],
            "metadatas": [
                [{"risk_level": "CRITICAL", "error_code": "CW_ERR_BLOCKCHAIN_TIMEOUT"}]
            ],
        }
    )

    asyncio.run(pipeline.process_log(VALID_LOG))

    rag_context_passed = pipeline.agent.run_diagnosis.call_args.args[1]
    assert "Known Risk Level (from manual): CRITICAL" in rag_context_passed


def test_missing_rag_match_skips_known_risk_level():
    pipeline = _build_pipeline({"documents": [], "metadatas": []})

    asyncio.run(pipeline.process_log(VALID_LOG))

    rag_context_passed = pipeline.agent.run_diagnosis.call_args.args[1]
    assert "Known Risk Level" not in rag_context_passed
