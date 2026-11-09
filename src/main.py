from __future__ import annotations

import logging
import os
import signal
import sys
from types import FrameType

from src.config import JobConfig
from src.errors import OsmPipelineError
from src.logging_utils import configure_logging
from src.pipeline import CancelToken, run_pipeline

logger = logging.getLogger(__name__)

USAGE = """Usage: python -m src.main

The job is configured entirely through environment variables:

  RAW_BUCKET              (required) bucket containing the PBF extract
  OUTPUT_BUCKET           (required) bucket receiving Parquet output
  RAW_KEY                 explicit input key (default: region=/ymd= layout)
  REGION_NAME             logical region name (default: monaco)
  RUN_ID                  unique run identifier (default: local-run)
  YMD                     partition date YYYYMMDD (default: today or from RAW_KEY)
  OUTPUT_PREFIX           curated prefix (default: curated)
  MODE                    all | nodes | ways | relations (default: all)
  OVERWRITE               error | skip | replace (default: error)
  PARQUET_COMPRESSION     snappy | gzip | brotli | lz4 | zstd | none
  INCLUDE_WAY_GEOMETRY    true/false (default: false)
  MAX_RECORDS_PER_FILE    records per part file (default: 250000)
  ROW_GROUP_SIZE          rows per Parquet row group (default: 100000)
  LOG_LEVEL               DEBUG | INFO | WARNING | ERROR (default: INFO)
"""


def _install_signal_handlers(token: CancelToken) -> None:
    def _handle(signum: int, frame: FrameType | None) -> None:
        logger.warning("Received signal %s; requesting graceful cancellation.", signum)
        token.cancel(signum, frame)

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _handle)
        except (ValueError, OSError):  # pragma: no cover - non-main thread
            logger.debug("Could not install handler for signal %s", sig)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in {"-h", "--help"}:
        print(USAGE)
        return 0
    if args:
        print(f"Unexpected arguments: {args}\n\n{USAGE}", file=sys.stderr)
        return 2

    configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
    token = CancelToken()
    _install_signal_handlers(token)

    try:
        config = JobConfig.from_env()
        configure_logging(config.log_level, config.run_id)
        result = run_pipeline(config, cancel_token=token)
        if result.skipped:
            logger.info(
                "Run skipped; completed output already exists for region=%s ymd=%s",
                result.region,
                result.ymd,
            )
        else:
            logger.info(
                "Pipeline finished: status=%s records=%s output_bytes=%d",
                result.status,
                result.record_counts,
                result.total_output_bytes,
            )
        return 0
    except OsmPipelineError as exc:
        logger.error("%s: %s", type(exc).__name__, exc)
        return exc.exit_code
    except Exception:  # pragma: no cover - unexpected failures
        logger.exception("Unexpected pipeline failure")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
