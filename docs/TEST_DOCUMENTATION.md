# Testing & API Documentation

## Overview
This document outlines the procedures for testing the **Automated Log Triager & Diagnostic Agent**. 
It includes instructions for running unit tests locally and an API reference for end-to-end (E2E) integration testing.

A complete **Postman Collection** is available in this folder: `docs/postman_collection.json`. You can import this file directly into Postman to test all endpoints.

---

## 1. Automated Unit Tests

The project uses `pytest` to validate core business logic (Data Masking) and structural integrity (Pydantic Schemas).

### Running Tests
To run the test suite locally, ensure you are in the project root and have the virtual environment activated:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. pytest -v
```

### Test Coverage
- **`tests/test_schemas.py`**: Ensures the API strictly rejects malformed incoming logs and enforces the structure of the RAG Knowledge Base entries.
- **`tests/test_masking.py`**: Validates the enterprise Regex engine, proving that IPv4 addresses, Email addresses, and Transaction IDs are successfully scrubbed and replaced with safe tags (e.g., `[MASKED_IP]`) before hitting the LLM.

---

## 2. API Endpoints (E2E Testing)

Ensure the Docker environment is running (`docker compose up -d`) before testing these endpoints.

### 2.1. System Health
- **Endpoint:** `GET /health`
- **Description:** Basic liveness probe.
- **Expected Response (200 OK):**
  ```json
  {
      "status": "ok",
      "environment": "development"
  }
  ```

### 2.2. Ingest Knowledge Base (RAG)
- **Endpoint:** `POST /api/v1/knowledge-base/ingest`
- **Description:** Populates the ChromaDB Vector Store with technical manuals.
- **Payload Example:**
  ```json
  [
      {
          "error_code": "CW_ERR_BLOCKCHAIN_TIMEOUT",
          "technical_description": "Gateway timeout when broadcasting transaction payload to Stratus node.",
          "root_cause": "The Stratus node (RPC) took longer than 15 seconds to acknowledge.",
          "action_plan": ["Verify RPC health", "Switch to fallback RPC"],
          "risk_level": "HIGH"
      }
  ]
  ```
- **Expected Response (201 Created):**
  ```json
  {
      "status": "success",
      "inserted_count": 1
  }
  ```

### 2.3. Submit Log for Triage
- **Endpoint:** `POST /api/v1/logs/triage`
- **Description:** The primary entry point. Triggers the async pipeline (Masking -> RAG -> AI Agent).
- **Payload Example (Contains sensitive data for masking validation):**
  ```json
  {
      "timestamp": "2026-06-09T23:15:00Z",
      "transaction_id": "tx_cw_PORTFOLIO_DEMO",
      "service": "stratus-ledger-gateway",
      "environment": "production",
      "error_payload": {
          "component": "EVM-Bridge-Client",
          "http_status": 504,
          "error_code": "CW_ERR_BLOCKCHAIN_TIMEOUT",
          "message": "Gateway timeout from IP 192.168.1.99 and user investor@example.com",
          "network_details": {
              "target_host": "rpc.stratus",
              "latency_ms": 15000,
              "retries_attempted": 3
          },
          "raw_trace": "Panic trace for john.doe@cloudwalk.io."
      }
  }
  ```
- **Expected Response (202 Accepted):**
  ```json
  {
      "status": "accepted",
      "transaction_id": "tx_cw_PORTFOLIO_DEMO",
      "message": "Log accepted for asynchronous triage."
  }
  ```

### 2.4. Fetch Real-time Reports
- **Endpoint:** `GET /api/v1/reports`
- **Description:** Returns the processed diagnoses. Used by the web dashboard for polling.
