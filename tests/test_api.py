import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.core.dependencies import get_pipeline_service, get_vector_store

VALID_LOG = {
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


@pytest.fixture
def client():
    mock_pipeline = MagicMock()
    mock_pipeline.process_log = AsyncMock()
    mock_vector_store = MagicMock()
    mock_vector_store.ingest_entries.return_value = 1

    app.dependency_overrides[get_pipeline_service] = (
        lambda: mock_pipeline
    )
    app.dependency_overrides[get_vector_store] = (
        lambda: mock_vector_store
    )

    with (
        patch("app.main.VectorStore", return_value=mock_vector_store),
        patch(
            "app.main.TriagePipelineService",
            return_value=mock_pipeline,
        ),
    ):
        with TestClient(app) as c:
            yield c

    app.dependency_overrides.clear()


def test_triage_accepts_valid_log(client):
    response = client.post("/api/v1/logs/triage", json=VALID_LOG)
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert response.json()["transaction_id"] == "tx_test_001"


def test_triage_rejects_invalid_payload(client):
    response = client.post("/api/v1/logs/triage", json={"bad": "data"})
    assert response.status_code == 422


def test_get_reports_returns_list(client):
    response = client.get("/api/v1/reports")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_ingest_knowledge_base(client):
    entry = {
        "error_code": "CW_ERR_TEST",
        "technical_description": "Test error description.",
        "root_cause": "Test root cause.",
        "action_plan": ["Step 1.", "Step 2."],
        "risk_level": "LOW",
    }
    response = client.post(
        "/api/v1/knowledge-base/ingest", json=[entry]
    )
    assert response.status_code == 201
    assert response.json()["inserted_count"] == 1


def test_list_knowledge_base(client):
    mock_vector_store = client.app.dependency_overrides[get_vector_store]()
    mock_vector_store.list_entries.return_value = [
        {
            "error_code": "CW_ERR_TEST",
            "risk_level": "LOW",
            "document": "Error Code: CW_ERR_TEST. ...",
        }
    ]
    response = client.get("/api/v1/knowledge-base")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["entries"][0]["error_code"] == "CW_ERR_TEST"


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "dependencies" in data
    assert "chromadb" in data["dependencies"]


def test_correlation_id_generated(client):
    response = client.get("/api/v1/reports")
    assert "x-request-id" in response.headers


def test_correlation_id_propagated(client):
    response = client.get(
        "/api/v1/reports",
        headers={"X-Request-ID": "custom-id-123"},
    )
    assert response.headers["x-request-id"] == "custom-id-123"
