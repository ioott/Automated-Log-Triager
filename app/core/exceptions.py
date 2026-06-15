from fastapi import Request, status
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

class TriagePipelineException(Exception):
    """Base exception for custom triage pipeline errors."""
    def __init__(self, message: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catches all unhandled exceptions globally to ensure the API never returns raw HTML traces,
    maintaining structured JSON outputs for clients.
    """
    logger.error(f"Unhandled exception on {request.method} {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal Server Error. Please check the logs."},
    )

async def triage_exception_handler(request: Request, exc: TriagePipelineException) -> JSONResponse:
    """Handles custom domain exceptions gracefully."""
    logger.warning(f"Triage exception: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )
