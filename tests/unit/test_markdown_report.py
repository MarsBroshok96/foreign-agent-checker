from datetime import UTC, datetime

from fa_checker.domain.enums import (
    ConfidenceLevel,
    EvidenceSource,
    FindingStatus,
    LabelStatus,
    ReportStatus,
    RiskLevel,
)
from fa_checker.domain.models import CheckReport, EvidenceFragment, FinalFinding
from fa_checker.pipeline import run_offline_check
from fa_checker.reporting.markdown_report import report_to_markdown


def make_finding(
    entity_name: str = "Варламов Илья Александрович",
    mention_text: str = "Илья Варламов",
    requires_human_review: bool = True,
) -> FinalFinding:
    return FinalFinding(
        entity_name=entity_name,
        mention_text=mention_text,
        status=FindingStatus.CONFIRMED,
        risk_level=RiskLevel.HIGH,
        confidence_level=ConfidenceLevel.HIGH,
        label_status=LabelStatus.ABSENT,
        requires_human_review=requires_human_review,
        evidence=[
            EvidenceFragment(
                source=EvidenceSource.ARTICLE_TEXT,
                text=f"Фрагмент с упоминанием: {mention_text}",
                start=0,
                end=20,
            )
        ],
        rationale="Strong exact registry match found, but label not found.",
    )


def make_report(
    status: ReportStatus = ReportStatus.NO_MATCH,
    findings: list[FinalFinding] | None = None,
) -> CheckReport:
    return CheckReport(
        article_url="https://www.rambler.ru/example",
        article_title="Тестовая статья",
        article_author="Редакция",
        checked_at=datetime(2026, 5, 28, 12, 30, tzinfo=UTC),
        registry_snapshot_date=None,
        status=status,
        findings=findings or [],
        limitations=["Offline deterministic check only; LLM disambiguation was not applied."],
    )


def test_markdown_no_match_report_contains_metadata_and_limitations() -> None:
    markdown = report_to_markdown(make_report())

    assert "# Проверка статьи на упоминание иностранных агентов" in markdown
    assert "https://www.rambler.ru/example" in markdown
    assert "Совпадения с реестром не выявлены текущей проверкой." in markdown
    assert "## Ограничения" in markdown
    assert "LLM disambiguation was not applied" in markdown


def test_markdown_confirmed_finding_contains_required_fields() -> None:
    markdown = report_to_markdown(
        make_report(
            status=ReportStatus.CONFIRMED_MATCH_FOUND,
            findings=[make_finding()],
        )
    )

    assert "Варламов Илья Александрович" in markdown
    assert "Илья Варламов" in markdown
    assert "Уровень риска: high" in markdown
    assert "Уверенность: high" in markdown
    assert "маркировка не найдена" in markdown
    assert "Strong exact registry match found, but label not found." in markdown
    assert "Фрагмент с упоминанием: Илья Варламов" in markdown


def test_markdown_human_review_wording() -> None:
    markdown = report_to_markdown(
        make_report(
            status=ReportStatus.CONFIRMED_MATCH_FOUND,
            findings=[
                make_finding(
                    entity_name="Первый",
                    mention_text="Первый",
                    requires_human_review=True,
                ),
                make_finding(
                    entity_name="Второй",
                    mention_text="Второй",
                    requires_human_review=False,
                ),
            ],
        )
    )

    assert "Требуется ручная проверка: да" in markdown
    assert "Требуется ручная проверка: нет" in markdown


def test_markdown_multiple_findings_renders_both_and_summary_count() -> None:
    markdown = report_to_markdown(
        make_report(
            status=ReportStatus.CONFIRMED_MATCH_FOUND,
            findings=[
                make_finding(entity_name="Первый", mention_text="Первый"),
                make_finding(entity_name="Второй", mention_text="Второй"),
            ],
        )
    )

    assert "Количество находок: 2" in markdown
    assert "Первый" in markdown
    assert "Второй" in markdown


def test_markdown_uses_cautious_wording() -> None:
    markdown = report_to_markdown(
        make_report(
            status=ReportStatus.CONFIRMED_MATCH_FOUND,
            findings=[make_finding()],
        )
    )

    forbidden_phrases = [
        "legal violation",
        "illegal article",
        "law was violated",
        "нарушение закона",
        "незаконная статья",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in markdown


def test_markdown_renders_context_evidence_from_offline_pipeline() -> None:
    from fa_checker.domain.enums import EntityType
    from fa_checker.domain.models import Article, RegistryEntry

    report = run_offline_check(
        Article(
            url="https://www.rambler.ru/example",
            source_domain="www.rambler.ru",
            text="Белый дом выступил с заявлением после встречи.",
        ),
        [
            RegistryEntry(
                full_name="Белый Руслан Викторович",
                entity_type=EntityType.PERSON,
                normalized_name="белый руслан викторович",
                registry_source_url="https://minjust.gov.ru/registry",
            )
        ],
    )

    markdown = report_to_markdown(report)

    assert "Белый дом выступил" in markdown
