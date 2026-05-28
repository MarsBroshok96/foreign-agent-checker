"""Human-readable Markdown report rendering."""

from fa_checker.domain.enums import LabelStatus, ReportStatus, RiskLevel
from fa_checker.domain.models import CheckReport

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

    if report.article_title:
        lines.append(f"- Заголовок: {report.article_title}")
    lines.append(f"- URL статьи: {report.article_url}")
    if report.article_author:
        lines.append(f"- Автор: {report.article_author}")
    lines.append(f"- Проверено: {_format_optional(report.checked_at)}")
    if report.registry_snapshot_date is not None:
        lines.append(f"- Дата снимка реестра: {_format_optional(report.registry_snapshot_date)}")
    lines.append(f"- Итоговый статус: {report.status.value}")
    lines.append(f"- Описание статуса: {_report_status_text(report.status)}")

    lines.extend(["", "## Сводка"])
    if not report.findings:
        lines.append(
            "Совпадения с сущностями из реестра не выявлены текущей "
            "детерминированной проверкой."
        )
    else:
        review_count = sum(finding.requires_human_review for finding in report.findings)
        lines.append(f"- Количество находок: {len(report.findings)}")
        lines.append(f"- Требуют ручной проверки: {review_count}")
        lines.append(f"- Наивысший уровень риска: {_highest_risk_level(report)}")

    lines.extend(["", "## Находки"])
    if not report.findings:
        lines.append("Находки отсутствуют.")
    for index, finding in enumerate(report.findings, start=1):
        lines.extend(
            [
                f"### {index}. {finding.entity_name}",
                "",
                f"- Упоминание: {finding.mention_text}",
                f"- Статус находки: {finding.status.value}",
                f"- Уровень риска: {finding.risk_level.value}",
                f"- Уверенность: {finding.confidence_level.value}",
                f"- Статус маркировки: {_label_status_text(finding.label_status)}",
                f"- Требуется ручная проверка: {_format_bool(finding.requires_human_review)}",
                f"- Обоснование: {finding.rationale}",
            ]
        )
        if finding.evidence:
            lines.append("- Фрагменты доказательств:")
            for evidence in finding.evidence:
                lines.append(f"  - `{evidence.source.value}`: {evidence.text}")

    if report.limitations:
        lines.extend(["", "## Ограничения"])
        for limitation in report.limitations:
            lines.append(f"- {limitation}")
    else:
        lines.extend(
            [
                "",
                "## Ограничения",
                "- Это вспомогательная детерминированная проверка; "
                "ручная проверка может быть нужна.",
            ]
        )

    return "\n".join(lines)


def render_markdown_report(report: CheckReport) -> str:
    return report_to_markdown(report)


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
