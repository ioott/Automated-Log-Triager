import pytest
from pydantic import ValidationError
from app.models.schemas import IncomingLogPayload, KnownErrorManualEntry


def test_valid_incoming_log_payload():
    """Test that a valid payload successfully instantiates the schema."""
    valid_data = {
      "timestamp": "2026-06-09T23:15:00Z",
      "transaction_id": "tx_cw_984521034_prod",
      "service": "stratus-ledger-gateway",
      "environment": "production",
      "error_payload": {
        "component": "EVM-Bridge-Client",
        "http_status": 504,
        "error_code": "CW_ERR_BLOCKCHAIN_TIMEOUT",
        "message": (
              "Gateway timeout when broadcasting transaction "
              "payload to Stratus node."
            ),
        "network_details": {
          "target_host": "rpc.stratus.cloudwalk.io",
          "latency_ms": 15000,
          "retries_attempted": 3
        },
        "raw_trace": "Panic: connection reset by peer at runtime.rs:142"
      }
    }

    payload = IncomingLogPayload(**valid_data)
    assert payload.transaction_id == "tx_cw_984521034_prod"
    assert payload.error_payload.http_status == 504
    assert payload.error_payload.network_details.retries_attempted == 3


def test_invalid_incoming_log_payload_missing_field():
    """Test that omitting a required field raises a validation error."""
    invalid_data = {
      "timestamp": "2026-06-09T23:15:00Z",
      "transaction_id": "tx_cw_984521034_prod",
      # "service" is missing
      "environment": "production",
      "error_payload": {
        "component": "EVM-Bridge-Client",
        "http_status": 504,
        "error_code": "CW_ERR_BLOCKCHAIN_TIMEOUT",
        "message": "Timeout",
        "network_details": {
          "target_host": "rpc.stratus.cloudwalk.io",
          "latency_ms": 15000,
          "retries_attempted": 3
        },
        "raw_trace": "Panic"
      }
    }

    with pytest.raises(ValidationError):
        IncomingLogPayload(**invalid_data)


def test_valid_known_error_manual_entry():
    """Test schema instantiation for a Knowledge Base manual entry."""
    valid_data = {
        "error_code": "CW_ERR_BLOCKCHAIN_TIMEOUT",
        "technical_description": "RPC node failed to respond in time.",
        "root_cause": "Network congestion or node offline.",
        "action_plan": [
            "Check node status.",
            "Restart node or fallback to secondary RPC.",
        ],
        "risk_level": "HIGH"
    }
    entry = KnownErrorManualEntry(**valid_data)
    assert entry.error_code == "CW_ERR_BLOCKCHAIN_TIMEOUT"
