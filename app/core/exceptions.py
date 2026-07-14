import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

_DEPENDENCY_FAILURE_MARKERS = (
    "chromadb",
    "<html",
    "<!doctype",
    "connect",
    "timed out",
    "timeout",
    "unavailable",
)


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


def classify_error(exc: Exception, max_length: int = 300) -> dict:
    """
    Classifies a pipeline exception for reporting, returning:
      - "type": a short machine-readable tag the frontend can branch on
      - "message": a short, human-readable message safe to display

    `type == "dependency_unavailable"` flags failures that look like a
    transient upstream outage - most commonly ChromaDB's free-tier
    instance still waking up from a cold start (its client can surface a
    raw HTML error page, e.g. Render's own 502 page, as the exception
    text; our own connection-failure message also gets tagged here).
    The frontend uses this to explain *why* it failed instead of a
    generic error, and to decide whether it's safe to auto-retry.

    Anything else is tagged "unknown" and passed through (truncated) as
    the message, since it's more likely an actual application bug worth
    seeing as-is rather than retrying blindly.
    """
    raw = str(exc)
    lowered = raw.lower()
    looks_like_dependency_failure = (
        any(marker in lowered for marker in _DEPENDENCY_FAILURE_MARKERS)
        or len(raw) > max_length
    )

    if looks_like_dependency_failure:
        return {
            "type": "dependency_unavailable",
            "message": (
                "ChromaDB didn't respond in time. This usually means its "
                "free-tier instance is waking up from inactivity, which "
                "can take up to a minute. Please try again shortly."
            ),
        }

    return {"type": "unknown", "message": raw[:max_length]}


def sanitize_error_message(exc: Exception, max_length: int = 300) -> str:
    """Backwards-compatible wrapper around classify_error()."""
    return classify_error(exc, max_length)["message"]
