import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


async def global_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Catches all unhandled exceptions to ensure the API always
    returns structured JSON instead of raw HTML traces."""
    logger.error(
        f"Unhandled exception on {request.method} {request.url}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal Server Error. Please check the logs."},
    )
