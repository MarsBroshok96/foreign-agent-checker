"""Human-readable Markdown report rendering."""

from dataclasses import dataclass, field

from fa_checker.article.normalizer import normalize_for_display
from fa_checker.domain.enums import FindingStatus, LabelStatus, ReportStatus, RiskLevel
from fa_checker.domain.models import (
    CheckReport,
    EvidenceFragment,
    FinalFinding,
    ProcessingSummary,
)

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

@dataclass
class GroupedFinding:
    entity_name: str
    status: FindingStatus
    risk_level: RiskLevel
    confidence_level: object
    label_status: LabelStatus
    requires_human_review: bool
    rationale: str
    review_rationales: list[str] = field(default_factory=list)
    mention_texts: list[str] = field(default_factory=list)
    evidence_fragments: list[EvidenceFragment] = field(default_factory=list)
    occurrences_count: int = 0


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
    lines.extend(["", "## Проверка ссылок в статье"])
    lines.extend(_resource_link_lines(report))
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
    if report.author_check is not None:
        lines.append(f"- {_author_check_text(report.author_check)}")
    lines.append(f"- Проверено: {_format_optional(report.checked_at)}")
    if report.registry_snapshot_date is not None:
        lines.append(f"- Дата снимка реестра: {_format_optional(report.registry_snapshot_date)}")
    mode = report.processing_summary.mode if report.processing_summary is not None else None
    lines.append(f"- Режим проверки: {_mode_text(mode)}")
    lines.append(f"- Итоговый статус: {_report_status_text(report.status)}")
    return lines


def _executive_summary_lines(report: CheckReport) -> list[str]:
    summary = report.processing_summary
    if summary is None:
        return _legacy_summary_lines(report)

    active_without_review = (
        summary.final_confirmed_findings + summary.final_probable_findings
    )
    has_non_text_signal = (
        summary.resource_link_matches_total > 0
        or summary.author_check_status in {"strong_match", "weak_match"}
    )
    lines = [
        "После полного цикла проверки:",
        f"- Подтверждено/вероятно найдено: {active_without_review}",
        f"- Требуют ручной проверки: {summary.final_requires_human_review}",
        f"- Отклонено после проверки: {summary.final_rejected_findings}",
        f"- Всего кандидатов/находок в отчёте: {summary.final_findings_total}",
        f"- Активные совпадения: {active_without_review}",
    ]
    if summary.resource_link_matches_total > 0:
        lines.append(
            "- Совпадения по полным ссылкам на ресурсы из реестра: "
            f"{summary.resource_link_matches_total}"
        )
    if summary.author_check_status in {"strong_match", "weak_match"}:
        lines.append(
            "- Проверка автора: "
            f"{_author_check_status_text(summary.author_check_status)}"
        )
    if (
        report.status == ReportStatus.NO_MATCH
        and summary.final_rejected_findings > 0
        and active_without_review == 0
    ):
        lines.append(
            "Активные совпадения с реестром не подтверждены; отклонённые "
            "кандидаты показаны ниже для аудита."
        )
    if summary.final_findings_total == 0 and not has_non_text_signal:
        lines.append("На текущем уровне проверки совпадения с реестром не выявлены.")
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
    ]


def _deterministic_summary_lines(summary: ProcessingSummary | None) -> list[str]:
    if summary is None:
        return ["Сводка deterministic layer недоступна для этого отчёта."]
    lines = [
        f"- Кандидатов найдено deterministic layer: {summary.deterministic_candidates_total}",
        f"- Сильные совпадения: {summary.deterministic_strong_candidates}",
        f"- Слабые совпадения: {summary.deterministic_weak_candidates}",
        f"- Совпадения по ссылкам: {summary.resource_link_matches_total}",
        f"- Статус проверки автора: {_author_check_status_text(summary.author_check_status)}",
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
        f"- Проверено слабых кандидатов: {summary.agentic_reviewed_candidates}",
        f"- Подтверждено: {summary.agentic_confirmed_after_review}",
        f"- Вероятные совпадения: {summary.agentic_probable_after_review}",
        f"- Отклонено: {summary.agentic_rejected_after_review}",
        f"- Остались на ручную проверку: {summary.agentic_uncertain_after_review}",
    ]


def _resource_link_lines(report: CheckReport) -> list[str]:
    if not report.resource_link_matches:
        return ["Ссылки на ресурсы иностранных агентов в тексте статьи не обнаружены."]

    lines = ["Обнаружены ссылки на ресурсы из реестра:"]
    for index, match in enumerate(report.resource_link_matches, start=1):
        lines.extend(
            [
                f"{index}. {match.entity_name}",
                f"   - Ссылка в статье: {match.article_url}",
                f"   - Ссылка в реестре: {match.registry_url}",
            ]
        )
    return lines


def _grouped_finding_lines(findings: list[FinalFinding]) -> list[str]:
    if not findings:
        return ["Текстовые упоминания кандидатов в статье не выявлены текущей проверкой."]

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
    for index, finding in enumerate(_group_findings(findings), start=1):
        lines.extend(["", ""])
        lines.extend(_finding_lines(index, finding, rejected=rejected))
    return lines


def _finding_lines(index: int, finding: GroupedFinding, rejected: bool = False) -> list[str]:
    lines = [
        f"#### {index}. {finding.entity_name}",
        "",
        f"- Количество упоминаний/срабатываний: {finding.occurrences_count}",
        f"- Варианты упоминания: {', '.join(finding.mention_texts)}",
        f"- Статус находки: {_finding_status_text(finding.status)}",
        f"- Статус маркировки: {_label_status_text(finding.label_status)}",
        f"- Требуется ручная проверка: {_format_bool(finding.requires_human_review)}",
    ]
    review_rationale = _combined_review_rationale(finding.review_rationales)
    if review_rationale:
        lines.append(f"- Обоснование agentic review: {review_rationale}")
    if rejected:
        lines.append("- Интерпретация: Кандидат отклонён в ходе disambiguation/review.")
    if finding.evidence_fragments:
        lines.append("- Фрагменты из источника:")
        for evidence_index, evidence in enumerate(finding.evidence_fragments, start=1):
            evidence_text = _format_evidence_text(evidence.text, finding.mention_texts)
            lines.append(f"  {evidence_index}. {_evidence_source_text(evidence)}: {evidence_text}")
    return lines


def _group_findings(findings: list[FinalFinding]) -> list[GroupedFinding]:
    groups: dict[tuple, GroupedFinding] = {}
    for finding in findings:
        key = (
            finding.entity_name,
            finding.status,
            finding.risk_level,
            finding.confidence_level,
            finding.label_status,
            finding.requires_human_review,
            finding.rationale,
        )
        if key not in groups:
            groups[key] = GroupedFinding(
                entity_name=finding.entity_name,
                status=finding.status,
                risk_level=finding.risk_level,
                confidence_level=finding.confidence_level,
                label_status=finding.label_status,
                requires_human_review=finding.requires_human_review,
                rationale=finding.rationale,
            )
        group = groups[key]
        group.occurrences_count += 1
        if finding.mention_text not in group.mention_texts:
            group.mention_texts.append(finding.mention_text)
        if finding.review_rationale and finding.review_rationale not in group.review_rationales:
            group.review_rationales.append(finding.review_rationale)
        _extend_evidence(group, finding.evidence)
    return list(groups.values())


def _extend_evidence(group: GroupedFinding, evidence_fragments: list[EvidenceFragment]) -> None:
    existing_keys = {
        (evidence.source, evidence.text, evidence.start, evidence.end)
        for evidence in group.evidence_fragments
    }
    for evidence in evidence_fragments:
        key = (evidence.source, evidence.text, evidence.start, evidence.end)
        if key not in existing_keys:
            group.evidence_fragments.append(evidence)
            existing_keys.add(key)


def _format_evidence_text(text: str, mention_texts: list[str]) -> str:
    trimmed = _trim_evidence_text(text)
    return _highlight_first_mention(trimmed, mention_texts)


def _trim_evidence_text(text: str, max_chars: int = 500) -> str:
    normalized = normalize_for_display(text)
    if len(normalized) <= max_chars:
        return normalized
    return normalized[:max_chars].rstrip() + "..."


def _highlight_first_mention(text: str, mention_texts: list[str]) -> str:
    lower_text = text.lower()
    for mention in mention_texts:
        if not mention:
            continue
        index = lower_text.find(mention.lower())
        if index == -1:
            continue
        end = index + len(mention)
        return f"{text[:index]}**{text[index:end]}**{text[end:]}"
    return text


def _combined_review_rationale(rationales: list[str]) -> str | None:
    if not rationales:
        return None
    return "; ".join(rationales)


def _evidence_source_text(evidence: EvidenceFragment) -> str:
    if evidence.source.value == "article_text":
        return "Контекст"
    return evidence.source.value


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


def _mode_text(mode: str | None) -> str:
    if mode == "deterministic":
        return "детерминированный"
    if mode == "agentic":
        return "agentic review"
    return "не указано"


def _report_status_text(status: ReportStatus) -> str:
    return REPORT_STATUS_TEXT[status]


def _label_status_text(status: LabelStatus) -> str:
    return LABEL_STATUS_TEXT[status]


def _finding_status_text(status: FindingStatus) -> str:
    status_text = {
        FindingStatus.CONFIRMED: "подтверждено",
        FindingStatus.PROBABLE: "вероятное совпадение",
        FindingStatus.UNCERTAIN: "не определено",
        FindingStatus.REJECTED: "отклонён",
    }
    return status_text[status]


def _author_check_text(author_check) -> str:
    if author_check.status == "no_author":
        return "Проверка автора: автор не указан в статье"
    if author_check.status == "no_match":
        return "Проверка автора: отсутствует в реестре иностранных агентов"
    if author_check.status == "strong_match":
        suffix = f" — {author_check.entity_name}" if author_check.entity_name else ""
        return (
            "Проверка автора: присутствует в реестре иностранных агентов"
            f"{suffix}"
        )
    if author_check.status == "weak_match":
        suffix = f" — {author_check.entity_name}" if author_check.entity_name else ""
        return (
            "Проверка автора: есть слабое совпадение с реестром, "
            f"требуется ручная проверка{suffix}"
        )
    return "Проверка автора: не выполнялась"


def _author_check_status_text(status: str | None) -> str:
    status_text = {
        "no_author": "автор не указан в статье",
        "no_match": "автор отсутствует в реестре иностранных агентов",
        "strong_match": "автор присутствует в реестре иностранных агентов",
        "weak_match": "слабое совпадение автора, требуется ручная проверка",
    }
    return status_text.get(status, "не выполнялась")
