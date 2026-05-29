from typer.testing import CliRunner

from fa_checker.cli import app


def test_cli_help_works() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Run article check" in result.output


def test_cli_rejects_invalid_output_format() -> None:
    result = CliRunner().invoke(
        app,
        ["https://www.rambler.ru/example", "--output-format", "xml"],
    )

    assert result.exit_code == 1
    assert "--output-format must be" in result.output
