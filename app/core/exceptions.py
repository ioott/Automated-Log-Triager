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


def sanitize_error_message(exc: Exception, max_length: int = 300) -> str:
    """
    Returns a short, user-facing message for an exception, guarding
    against upstream HTTP clients (e.g. the ChromaDB client) occasionally
    surfacing a raw HTML error page as the exception's string
    representation.

    This happens, for example, when a dependency is hosted on a
    free-tier PaaS instance that spins down after inactivity: the
    platform's own proxy returns an HTML error page while the instance
    wakes up, and that HTML ends up as `str(exc)`. Without this guard,
    that raw HTML gets stored in reports and rendered as-is by the
    frontend.
    """
    raw = str(exc)
    looks_like_html = "<html" in raw.lower() or "<!doctype" in raw.lower()
    if looks_like_html or len(raw) > max_length:
        return (
            "A downstream dependency (likely ChromaDB) returned an "
            "unexpected response instead of failing cleanly. This "
            "commonly happens when a free-tier instance is waking up "
            "from inactivity. Please retry in a few seconds."
        )
    return raw
