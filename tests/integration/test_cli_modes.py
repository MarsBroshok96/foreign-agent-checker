import json
from datetime import UTC, datetime
from pathlib import Path

from openpyxl import Workbook
from typer.testing import CliRunner

from fa_checker import cli
from fa_checker.cli import app
from fa_checker.domain.enums import EntityType, ReportStatus
from fa_checker.domain.models import Article, CheckReport, RegistryEntry


def make_article(text: str | None = None) -> Article:
    return Article(
        url="https://www.rambler.ru/news/example",
        source_domain="www.rambler.ru",
        title="Test article",
        author="Reporter",
        text=text or "Илья Варламов прокомментировал ситуацию.",
    )


def write_registry_xlsx(path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["registry_id", "full_name", "entity_type", "aliases"])
    sheet.append(["1", "Варламов Илья Александрович", "person", "Илья Варламов"])
    workbook.save(path)


def make_agentic_report() -> CheckReport:
    return CheckReport(
        article_url="https://www.rambler.ru/news/example",
        article_title="Test article",
        article_author="Reporter",
        checked_at=datetime.now(UTC),
        registry_snapshot_date=None,
        status=ReportStatus.NO_MATCH,
        findings=[],
        limitations=["Bounded LLM review applied to weak candidates."],
    )


def make_registry_entry() -> RegistryEntry:
    return RegistryEntry(
        registry_id="1",
        full_name="Варламов Илья Александрович",
        entity_type=EntityType.PERSON,
        normalized_name="варламов илья александрович",
        registry_source_url="https://minjust.gov.ru/registry",
    )


def test_cli_deterministic_mode_uses_deterministic_pipeline(monkeypatch, tmp_path) -> None:
    registry_path = tmp_path / "registry.xlsx"
    write_registry_xlsx(registry_path)
    monkeypatch.setattr(cli, "load_rambler_article", lambda url: make_article())

    result = CliRunner().invoke(
        app,
        [
            "https://www.rambler.ru/news/example",
            "--mode",
            "deterministic",
            "--registry-path",
            str(registry_path),
        ],
    )

    assert result.exit_code == 0
    assert "# Проверка статьи на упоминание иностранных агентов" in result.output
    assert "Варламов Илья Александрович" in result.output


def test_cli_default_mode_is_deterministic(monkeypatch, tmp_path) -> None:
    registry_path = tmp_path / "registry.xlsx"
    write_registry_xlsx(registry_path)
    monkeypatch.setattr(cli, "load_rambler_article", lambda url: make_article())

    def fail_agentic_review(*args, **kwargs):
        raise AssertionError("Agentic review should not run by default")

    monkeypatch.setattr(cli, "run_agentic_review_check", fail_agentic_review)

    result = CliRunner().invoke(
        app,
        [
            "https://www.rambler.ru/news/example",
            "--registry-path",
            str(registry_path),
        ],
    )

    assert result.exit_code == 0
    assert "Варламов Илья Александрович" in result.output


def test_cli_agentic_mode_uses_bounded_review_pipeline(monkeypatch, tmp_path) -> None:
    registry_path = tmp_path / "registry.xlsx"
    context_profiles_path = tmp_path / "profiles.json"
    context_profiles_path.write_text('{"profiles": []}', encoding="utf-8")
    write_registry_xlsx(registry_path)
    monkeypatch.setattr(cli, "load_rambler_article", lambda url: make_article())
    monkeypatch.setattr(
        cli,
        "run_agentic_review_check",
        lambda *args, **kwargs: make_agentic_report(),
    )

    result = CliRunner().invoke(
        app,
        [
            "https://www.rambler.ru/news/example",
            "--mode",
            "agentic",
            "--registry-path",
            str(registry_path),
            "--context-profiles-path",
            str(context_profiles_path),
        ],
    )

    assert result.exit_code == 0
    assert "Bounded LLM review applied to weak candidates." in result.output


def test_cli_agentic_mode_loads_context_profiles(monkeypatch, tmp_path) -> None:
    registry_path = tmp_path / "registry.xlsx"
    context_profiles_path = tmp_path / "profiles.json"
    write_registry_xlsx(registry_path)
    calls = {}
    profiles = []
    monkeypatch.setattr(cli, "load_rambler_article", lambda url: make_article())

    def fake_load_context_profiles(path):
        calls["path"] = path
        return profiles

    def fake_run_agentic_review_check(article, registry_entries, context_profiles=None):
        calls["context_profiles"] = context_profiles
        return make_agentic_report()

    monkeypatch.setattr(cli, "load_context_profiles", fake_load_context_profiles)
    monkeypatch.setattr(cli, "run_agentic_review_check", fake_run_agentic_review_check)

    result = CliRunner().invoke(
        app,
        [
            "https://www.rambler.ru/news/example",
            "--mode",
            "agentic",
            "--registry-path",
            str(registry_path),
            "--context-profiles-path",
            str(context_profiles_path),
        ],
    )

    assert result.exit_code == 0
    assert calls["path"] == context_profiles_path
    assert calls["context_profiles"] is profiles


def test_cli_agentic_mode_uses_enriched_context_profiles_by_default(
    monkeypatch,
    tmp_path,
) -> None:
    registry_path = tmp_path / "registry.xlsx"
    write_registry_xlsx(registry_path)
    calls = {}
    profiles = []
    monkeypatch.setattr(cli, "load_rambler_article", lambda url: make_article())

    def fake_load_context_profiles(path):
        calls["path"] = path
        return profiles

    def fake_run_agentic_review_check(article, registry_entries, context_profiles=None):
        calls["context_profiles"] = context_profiles
        return make_agentic_report()

    monkeypatch.setattr(cli, "load_context_profiles", fake_load_context_profiles)
    monkeypatch.setattr(cli, "run_agentic_review_check", fake_run_agentic_review_check)

    result = CliRunner().invoke(
        app,
        [
            "https://www.rambler.ru/news/example",
            "--mode",
            "agentic",
            "--registry-path",
            str(registry_path),
        ],
    )

    assert result.exit_code == 0
    assert calls["path"] == Path("data/context/context_profiles.json")
    assert calls["context_profiles"] is profiles


def test_cli_json_output_works_in_deterministic_mode(monkeypatch, tmp_path) -> None:
    registry_path = tmp_path / "registry.xlsx"
    write_registry_xlsx(registry_path)
    monkeypatch.setattr(cli, "load_rambler_article", lambda url: make_article())

    result = CliRunner().invoke(
        app,
        [
            "https://www.rambler.ru/news/example",
            "--mode",
            "deterministic",
            "--registry-path",
            str(registry_path),
            "--output-format",
            "json",
        ],
    )

    assert result.exit_code == 0
    parsed = json.loads(result.stdout)
    assert parsed["status"] == "confirmed_match_found"


def test_cli_json_output_works_in_agentic_mode(monkeypatch, tmp_path) -> None:
    registry_path = tmp_path / "registry.xlsx"
    write_registry_xlsx(registry_path)
    monkeypatch.setattr(cli, "load_rambler_article", lambda url: make_article())
    monkeypatch.setattr(
        cli,
        "run_agentic_review_check",
        lambda *args, **kwargs: make_agentic_report(),
    )

    result = CliRunner().invoke(
        app,
        [
            "https://www.rambler.ru/news/example",
            "--mode",
            "agentic",
            "--registry-path",
            str(registry_path),
            "--output-format",
            "json",
        ],
    )

    assert result.exit_code == 0
    parsed = json.loads(result.stdout)
    assert parsed["status"] == "no_match"


def test_cli_rejects_invalid_mode() -> None:
    result = CliRunner().invoke(
        app,
        ["https://www.rambler.ru/news/example", "--mode", "invalid"],
    )

    assert result.exit_code == 1
    assert "--mode must be" in result.output


def test_cli_missing_context_profiles_file_does_not_crash(monkeypatch, tmp_path) -> None:
    registry_path = tmp_path / "registry.xlsx"
    write_registry_xlsx(registry_path)
    monkeypatch.setattr(cli, "load_rambler_article", lambda url: make_article())

    def fake_run_agentic_review_check(article, registry_entries, context_profiles=None):
        assert context_profiles == []
        return make_agentic_report()

    monkeypatch.setattr(cli, "run_agentic_review_check", fake_run_agentic_review_check)

    result = CliRunner().invoke(
        app,
        [
            "https://www.rambler.ru/news/example",
            "--mode",
            "agentic",
            "--registry-path",
            str(registry_path),
            "--context-profiles-path",
            str(tmp_path / "missing.json"),
        ],
    )

    assert result.exit_code == 0


def test_cli_deterministic_mode_does_not_call_agentic_review(monkeypatch, tmp_path) -> None:
    registry_path = tmp_path / "registry.xlsx"
    write_registry_xlsx(registry_path)
    monkeypatch.setattr(cli, "load_rambler_article", lambda url: make_article())

    def fail_agentic_review(*args, **kwargs):
        raise AssertionError("Agentic review should not run in deterministic mode")

    monkeypatch.setattr(cli, "run_agentic_review_check", fail_agentic_review)

    result = CliRunner().invoke(
        app,
        [
            "https://www.rambler.ru/news/example",
            "--mode",
            "deterministic",
            "--registry-path",
            str(registry_path),
        ],
    )

    assert result.exit_code == 0
