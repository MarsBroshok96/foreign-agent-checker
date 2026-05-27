from typer.testing import CliRunner

from fa_checker.cli import app


def test_cli_help_works() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Run the scaffolded checker" in result.output


def test_cli_runs_with_placeholder_stages() -> None:
    result = CliRunner().invoke(app, ["https://www.rambler.ru/example"])

    assert result.exit_code == 0
    assert "Planned pipeline stages" in result.output
    assert "Load Rambler article" in result.output
    assert "Status:" in result.output
    assert "no_match" in result.output
    assert "Scaffold is ready" in result.output
