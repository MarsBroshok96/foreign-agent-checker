import json

import pytest
from openpyxl import Workbook
from typer.testing import CliRunner

from fa_checker import cli
from fa_checker.article.extractor import ArticleExtractionError
from fa_checker.cli import app
from fa_checker.domain.enums import EntityType
from fa_checker.domain.models import Article, RegistryEntry


def make_article(text: str | None = None) -> Article:
    return Article(
        url="https://www.rambler.ru/news/example",
        source_domain="www.rambler.ru",
        title="Test article",
        author="Reporter",
        text=text or "Илья Варламов, признан иностранным агентом, прокомментировал ситуацию.",
        links=[],
    )


def write_registry_xlsx(path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["registry_id", "full_name", "entity_type"])
    sheet.append(["1", "Варламов Илья Александрович", "person"])
    workbook.save(path)


def make_registry_entry() -> RegistryEntry:
    return RegistryEntry(
        registry_id="1",
        full_name="Варламов Илья Александрович",
        entity_type=EntityType.PERSON,
        normalized_name="варламов илья александрович",
        registry_source_url="https://minjust.gov.ru/registry",
    )


def test_cli_markdown_path_with_local_registry_file(monkeypatch, tmp_path) -> None:
    registry_path = tmp_path / "registry.xlsx"
    write_registry_xlsx(registry_path)
    monkeypatch.setattr(cli, "load_rambler_article", lambda url: make_article())

    result = CliRunner().invoke(
        app,
        [
            "https://www.rambler.ru/news/example",
            "--registry-path",
            str(registry_path),
        ],
    )

    assert result.exit_code == 0
    assert "# Проверка статьи на упоминание иностранных агентов" in result.output
    assert "Варламов Илья Александрович" in result.output
    assert "Найдены совпадения с реестром." in result.output


def test_cli_json_path_with_local_registry_file(monkeypatch, tmp_path) -> None:
    registry_path = tmp_path / "registry.xlsx"
    write_registry_xlsx(registry_path)
    monkeypatch.setattr(cli, "load_rambler_article", lambda url: make_article())

    result = CliRunner().invoke(
        app,
        [
            "https://www.rambler.ru/news/example",
            "--registry-path",
            str(registry_path),
            "--output-format",
            "json",
        ],
    )

    assert result.exit_code == 0
    parsed = json.loads(result.stdout)
    assert parsed["status"] == "confirmed_match_found"
    assert parsed["findings"][0]["entity_name"] == "Варламов Илья Александрович"


def test_cli_uses_cached_minjust_loader_when_registry_path_missing(monkeypatch) -> None:
    calls = {}
    monkeypatch.setattr(cli, "load_rambler_article", lambda url: make_article())

    def fake_load_minjust_registry_entries(**kwargs):
        calls.update(kwargs)
        return [make_registry_entry()]

    monkeypatch.setattr(
        cli,
        "load_minjust_registry_entries",
        fake_load_minjust_registry_entries,
    )

    result = CliRunner().invoke(app, ["https://www.rambler.ru/news/example"])

    assert result.exit_code == 0
    assert calls["registry_page_url"].startswith("https://minjust.gov.ru/")
    assert calls["force_refresh"] is False


def test_cli_force_refresh_flag_is_passed_to_cached_loader(monkeypatch) -> None:
    calls = {}
    monkeypatch.setattr(cli, "load_rambler_article", lambda url: make_article())

    def fake_load_minjust_registry_entries(**kwargs):
        calls.update(kwargs)
        return [make_registry_entry()]

    monkeypatch.setattr(
        cli,
        "load_minjust_registry_entries",
        fake_load_minjust_registry_entries,
    )

    result = CliRunner().invoke(
        app,
        ["https://www.rambler.ru/news/example", "--force-refresh-registry"],
    )

    assert result.exit_code == 0
    assert calls["force_refresh"] is True


@pytest.mark.parametrize(
    "error",
    [
        ValueError("URL must belong to rambler.ru"),
        ArticleExtractionError("Could not extract article text"),
    ],
)
def test_cli_loader_error_exits_nonzero(monkeypatch, error) -> None:
    def fake_load_rambler_article(url):
        raise error

    monkeypatch.setattr(cli, "load_rambler_article", fake_load_rambler_article)

    result = CliRunner().invoke(app, ["https://www.rambler.ru/news/example"])

    assert result.exit_code == 1
    assert "Error:" in result.output


def test_cli_prompts_for_url_when_argument_missing(monkeypatch) -> None:
    calls = {}

    def fake_load_rambler_article(url):
        calls["url"] = url
        return make_article()

    monkeypatch.setattr(cli, "load_rambler_article", fake_load_rambler_article)
    monkeypatch.setattr(
        cli,
        "load_minjust_registry_entries",
        lambda **kwargs: [make_registry_entry()],
    )

    result = CliRunner().invoke(app, input="https://www.rambler.ru/news/example\n")

    assert result.exit_code == 0
    assert calls["url"] == "https://www.rambler.ru/news/example"
    assert "Варламов Илья Александрович" in result.output
