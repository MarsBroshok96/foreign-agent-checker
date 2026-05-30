"""Shared report status and processing-summary helpers."""

from typing import Any

from fa_checker.domain.enums import FindingStatus, ReportStatus
from fa_checker.domain.models import (
    AuthorCheckResult,
    FinalFinding,
    ProcessingSummary,
    ResourceLinkMatch,
)


def value_of(value: Any) -> Any:
    """Return enum values as plain values while preserving non-enum inputs."""
    if hasattr(value, "value"):
        return value.value
    return value


def derive_report_status(
    findings: list[FinalFinding],
    author_check: AuthorCheckResult | None = None,
    resource_link_matches: list[ResourceLinkMatch] | None = None,
) -> ReportStatus:
    """Derive the overall report status from final report signals."""
    if any(value_of(finding.status) == FindingStatus.CONFIRMED.value for finding in findings):
        return ReportStatus.CONFIRMED_MATCH_FOUND
    if resource_link_matches:
        return ReportStatus.CONFIRMED_MATCH_FOUND
    if author_check is not None and author_check.status == "strong_match":
        return ReportStatus.CONFIRMED_MATCH_FOUND
    if any(
        value_of(finding.status)
        in {FindingStatus.PROBABLE.value, FindingStatus.UNCERTAIN.value}
        for finding in findings
    ):
        return ReportStatus.POTENTIAL_MATCH_FOUND
    if author_check is not None and author_check.status == "weak_match":
        return ReportStatus.POTENTIAL_MATCH_FOUND
    return ReportStatus.NO_MATCH


def count_findings(findings: list[FinalFinding]) -> dict[str, int]:
    """Count findings by status and common report groupings."""
    confirmed = _count_status(findings, FindingStatus.CONFIRMED)
    probable = _count_status(findings, FindingStatus.PROBABLE)
    uncertain = _count_status(findings, FindingStatus.UNCERTAIN)
    rejected = _count_status(findings, FindingStatus.REJECTED)
    return {
        "total": len(findings),
        "confirmed": confirmed,
        "probable": probable,
        "uncertain": uncertain,
        "rejected": rejected,
        "requires_human_review": sum(finding.requires_human_review for finding in findings),
        "active": confirmed + probable,
        "active_no_human_review": sum(
            value_of(finding.status)
            in {FindingStatus.CONFIRMED.value, FindingStatus.PROBABLE.value}
            and not finding.requires_human_review
            for finding in findings
        ),
    }


def build_processing_summary(
    mode: str,
    deterministic_candidates_total: int,
    deterministic_strong_candidates: int,
    deterministic_weak_candidates: int,
    deterministic_fuzzy_candidates: int,
    fuzzy_enabled: bool,
    deterministic_findings: list[FinalFinding],
    final_findings: list[FinalFinding],
    author_check: AuthorCheckResult | None = None,
    resource_link_matches: list[ResourceLinkMatch] | None = None,
    agentic_review_applied: bool = False,
    agentic_review_candidates_total: int = 0,
    agentic_reviewed_candidates: int = 0,
    agentic_reviewed_candidate_indexes: set[int] | None = None,
) -> ProcessingSummary:
    """Build a ProcessingSummary using the project's existing field semantics."""
    deterministic_counts = count_findings(deterministic_findings)
    final_counts = count_findings(final_findings)
    reviewed_findings = [
        final_findings[index]
        for index in (agentic_reviewed_candidate_indexes or set())
        if index < len(final_findings)
    ]
    reviewed_counts = count_findings(reviewed_findings)

    return ProcessingSummary(
        mode=mode,
        deterministic_candidates_total=deterministic_candidates_total,
        deterministic_strong_candidates=deterministic_strong_candidates,
        deterministic_weak_candidates=deterministic_weak_candidates,
        deterministic_fuzzy_candidates=deterministic_fuzzy_candidates,
        fuzzy_enabled=fuzzy_enabled,
        deterministic_confirmed_findings=deterministic_counts["confirmed"],
        deterministic_probable_findings=deterministic_counts["probable"],
        deterministic_uncertain_findings=deterministic_counts["uncertain"],
        deterministic_rejected_findings=deterministic_counts["rejected"],
        agentic_review_applied=agentic_review_applied,
        agentic_review_candidates_total=agentic_review_candidates_total,
        agentic_reviewed_candidates=agentic_reviewed_candidates,
        agentic_confirmed_after_review=reviewed_counts["confirmed"],
        agentic_probable_after_review=reviewed_counts["probable"],
        agentic_uncertain_after_review=reviewed_counts["uncertain"],
        agentic_rejected_after_review=reviewed_counts["rejected"],
        final_findings_total=final_counts["total"],
        final_confirmed_findings=final_counts["confirmed"],
        final_probable_findings=final_counts["probable"],
        final_uncertain_findings=final_counts["uncertain"],
        final_rejected_findings=final_counts["rejected"],
        final_requires_human_review=final_counts["requires_human_review"],
        resource_link_matches_total=len(resource_link_matches or []),
        author_check_status=author_check.status if author_check is not None else None,
        author_requires_human_review=(
            author_check.requires_human_review if author_check is not None else False
        ),
    )


def _count_status(findings: list[FinalFinding], status: FindingStatus) -> int:
    return sum(value_of(finding.status) == status.value for finding in findings)
