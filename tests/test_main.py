from src.main import main


def test_help_returns_success():
    assert main(["--help"]) == 0


def test_unexpected_arguments_return_config_error():
    assert main(["unexpected"]) == 2


def test_missing_required_env_returns_config_error(monkeypatch):
    monkeypatch.delenv("RAW_BUCKET", raising=False)
    monkeypatch.delenv("OUTPUT_BUCKET", raising=False)

    assert main([]) == 2
