from __future__ import annotations

import logging
import sys

_CONFIGURED = False


def configure_logging(level: str = "INFO", run_id: str | None = None) -> None:
    """Configure a single stdout logger suitable for AWS Batch / CloudWatch.

    Docker and AWS Batch capture stdout/stderr, so we intentionally do not
    write log files inside the container.
    """

    global _CONFIGURED

    root = logging.getLogger()
    root.setLevel(level.upper())

    if _CONFIGURED:
        for handler in root.handlers:
            handler.setLevel(level.upper())
        return

    handler = logging.StreamHandler(stream=sys.stdout)
    fmt = "%(asctime)s %(levelname)s %(name)s"
    if run_id:
        fmt += f" run_id={run_id}"
    fmt += " %(message)s"
    handler.setFormatter(logging.Formatter(fmt))
    handler.setLevel(level.upper())

    root.addHandler(handler)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    _CONFIGURED = True
