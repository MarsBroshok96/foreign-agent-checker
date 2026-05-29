from datetime import date

from fa_checker.domain.enums import (
    ConfidenceLevel,
    EntityType,
    FindingStatus,
    LabelStatus,
    ReportStatus,
    RiskLevel,
)
from fa_checker.domain.models import Article, RegistryEntry
from fa_checker.pipeline import run_offline_check


def make_article(text: str) -> Article:
    return Article(
        url="https://www.rambler.ru/example",
        source_domain="www.rambler.ru",
        title="Example",
        author="Reporter",
        text=text,
    )


def make_entry(
    full_name: str,
    entity_type: EntityType = EntityType.PERSON,
    aliases: list[str] | None = None,
    snapshot_date: date | None = None,
) -> RegistryEntry:
    return RegistryEntry(
        registry_id=full_name,
        full_name=full_name,
        entity_type=entity_type,
        normalized_name=full_name.lower(),
        aliases=aliases or [],
        registry_source_url="https://minjust.gov.ru/registry",
        registry_snapshot_date=snapshot_date,
    )


def test_run_offline_check_returns_no_match_when_no_entities_found() -> None:
    report = run_offline_check(
        make_article("В статье нет совпадений с реестром."),
        [make_entry("Варламов Илья Александрович")],
    )

    assert report.status == ReportStatus.NO_MATCH
    assert report.findings == []


def test_run_offline_check_scores_strong_match_without_label_as_high_risk() -> None:
    report = run_offline_check(
        make_article("Илья Варламов прокомментировал ситуацию."),
        [make_entry("Варламов Илья Александрович")],
    )

    assert report.status == ReportStatus.CONFIRMED_MATCH_FOUND
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.status == FindingStatus.CONFIRMED
    assert finding.risk_level == RiskLevel.HIGH
    assert finding.label_status == LabelStatus.ABSENT
    assert finding.requires_human_review is True
    assert report.processing_summary is not None
    assert report.processing_summary.mode == "deterministic"
    assert report.processing_summary.deterministic_strong_candidates == 1
    assert report.processing_summary.final_requires_human_review == 1


def test_run_offline_check_scores_strong_match_with_nearby_label_as_low_risk() -> None:
    report = run_offline_check(
        make_article(
            "Илья Варламов, признан иностранным агентом, прокомментировал ситуацию."
        ),
        [make_entry("Варламов Илья Александрович")],
    )

    assert report.status == ReportStatus.CONFIRMED_MATCH_FOUND
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.risk_level == RiskLevel.LOW
    assert finding.label_status == LabelStatus.PRESENT
    assert finding.requires_human_review is False


def test_run_offline_check_scores_weak_surname_only_match_as_potential() -> None:
    report = run_offline_check(
        make_article("Варламов прокомментировал ситуацию."),
        [make_entry("Варламов Илья Александрович")],
    )

    assert report.status == ReportStatus.POTENTIAL_MATCH_FOUND
    assert len(report.findings) == 1
    assert report.findings[0].status == FindingStatus.UNCERTAIN
    assert report.findings[0].requires_human_review is True


def test_run_offline_check_keeps_one_token_project_alias_as_weak_potential() -> None:
    report = run_offline_check(
        make_article("После дождя случилось событие."),
        [make_entry("Проект «После»", entity_type=EntityType.PROJECT, aliases=["После"])],
    )

    assert report.status == ReportStatus.POTENTIAL_MATCH_FOUND
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.status == FindingStatus.UNCERTAIN
    assert finding.risk_level == RiskLevel.MEDIUM
    assert finding.confidence_level == ConfidenceLevel.LOW
    assert finding.requires_human_review is True


def test_run_offline_check_carries_context_evidence_for_weak_match() -> None:
    report = run_offline_check(
        make_article("Белый дом выступил с заявлением после встречи."),
        [make_entry("Белый Руслан Викторович")],
    )

    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.status == FindingStatus.UNCERTAIN
    assert finding.evidence
    evidence_text = finding.evidence[0].text
    assert len(evidence_text) > len("белый")
    assert "дом" in evidence_text.lower()


def test_run_offline_check_handles_multiple_findings() -> None:
    report = run_offline_check(
        make_article("Илья Варламов и После упоминаются в одном материале."),
        [
            make_entry("Варламов Илья Александрович"),
            make_entry("Проект «После»", entity_type=EntityType.PROJECT, aliases=["После"]),
        ],
    )

    assert report.status == ReportStatus.CONFIRMED_MATCH_FOUND
    assert len(report.findings) == 2
    assert [finding.entity_name for finding in report.findings] == [
        "Варламов Илья Александрович",
        "Проект «После»",
    ]


def test_run_offline_check_propagates_registry_snapshot_date() -> None:
    snapshot = date(2026, 5, 22)

    report = run_offline_check(
        make_article("Илья Варламов прокомментировал ситуацию."),
        [make_entry("Варламов Илья Александрович", snapshot_date=snapshot)],
    )

    assert report.registry_snapshot_date == snapshot


def test_run_offline_check_handles_empty_registry() -> None:
    report = run_offline_check(
        make_article("Илья Варламов прокомментировал ситуацию."),
        [],
    )

    assert report.status == ReportStatus.NO_MATCH
    assert report.findings == []
    assert report.registry_snapshot_date is None
