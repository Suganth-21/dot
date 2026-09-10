"""Minimal structured logging. No framework — stdlib `logging` with a
formatter that always prints a request id (falls back to "-" for log lines
outside a request, e.g. startup)."""
import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s level=%(levelname)s logger=%(name)s request_id=%(request_id)s message=%(message)s",
        defaults={"request_id": "-"},
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
