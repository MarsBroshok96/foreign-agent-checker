from datetime import UTC, datetime

from fa_checker.domain.enums import (
    ConfidenceLevel,
    EvidenceSource,
    FindingStatus,
    LabelStatus,
    ReportStatus,
    RiskLevel,
)
from fa_checker.domain.models import (
    CheckReport,
    EvidenceFragment,
    FinalFinding,
    ProcessingSummary,
)
from fa_checker.pipeline import run_offline_check
from fa_checker.reporting.markdown_report import report_to_markdown


def make_finding(
    entity_name: str = "Варламов Илья Александрович",
    mention_text: str = "Илья Варламов",
    requires_human_review: bool = True,
    status: FindingStatus = FindingStatus.CONFIRMED,
    risk_level: RiskLevel = RiskLevel.HIGH,
    confidence_level: ConfidenceLevel = ConfidenceLevel.HIGH,
) -> FinalFinding:
    return FinalFinding(
        entity_name=entity_name,
        mention_text=mention_text,
        status=status,
        risk_level=risk_level,
        confidence_level=confidence_level,
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
    processing_summary: ProcessingSummary | None = None,
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
        processing_summary=processing_summary,
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

    assert "Всего кандидатов/находок в отчёте: 2" in markdown
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


def test_markdown_without_processing_summary_still_renders() -> None:
    markdown = report_to_markdown(make_report(findings=[make_finding()]))

    assert "Сводка deterministic layer недоступна" in markdown
    assert "Варламов Илья Александрович" in markdown


def test_markdown_deterministic_report_summary_from_pipeline() -> None:
    from fa_checker.domain.enums import EntityType
    from fa_checker.domain.models import Article, RegistryEntry

    report = run_offline_check(
        Article(
            url="https://www.rambler.ru/example",
            source_domain="www.rambler.ru",
            text="Илья Варламов прокомментировал ситуацию.",
        ),
        [
            RegistryEntry(
                full_name="Варламов Илья Александрович",
                entity_type=EntityType.PERSON,
                normalized_name="варламов илья александрович",
                registry_source_url="https://minjust.gov.ru/registry",
            )
        ],
    )

    markdown = report_to_markdown(report)

    assert "deterministic layer" in markdown
    assert "Кандидатов найдено deterministic layer: 1" in markdown
    assert "Сильные совпадения: 1" in markdown
    assert "Слабые совпадения: 0" in markdown
    assert "Требуют ручной проверки: 1" in markdown


def test_markdown_agentic_rejected_only_report_is_clear() -> None:
    rejected = make_finding(
        entity_name="Белый Руслан Викторович",
        mention_text="Белый",
        requires_human_review=False,
        status=FindingStatus.REJECTED,
        risk_level=RiskLevel.LOW,
        confidence_level=ConfidenceLevel.LOW,
    )
    report = make_report(
        status=ReportStatus.NO_MATCH,
        findings=[rejected],
        processing_summary=ProcessingSummary(
            mode="agentic",
            deterministic_candidates_total=1,
            deterministic_weak_candidates=1,
            agentic_review_applied=True,
            agentic_review_candidates_total=1,
            agentic_reviewed_candidates=1,
            agentic_rejected_after_review=1,
            final_findings_total=1,
            final_rejected_findings=1,
        ),
    )

    markdown = report_to_markdown(report)

    assert "Активные совпадения с реестром не подтверждены" in markdown
    assert "Отклонено после проверки: 1" in markdown
    assert "### Отклонены в ходе проверки" in markdown
    assert "Кандидат отклонён" in markdown
    assert "### Требуют ручной проверки\nКандидатов для ручной проверки нет." in markdown


def test_markdown_agentic_uncertain_report_goes_to_human_review_section() -> None:
    uncertain = make_finding(
        entity_name="Проект «После»",
        mention_text="После",
        requires_human_review=True,
        status=FindingStatus.UNCERTAIN,
        risk_level=RiskLevel.MEDIUM,
        confidence_level=ConfidenceLevel.LOW,
    )
    markdown = report_to_markdown(
        make_report(
            status=ReportStatus.POTENTIAL_MATCH_FOUND,
            findings=[uncertain],
            processing_summary=ProcessingSummary(
                mode="agentic",
                agentic_review_applied=True,
                agentic_uncertain_after_review=1,
                final_findings_total=1,
                final_uncertain_findings=1,
                final_requires_human_review=1,
            ),
        )
    )

    assert "### Требуют ручной проверки" in markdown
    assert "Проект «После»" in markdown


def test_markdown_agentic_mixed_report_groups_confirmed_and_rejected() -> None:
    confirmed = make_finding(
        entity_name="Варламов Илья Александрович",
        mention_text="Илья Варламов",
        requires_human_review=False,
        status=FindingStatus.CONFIRMED,
        risk_level=RiskLevel.LOW,
    )
    rejected = make_finding(
        entity_name="Белый Руслан Викторович",
        mention_text="Белый",
        requires_human_review=False,
        status=FindingStatus.REJECTED,
        risk_level=RiskLevel.LOW,
        confidence_level=ConfidenceLevel.LOW,
    )
    markdown = report_to_markdown(
        make_report(
            status=ReportStatus.CONFIRMED_MATCH_FOUND,
            findings=[confirmed, rejected],
            processing_summary=ProcessingSummary(
                mode="agentic",
                agentic_review_applied=True,
                agentic_reviewed_candidates=1,
                agentic_rejected_after_review=1,
                final_findings_total=2,
                final_confirmed_findings=1,
                final_rejected_findings=1,
            ),
        )
    )

    assert "Подтверждено/вероятно найдено: 1" in markdown
    assert "Отклонено после проверки: 1" in markdown
    assert "### Совпадения, не требующие ручной проверки" in markdown
    assert "### Отклонены в ходе проверки" in markdown
    assert "Варламов Илья Александрович" in markdown
    assert "Белый Руслан Викторович" in markdown
