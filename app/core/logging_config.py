import json
import logging


class JsonFormatter(logging.Formatter):
    """
    Formats log records as a single JSON object per line, safely
    escaping the message via json.dumps instead of naive string
    interpolation.

    The previous setup built the "JSON" manually with an f-string
    (`'"message": "%(message)s"'`). That breaks - and silently truncates
    the visible message - whenever the logged text contains a newline or
    an unescaped quote, which happens whenever an upstream HTTP error
    (e.g. a raw HTML error page from a dependency, or a multi-line
    traceback) ends up embedded in an exception's string representation.
    json.dumps escapes all of that correctly, so the full message is
    always readable in Render's log viewer.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: int = logging.INFO) -> None:
    """Configures the root logger to emit one JSON object per line."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]
