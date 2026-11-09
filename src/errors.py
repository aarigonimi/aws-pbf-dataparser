from __future__ import annotations


class OsmPipelineError(Exception):
    """Base class for expected pipeline failures.

    ``exit_code`` is used by the CLI so AWS Batch can distinguish
    non-retryable failures from transient ones.
    """

    exit_code = 1


class ConfigError(OsmPipelineError):
    """Invalid or missing configuration (non-retryable)."""

    exit_code = 2


class InputError(OsmPipelineError):
    """The input PBF is missing, empty, or malformed (non-retryable)."""

    exit_code = 3


class OutputConflictError(OsmPipelineError):
    """Output already exists and overwrite behaviour forbids replacing it."""

    exit_code = 4


class AccessDeniedError(OsmPipelineError):
    """An AWS authorization failure that should not be retried."""

    exit_code = 5


class TransientError(OsmPipelineError):
    """A failure that is likely to succeed on retry (S3/network)."""

    exit_code = 75


class JobCancelled(OsmPipelineError):
    """The job received SIGTERM/SIGINT (e.g. Spot interruption).

    Treated as retryable so AWS Batch can reschedule the work.
    """

    exit_code = 75
