from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class NetworkDetails(BaseModel):
    """Network metrics and context for the transaction failure."""
    target_host: str = Field(..., description="The hostname or IP of the target service.")
    latency_ms: int = Field(..., description="Latency in milliseconds.")
    retries_attempted: int = Field(..., description="Number of retries attempted before failure.")


class ErrorPayload(BaseModel):
    """Detailed error information extracted from the source system."""
    component: str = Field(..., description="The internal component where the error originated.")
    http_status: int = Field(..., description="HTTP status code associated with the error.")
    error_code: str = Field(..., description="Internal error code (e.g., CW_ERR_BLOCKCHAIN_TIMEOUT).")
    message: str = Field(..., description="Human-readable error message.")
    network_details: NetworkDetails
    raw_trace: str = Field(..., description="Raw stack trace or panic message.")


class IncomingLogPayload(BaseModel):
    """
    Strict validation schema for incoming transaction failure logs.
    This is the primary entry point for the triage pipeline.
    """
    timestamp: datetime = Field(..., description="ISO 8601 timestamp of the error.")
    transaction_id: str = Field(..., description="Unique identifier for the transaction.")
    service: str = Field(..., description="The name of the service reporting the error.")
    environment: str = Field(..., description="Deployment environment (e.g., production, staging).")
    error_payload: ErrorPayload


class KnownErrorManualEntry(BaseModel):
    """
    Schema representing a single entry in the Known Errors Manual.
    Used for embedding into the Vector DB during Phase 2.
    """
    error_code: str = Field(..., description="The exact error code to match against incoming logs.")
    technical_description: str = Field(..., description="Detailed technical explanation of the error.")
    root_cause: str = Field(..., description="Common root causes for this error.")
    action_plan: str = Field(..., description="Step-by-step resolution or mitigation plan.")
    risk_level: str = Field(..., description="Risk level (e.g., CRITICAL, HIGH, MEDIUM, LOW).")
