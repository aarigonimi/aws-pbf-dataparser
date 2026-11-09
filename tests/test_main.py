import signal

import pytest

from src.errors import (
    AccessDeniedError,
    ConfigError,
    InputError,
    JobCancelled,
    OutputConflictError,
    TransientError,
)
from src.main import _install_signal_handlers, main
from src.pipeline import CancelToken


def test_help_returns_success():
    assert main(["--help"]) == 0


def test_unexpected_arguments_return_config_error():
    assert main(["unexpected"]) == 2


def test_missing_required_env_returns_config_error(monkeypatch):
    monkeypatch.delenv("RAW_BUCKET", raising=False)
    monkeypatch.delenv("OUTPUT_BUCKET", raising=False)

    assert main([]) == 2


@pytest.mark.parametrize(
    ("error", "exit_code"),
    [
        (ConfigError("bad config"), 2),
        (InputError("bad input"), 3),
        (OutputConflictError("conflict"), 4),
        (AccessDeniedError("denied"), 5),
        (TransientError("temporary"), 75),
        (JobCancelled("cancelled"), 75),
    ],
)
def test_expected_pipeline_errors_map_to_exit_codes(monkeypatch, error, exit_code):
    monkeypatch.setattr(
        "src.main.run_pipeline", lambda *_args, **_kwargs: (_ for _ in ()).throw(error)
    )
    monkeypatch.setattr(
        "src.main.JobConfig.from_env",
        lambda: type("Config", (), {"log_level": "INFO", "run_id": "test"})(),
    )

    assert main([]) == exit_code


def test_signal_handler_marks_cancel_token(monkeypatch):
    installed = {}

    def register(signum, handler):
        installed[signum] = handler

    monkeypatch.setattr(signal, "signal", register)
    token = CancelToken()
    _install_signal_handlers(token)

    installed[signal.SIGTERM](signal.SIGTERM, None)
    assert token.cancelled
