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
        lambda *_args, **_kwargs: type("Config", (), {"log_level": "INFO", "run_id": "test"})(),
    )

    assert main([]) == exit_code


def test_cli_overrides_are_applied_before_config(monkeypatch):
    captured = {}

    def fake_from_env(env):
        captured.update(env)
        return type("Config", (), {"log_level": "INFO", "run_id": "test"})()

    result = type(
        "Result",
        (),
        {
            "skipped": False,
            "status": "success",
            "record_counts": {},
            "total_output_bytes": 0,
            "region": "quebec",
            "ymd": "20261108",
        },
    )()
    monkeypatch.setattr("src.main.JobConfig.from_env", fake_from_env)
    monkeypatch.setattr("src.main.run_pipeline", lambda *_args, **_kwargs: result)

    assert (
        main(
            [
                "--raw-key",
                "region=quebec/2026/11/08/quebec-20261108.osm.pbf",
                "--raw-bucket",
                "raw-bucket",
                "--region-name",
                "quebec",
                "--ymd",
                "20261108",
                "--overwrite",
                "skip",
            ]
        )
        == 0
    )
    assert captured["RAW_KEY"] == "region=quebec/2026/11/08/quebec-20261108.osm.pbf"
    assert captured["RAW_BUCKET"] == "raw-bucket"
    assert captured["REGION_NAME"] == "quebec"
    assert captured["YMD"] == "20261108"
    assert captured["OVERWRITE"] == "skip"


def test_empty_cli_value_does_not_override_environment(monkeypatch):
    captured = {}

    def fake_from_env(env):
        captured.update(env)
        return type("Config", (), {"log_level": "INFO", "run_id": "test"})()

    result = type(
        "Result",
        (),
        {
            "skipped": False,
            "status": "success",
            "record_counts": {},
            "total_output_bytes": 0,
            "region": "monaco",
            "ymd": "20261108",
        },
    )()
    monkeypatch.setenv("RAW_KEY", "from-environment")
    monkeypatch.setattr("src.main.JobConfig.from_env", fake_from_env)
    monkeypatch.setattr("src.main.run_pipeline", lambda *_args, **_kwargs: result)

    assert main(["--raw-key", ""]) == 0
    assert captured["RAW_KEY"] == "from-environment"


def test_cli_flag_without_value_returns_config_error():
    assert main(["--raw-key"]) == 2


def test_signal_handler_marks_cancel_token(monkeypatch):
    installed = {}

    def register(signum, handler):
        installed[signum] = handler

    monkeypatch.setattr(signal, "signal", register)
    token = CancelToken()
    _install_signal_handlers(token)

    installed[signal.SIGTERM](signal.SIGTERM, None)
    assert token.cancelled
