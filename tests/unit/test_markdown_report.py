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
    review_rationale: str | None = None,
    evidence_text: str | None = None,
    evidence_start: int = 0,
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
                text=evidence_text or f"Фрагмент с упоминанием: {mention_text}",
                start=evidence_start,
                end=evidence_start + 20,
            )
        ],
        rationale="Strong exact registry match found, but label not found.",
        review_rationale=review_rationale,
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
    assert "Уровень риска:" not in markdown
    assert "Уверенность:" not in markdown
    assert "Статус находки: подтверждено" in markdown
    assert "маркировка не найдена" in markdown
    assert "Strong exact registry match found, but label not found." not in markdown
    assert "Фрагмент с упоминанием:" in markdown
    assert "**Илья Варламов**" in markdown
    assert "Фрагменты из источника:" in markdown
    assert "Контекст:" in markdown
    assert "article_text" not in markdown


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

    assert "**Белый** дом выступил" in markdown


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


def test_markdown_has_two_blank_lines_before_grouped_candidate() -> None:
    finding = make_finding(
        entity_name="Белый Руслан Викторович",
        mention_text="Белый",
        requires_human_review=False,
        status=FindingStatus.REJECTED,
        risk_level=RiskLevel.LOW,
        confidence_level=ConfidenceLevel.LOW,
    )

    markdown = report_to_markdown(make_report(findings=[finding]))

    assert "Отклонённых кандидатов нет.\n###" not in markdown
    assert "### Отклонены в ходе проверки\n\n\n#### 1. Белый Руслан Викторович" in markdown
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


def test_markdown_groups_duplicate_rejected_findings() -> None:
    first = make_finding(
        entity_name="Белый Руслан Викторович",
        mention_text="Белый",
        requires_human_review=False,
        status=FindingStatus.REJECTED,
        risk_level=RiskLevel.LOW,
        confidence_level=ConfidenceLevel.LOW,
        review_rationale="Контекст относится к Белому дому, а не к человеку.",
        evidence_text="Первый фрагмент: Белый дом выступил с заявлением.",
        evidence_start=0,
    )
    second = make_finding(
        entity_name="Белый Руслан Викторович",
        mention_text="Белый",
        requires_human_review=False,
        status=FindingStatus.REJECTED,
        risk_level=RiskLevel.LOW,
        confidence_level=ConfidenceLevel.LOW,
        review_rationale="Контекст относится к выражению Белый дом, а не к человеку.",
        evidence_text="Второй фрагмент: Белый дом повторил позицию.",
        evidence_start=100,
    )

    markdown = report_to_markdown(
        make_report(
            status=ReportStatus.NO_MATCH,
            findings=[first, second],
            processing_summary=ProcessingSummary(
                mode="agentic",
                final_findings_total=2,
                final_rejected_findings=2,
            ),
        )
    )

    assert markdown.count("#### 1. Белый Руслан Викторович") == 1
    assert "Количество упоминаний/срабатываний: 2" in markdown
    assert "Первый фрагмент" in markdown
    assert "Второй фрагмент" in markdown
    assert "Контекст относится к Белому дому" in markdown
    assert "Контекст относится к выражению Белый дом" in markdown
    assert "### Отклонены в ходе проверки" in markdown


def test_markdown_does_not_merge_same_entity_with_different_status() -> None:
    uncertain = make_finding(
        entity_name="Белый Руслан Викторович",
        mention_text="Белый",
        requires_human_review=True,
        status=FindingStatus.UNCERTAIN,
        risk_level=RiskLevel.MEDIUM,
        confidence_level=ConfidenceLevel.LOW,
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
            status=ReportStatus.POTENTIAL_MATCH_FOUND,
            findings=[uncertain, rejected],
        )
    )

    assert "### Требуют ручной проверки" in markdown
    assert "### Отклонены в ходе проверки" in markdown
    assert markdown.count("Белый Руслан Викторович") >= 2


def test_markdown_groups_duplicate_human_review_findings() -> None:
    first = make_finding(
        entity_name="Проект «После»",
        mention_text="После",
        requires_human_review=True,
        status=FindingStatus.UNCERTAIN,
        risk_level=RiskLevel.MEDIUM,
        confidence_level=ConfidenceLevel.LOW,
        evidence_text="После дождя случилось событие.",
    )
    second = make_finding(
        entity_name="Проект «После»",
        mention_text="После",
        requires_human_review=True,
        status=FindingStatus.UNCERTAIN,
        risk_level=RiskLevel.MEDIUM,
        confidence_level=ConfidenceLevel.LOW,
        evidence_text="После встречи участники разошлись.",
        evidence_start=50,
    )

    markdown = report_to_markdown(
        make_report(
            status=ReportStatus.POTENTIAL_MATCH_FOUND,
            findings=[first, second],
        )
    )

    assert "### Требуют ручной проверки" in markdown
    assert markdown.count("#### 1. Проект «После»") == 1
    assert "Количество упоминаний/срабатываний: 2" in markdown


def test_markdown_renders_review_rationale_separately() -> None:
    finding = make_finding(
        status=FindingStatus.REJECTED,
        risk_level=RiskLevel.LOW,
        confidence_level=ConfidenceLevel.LOW,
        requires_human_review=False,
        review_rationale="Контекст относится к Белому дому, а не к человеку.",
    )

    markdown = report_to_markdown(make_report(findings=[finding]))

    assert "Обоснование deterministic/risk layer" not in markdown
    assert "Обоснование agentic review: Контекст относится к Белому дому" in markdown


def test_markdown_trims_long_evidence_without_modifying_report() -> None:
    long_text = "Белый " + ("очень длинный фрагмент " * 40)
    finding = make_finding(
        mention_text="Белый",
        evidence_text=long_text,
    )
    report = make_report(findings=[finding])

    markdown = report_to_markdown(report)

    assert "..." in markdown
    assert report.findings[0].evidence[0].text == long_text


def test_markdown_highlights_first_matching_mention() -> None:
    finding = make_finding(
        mention_text="Белый",
        evidence_text="Белый дом выступил с заявлением.",
    )

    markdown = report_to_markdown(make_report(findings=[finding]))

    assert "**Белый** дом" in markdown


def test_markdown_rejected_only_summary_mentions_auditability() -> None:
    rejected = make_finding(
        status=FindingStatus.REJECTED,
        risk_level=RiskLevel.LOW,
        confidence_level=ConfidenceLevel.LOW,
        requires_human_review=False,
    )

    markdown = report_to_markdown(
        make_report(
            status=ReportStatus.NO_MATCH,
            findings=[rejected],
            processing_summary=ProcessingSummary(
                mode="agentic",
                final_findings_total=1,
                final_rejected_findings=1,
            ),
        )
    )

    assert "Активные совпадения с реестром не подтверждены" in markdown
    assert "показаны ниже для аудита" in markdown
