from fa_checker.domain.enums import EntityType, ReportStatus
from fa_checker.domain.models import Article, RegistryEntry
from fa_checker.pipeline import run_deterministic_analysis, run_offline_check


def make_article(text: str) -> Article:
    return Article(
        url="https://www.rambler.ru/example",
        source_domain="www.rambler.ru",
        text=text,
    )


def make_entry(
    full_name: str,
    entity_type: EntityType = EntityType.PERSON,
    aliases: list[str] | None = None,
) -> RegistryEntry:
    return RegistryEntry(
        full_name=full_name,
        entity_type=entity_type,
        normalized_name=full_name.lower(),
        aliases=aliases or [],
        registry_source_url="https://minjust.gov.ru/registry",
    )


def test_deterministic_analysis_no_matches() -> None:
    analysis = run_deterministic_analysis(
        make_article("В статье нет совпадений."),
        [make_entry("Варламов Илья Александрович")],
    )

    assert analysis.candidates == []
    assert analysis.findings == []
    assert analysis.strong_candidates_count == 0
    assert analysis.weak_candidates_count == 0
    assert analysis.requires_agent_review is False
    assert analysis.base_report.status == ReportStatus.NO_MATCH


def test_deterministic_analysis_strong_exact_match() -> None:
    analysis = run_deterministic_analysis(
        make_article("Илья Варламов прокомментировал ситуацию."),
        [make_entry("Варламов Илья Александрович")],
    )

    assert len(analysis.candidates) == 1
    assert analysis.strong_candidates_count == 1
    assert analysis.weak_candidates_count == 0
    assert analysis.confirmed_findings_count == 1
    assert analysis.requires_agent_review is False
    assert analysis.base_report.status == ReportStatus.CONFIRMED_MATCH_FOUND


def test_deterministic_analysis_weak_one_token_match_requires_review() -> None:
    analysis = run_deterministic_analysis(
        make_article("После дождя случилось событие."),
        [make_entry("Проект «После»", entity_type=EntityType.PROJECT, aliases=["После"])],
    )

    assert len(analysis.candidates) == 1
    assert analysis.strong_candidates_count == 0
    assert analysis.weak_candidates_count == 1
    assert analysis.uncertain_findings_count == 1
    assert analysis.requires_agent_review is True
    assert analysis.base_report.status == ReportStatus.POTENTIAL_MATCH_FOUND


def test_run_offline_check_delegates_to_deterministic_analysis_report() -> None:
    article = make_article("Илья Варламов прокомментировал ситуацию.")
    entries = [make_entry("Варламов Илья Александрович")]

    report = run_offline_check(article, entries)
    analysis = run_deterministic_analysis(article, entries)

    assert report.status == analysis.base_report.status
    assert len(report.findings) == len(analysis.base_report.findings)

