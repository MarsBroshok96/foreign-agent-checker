"""Human-readable Markdown report rendering."""

from fa_checker.domain.enums import FindingStatus, LabelStatus, ReportStatus, RiskLevel
from fa_checker.domain.models import CheckReport, FinalFinding, ProcessingSummary

REPORT_STATUS_TEXT = {
    ReportStatus.NO_MATCH: "Совпадения с реестром не выявлены текущей проверкой.",
    ReportStatus.POTENTIAL_MATCH_FOUND: (
        "Найдены потенциальные совпадения, требуется ручная проверка."
    ),
    ReportStatus.CONFIRMED_MATCH_FOUND: "Найдены совпадения с реестром.",
    ReportStatus.ERROR: "Проверка завершилась с ошибкой.",
}

LABEL_STATUS_TEXT = {
    LabelStatus.PRESENT: "маркировка найдена рядом с упоминанием",
    LabelStatus.WEAK: "маркировка найдена в статье, но не рядом с упоминанием",
    LabelStatus.ABSENT: "маркировка не найдена",
    LabelStatus.NOT_CHECKED: "проверка маркировки не выполнялась",
}

RISK_ORDER = {
    RiskLevel.NO_MATCH: 0,
    RiskLevel.LOW: 1,
    RiskLevel.MEDIUM: 2,
    RiskLevel.HIGH: 3,
}


def report_to_markdown(report: CheckReport) -> str:
    """Render a cautious human-readable Markdown report."""
    lines = [
        "# Проверка статьи на упоминание иностранных агентов",
        "",
        "## Метаданные",
    ]
    lines.extend(_metadata_lines(report))
    lines.extend(["", "## Краткая сводка"])
    lines.extend(_executive_summary_lines(report))
    lines.extend(["", "## Детерминированный слой"])
    lines.extend(_deterministic_summary_lines(report.processing_summary))
    lines.extend(["", "## Agentic review"])
    lines.extend(_agentic_summary_lines(report.processing_summary))
    lines.extend(["", "## Находки и кандидаты"])
    lines.extend(_grouped_finding_lines(report.findings))
    lines.extend(["", "## Ограничения"])
    lines.extend(_limitations_lines(report))
    return "\n".join(lines)


def render_markdown_report(report: CheckReport) -> str:
    return report_to_markdown(report)


def _metadata_lines(report: CheckReport) -> list[str]:
    lines: list[str] = []
    if report.article_title:
        lines.append(f"- Заголовок: {report.article_title}")
    lines.append(f"- URL статьи: {report.article_url}")
    if report.article_author:
        lines.append(f"- Автор: {report.article_author}")
    lines.append(f"- Проверено: {_format_optional(report.checked_at)}")
    if report.registry_snapshot_date is not None:
        lines.append(f"- Дата снимка реестра: {_format_optional(report.registry_snapshot_date)}")
    mode = report.processing_summary.mode if report.processing_summary is not None else "не указано"
    lines.append(f"- Режим проверки: {mode}")
    lines.append(f"- Итоговый статус: {report.status.value}")
    lines.append(f"- Описание статуса: {_report_status_text(report.status)}")
    return lines


def _executive_summary_lines(report: CheckReport) -> list[str]:
    summary = report.processing_summary
    if summary is None:
        return _legacy_summary_lines(report)

    active_without_review = (
        summary.final_confirmed_findings + summary.final_probable_findings
    )
    lines = [
        "После полного цикла проверки:",
        f"- Подтверждено/вероятно найдено: {active_without_review}",
        f"- Требуют ручной проверки: {summary.final_requires_human_review}",
        f"- Отклонено после проверки: {summary.final_rejected_findings}",
        f"- Всего кандидатов/находок в отчёте: {summary.final_findings_total}",
        f"- Активные совпадения: {active_without_review}",
    ]
    if (
        report.status == ReportStatus.NO_MATCH
        and summary.final_rejected_findings > 0
        and active_without_review == 0
    ):
        lines.append(
            "Активные совпадения с реестром не подтверждены; часть кандидатов "
            "была отклонена в ходе проверки."
        )
    if summary.final_findings_total == 0:
        lines.append("На текущем уровне проверки совпадения с реестром не выявлены.")
    lines.append(f"- Наивысший уровень риска: {_highest_risk_level(report)}")
    return lines


def _legacy_summary_lines(report: CheckReport) -> list[str]:
    if not report.findings:
        return ["На текущем уровне проверки совпадения с реестром не выявлены."]
    review_count = sum(finding.requires_human_review for finding in report.findings)
    rejected_count = sum(finding.status == FindingStatus.REJECTED for finding in report.findings)
    return [
        f"- Всего кандидатов/находок в отчёте: {len(report.findings)}",
        f"- Требуют ручной проверки: {review_count}",
        f"- Отклонено: {rejected_count}",
        f"- Наивысший уровень риска: {_highest_risk_level(report)}",
    ]


def _deterministic_summary_lines(summary: ProcessingSummary | None) -> list[str]:
    if summary is None:
        return ["Сводка deterministic layer недоступна для этого отчёта."]
    lines = [
        f"- Кандидатов найдено deterministic layer: {summary.deterministic_candidates_total}",
        f"- Сильные совпадения: {summary.deterministic_strong_candidates}",
        f"- Слабые совпадения: {summary.deterministic_weak_candidates}",
        f"- Подтверждено: {summary.deterministic_confirmed_findings}",
        f"- Вероятные совпадения: {summary.deterministic_probable_findings}",
        f"- Неопределённые кандидаты: {summary.deterministic_uncertain_findings}",
        f"- Отклонено: {summary.deterministic_rejected_findings}",
    ]
    if summary.mode == "agentic" and summary.deterministic_weak_candidates > 0:
        lines.append("Слабые совпадения направлены на agentic review.")
    return lines


def _agentic_summary_lines(summary: ProcessingSummary | None) -> list[str]:
    if summary is None or summary.mode != "agentic":
        return ["Agentic review не применялся."]
    return [
        f"- Agentic review: {_format_bool(summary.agentic_review_applied)}",
        f"- Проверено weak-кандидатов: {summary.agentic_reviewed_candidates}",
        f"- Подтверждено: {summary.agentic_confirmed_after_review}",
        f"- Вероятные совпадения: {summary.agentic_probable_after_review}",
        f"- Отклонено: {summary.agentic_rejected_after_review}",
        f"- Остались на ручную проверку: {summary.agentic_uncertain_after_review}",
    ]


def _grouped_finding_lines(findings: list[FinalFinding]) -> list[str]:
    if not findings:
        return ["На текущем уровне проверки совпадения с реестром не выявлены."]

    active = [
        finding
        for finding in findings
        if finding.status in {FindingStatus.CONFIRMED, FindingStatus.PROBABLE}
        and not finding.requires_human_review
    ]
    human_review = [
        finding
        for finding in findings
        if finding.requires_human_review and finding.status != FindingStatus.REJECTED
    ]
    rejected = [
        finding for finding in findings if finding.status == FindingStatus.REJECTED
    ]

    lines: list[str] = []
    lines.extend(
        _finding_section_lines(
            "### Совпадения, не требующие ручной проверки",
            active,
            empty_text="Таких совпадений нет.",
        )
    )
    lines.extend(
        _finding_section_lines(
            "### Требуют ручной проверки",
            human_review,
            empty_text="Кандидатов для ручной проверки нет.",
        )
    )
    lines.extend(
        _finding_section_lines(
            "### Отклонены в ходе проверки",
            rejected,
            empty_text="Отклонённых кандидатов нет.",
            rejected=True,
        )
    )
    return lines


def _finding_section_lines(
    title: str,
    findings: list[FinalFinding],
    empty_text: str,
    rejected: bool = False,
) -> list[str]:
    lines = [title]
    if not findings:
        lines.append(empty_text)
        return lines
    for index, finding in enumerate(findings, start=1):
        lines.extend(_finding_lines(index, finding, rejected=rejected))
    return lines


def _finding_lines(index: int, finding: FinalFinding, rejected: bool = False) -> list[str]:
    lines = [
        f"#### {index}. {finding.entity_name}",
        "",
        f"- Упоминание: {finding.mention_text}",
        f"- Статус находки: {finding.status.value}",
        f"- Уровень риска: {finding.risk_level.value}",
        f"- Уверенность: {finding.confidence_level.value}",
        f"- Статус маркировки: {_label_status_text(finding.label_status)}",
        f"- Требуется ручная проверка: {_format_bool(finding.requires_human_review)}",
        f"- Обоснование: {finding.rationale}",
    ]
    if rejected:
        lines.append("- Интерпретация: Кандидат отклонён в ходе disambiguation/review.")
    if finding.evidence:
        lines.append("- Фрагменты доказательств:")
        for evidence in finding.evidence:
            lines.append(f"  - `{evidence.source.value}`: {evidence.text}")
    return lines


def _limitations_lines(report: CheckReport) -> list[str]:
    if report.limitations:
        return [f"- {limitation}" for limitation in report.limitations]
    return [
        "- Это вспомогательная проверка; ручная проверка может быть нужна.",
    ]


def _format_optional(value: object) -> str:
    if value is None:
        return "не указано"
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _format_bool(value: bool) -> str:
    return "да" if value else "нет"


def _highest_risk_level(report: CheckReport) -> str:
    if not report.findings:
        return RiskLevel.NO_MATCH.value
    return max(report.findings, key=lambda finding: RISK_ORDER[finding.risk_level]).risk_level.value


def _report_status_text(status: ReportStatus) -> str:
    return REPORT_STATUS_TEXT[status]


def _label_status_text(status: LabelStatus) -> str:
    return LABEL_STATUS_TEXT[status]
