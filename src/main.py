from __future__ import annotations

import logging
import os
import signal
import sys
from types import FrameType

from src.config import JobConfig, env_for_raw_key
from src.errors import OsmPipelineError
from src.logging_utils import configure_logging
from src.pipeline import CancelToken, run_pipeline

logger = logging.getLogger(__name__)

USAGE = """Usage: python -m src.main [options]

The job is configured through environment variables, with optional command-line
overrides for the values supplied by EventBridge through AWS Batch parameters:

  --raw-key KEY           override RAW_KEY (decoded and validated; derives
                          REGION_NAME and YMD from the key layout)
  --raw-bucket BUCKET     override RAW_BUCKET
  --region-name NAME      override REGION_NAME
  --ymd YYYYMMDD          override YMD
  --overwrite MODE        override OVERWRITE (error | skip | replace)

Environment variables:

  RAW_BUCKET              (required) bucket containing the PBF extract
  OUTPUT_BUCKET           (required) bucket receiving Parquet output
  RAW_KEY                 explicit input key, region=<name>/yyyy/mm/dd/<file>.osm.pbf
  REGION_NAME             logical region name (required without RAW_KEY;
                          overrides the region derived from RAW_KEY)
  RUN_ID                  unique run identifier (default: derived from
                          AWS_BATCH_JOB_ID and AWS_BATCH_JOB_ATTEMPT)
  YMD                     partition date YYYYMMDD (required without RAW_KEY;
                          overrides the date derived from RAW_KEY)
  OUTPUT_PREFIX           curated prefix (default: curated)
  MODE                    all | nodes | ways | relations (default: all)
  OVERWRITE               error | skip | replace (default: error)
  PARQUET_COMPRESSION     snappy | gzip | brotli | lz4 | zstd | none
  INCLUDE_WAY_GEOMETRY    true/false (default: true)
  MAX_RECORDS_PER_FILE    records per part file (default: 250000)
  ROW_GROUP_SIZE          rows per Parquet row group (default: 100000)
  LOG_LEVEL               DEBUG | INFO | WARNING | ERROR (default: INFO)
"""

_CLI_ENV_FLAGS = {
    "--raw-key": "RAW_KEY",
    "--raw-bucket": "RAW_BUCKET",
    "--region-name": "REGION_NAME",
    "--ymd": "YMD",
    "--overwrite": "OVERWRITE",
}


def _parse_cli(args: list[str]) -> tuple[dict[str, str] | None, int]:
    if any(arg in {"-h", "--help"} for arg in args):
        print(USAGE)
        return None, 0

    overrides: dict[str, str] = {}
    index = 0
    while index < len(args):
        arg = args[index]
        env_name = _CLI_ENV_FLAGS.get(arg)
        if env_name is None:
            print(f"Unexpected arguments: {args}\n\n{USAGE}", file=sys.stderr)
            return None, 2
        if index + 1 >= len(args):
            print(f"Missing value for {arg}\n\n{USAGE}", file=sys.stderr)
            return None, 2
        value = args[index + 1].strip()
        if value:
            overrides[env_name] = value
        index += 2
    return overrides, 0


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
    overrides, exit_code = _parse_cli(args)
    if overrides is None:
        return exit_code

    env = dict(os.environ)
    configure_logging(env.get("LOG_LEVEL", "INFO"))
    token = CancelToken()
    _install_signal_handlers(token)

    try:
        raw_key_override = overrides.pop("RAW_KEY", None)
        if raw_key_override is not None:
            env = env_for_raw_key(raw_key_override, env)
        env.update(overrides)
        config = JobConfig.from_env(env)
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
