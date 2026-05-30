"""Top-level deterministic pipeline entry point."""

from datetime import UTC, date, datetime

from fa_checker.agent.context_profiles import ContextProfile
from fa_checker.agent.state import DeterministicAnalysisResult
from fa_checker.domain.enums import FindingStatus, MatchType, ReportStatus
from fa_checker.domain.models import (
    Article,
    AuthorCheckResult,
    CheckReport,
    FinalFinding,
    ProcessingSummary,
    RegistryEntry,
    ResourceLinkMatch,
)
from fa_checker.matching.author import check_article_author
from fa_checker.matching.exact import find_exact_matches
from fa_checker.matching.fuzzy import find_fuzzy_person_matches
from fa_checker.matching.labels import check_label
from fa_checker.matching.resource_links import find_resource_link_matches
from fa_checker.scoring.risk import ScoringInput, score_candidate_matches

SCAFFOLD_LIMITATION = "Business logic is not implemented yet; this is a scaffold report."
OFFLINE_LIMITATION = (
    "Offline deterministic check only; fuzzy matching, LLM disambiguation, "
    "and agentic recall pass are not applied."
)
FUZZY_OFFLINE_LIMITATION = (
    "Offline deterministic check with person-only fuzzy recall; LLM "
    "disambiguation and agentic recall pass are not applied."
)


def run_deterministic_analysis(
    article: Article,
    registry_entries: list[RegistryEntry],
    enable_fuzzy: bool = False,
) -> DeterministicAnalysisResult:
    """Run mandatory deterministic checks and return structured analysis state."""
    candidates = find_exact_matches(article, registry_entries)
    if enable_fuzzy:
        candidates = [
            *candidates,
            *find_fuzzy_person_matches(
                article,
                registry_entries,
                existing_matches=candidates,
            ),
        ]
    label_results = [check_label(article, candidate) for candidate in candidates]
    scoring_inputs = [
        ScoringInput(
            match=candidate,
            label_result=label_result,
            disambiguation=None,
        )
        for candidate, label_result in zip(candidates, label_results, strict=True)
    ]
    findings = score_candidate_matches(scoring_inputs)
    resource_link_matches = find_resource_link_matches(article, registry_entries)
    author_check = check_article_author(article, registry_entries)
    registry_snapshot_date = _get_registry_snapshot_date(registry_entries)
    base_report = _build_check_report(
        article=article,
        registry_snapshot_date=registry_snapshot_date,
        findings=findings,
        resource_link_matches=resource_link_matches,
        author_check=author_check,
        processing_summary=_build_deterministic_processing_summary(
            candidates=candidates,
            findings=findings,
            resource_link_matches=resource_link_matches,
            author_check=author_check,
            fuzzy_enabled=enable_fuzzy,
        ),
    )

    return DeterministicAnalysisResult(
        article=article,
        registry_snapshot_date=registry_snapshot_date,
        candidates=candidates,
        label_results=label_results,
        resource_link_matches=resource_link_matches,
        author_check=author_check,
        findings=findings,
        base_report=base_report,
        strong_candidates_count=sum(
            not candidate.requires_disambiguation for candidate in candidates
        ),
        weak_candidates_count=sum(
            candidate.requires_disambiguation for candidate in candidates
        ),
        confirmed_findings_count=_count_findings(findings, FindingStatus.CONFIRMED),
        probable_findings_count=_count_findings(findings, FindingStatus.PROBABLE),
        uncertain_findings_count=_count_findings(findings, FindingStatus.UNCERTAIN),
        rejected_findings_count=_count_findings(findings, FindingStatus.REJECTED),
        requires_agent_review=any(candidate.requires_disambiguation for candidate in candidates),
        limitations=[_offline_limitation(enable_fuzzy)],
    )


def run_offline_check(
    article: Article,
    registry_entries: list[RegistryEntry],
    enable_fuzzy: bool = False,
) -> CheckReport:
    """Run deterministic offline matching, label checking, and scoring."""
    return run_deterministic_analysis(
        article,
        registry_entries,
        enable_fuzzy=enable_fuzzy,
    ).base_report


def run_agentic_review_check(
    article: Article,
    registry_entries: list[RegistryEntry],
    context_profiles: list[ContextProfile] | None = None,
    enable_fuzzy: bool = False,
) -> CheckReport:
    """Run deterministic baseline plus bounded weak-candidate review."""
    from fa_checker.agent.orchestrator import run_bounded_review_check

    return run_bounded_review_check(
        article,
        registry_entries,
        context_profiles=context_profiles,
        enable_fuzzy=enable_fuzzy,
    )


def _build_check_report(
    article: Article,
    registry_snapshot_date: date | None,
    findings: list[FinalFinding],
    resource_link_matches: list[ResourceLinkMatch] | None = None,
    author_check: AuthorCheckResult | None = None,
    processing_summary: ProcessingSummary | None = None,
) -> CheckReport:
    link_matches = resource_link_matches or []
    return CheckReport(
        article_url=article.url,
        article_title=article.title,
        article_author=article.author,
        checked_at=datetime.now(UTC),
        registry_snapshot_date=registry_snapshot_date,
        status=_derive_report_status(findings, link_matches, author_check),
        findings=findings,
        resource_link_matches=link_matches,
        author_check=author_check,
        limitations=[
            _offline_limitation(
                processing_summary.fuzzy_enabled
                if processing_summary is not None
                else False
            )
        ],
        processing_summary=processing_summary,
    )


def run_check(url: str) -> CheckReport:
    """Return a placeholder report while the real pipeline is still scaffolded."""
    return CheckReport(
        article_url=url,
        article_title=None,
        article_author=None,
        checked_at=datetime.now(UTC),
        registry_snapshot_date=None,
        status=ReportStatus.NO_MATCH,
        findings=[],
        limitations=[SCAFFOLD_LIMITATION],
    )


def _derive_report_status(
    findings: list[FinalFinding],
    resource_link_matches: list[ResourceLinkMatch] | None = None,
    author_check: AuthorCheckResult | None = None,
) -> ReportStatus:
    if any(finding.status == FindingStatus.CONFIRMED for finding in findings):
        return ReportStatus.CONFIRMED_MATCH_FOUND
    if resource_link_matches:
        return ReportStatus.CONFIRMED_MATCH_FOUND
    if author_check is not None and author_check.status == "strong_match":
        return ReportStatus.CONFIRMED_MATCH_FOUND
    if any(
        finding.status in {FindingStatus.PROBABLE, FindingStatus.UNCERTAIN}
        for finding in findings
    ):
        return ReportStatus.POTENTIAL_MATCH_FOUND
    if author_check is not None and author_check.status == "weak_match":
        return ReportStatus.POTENTIAL_MATCH_FOUND
    return ReportStatus.NO_MATCH


def _count_findings(findings: list[FinalFinding], status: FindingStatus) -> int:
    return sum(finding.status == status for finding in findings)


def _build_deterministic_processing_summary(
    candidates,
    findings: list[FinalFinding],
    resource_link_matches: list[ResourceLinkMatch] | None = None,
    author_check: AuthorCheckResult | None = None,
    fuzzy_enabled: bool = False,
) -> ProcessingSummary:
    confirmed = _count_findings(findings, FindingStatus.CONFIRMED)
    probable = _count_findings(findings, FindingStatus.PROBABLE)
    uncertain = _count_findings(findings, FindingStatus.UNCERTAIN)
    rejected = _count_findings(findings, FindingStatus.REJECTED)
    return ProcessingSummary(
        mode="deterministic",
        deterministic_candidates_total=len(candidates),
        deterministic_strong_candidates=sum(
            not candidate.requires_disambiguation for candidate in candidates
        ),
        deterministic_weak_candidates=sum(
            candidate.requires_disambiguation for candidate in candidates
        ),
        deterministic_fuzzy_candidates=sum(
            candidate.match_type == MatchType.FUZZY for candidate in candidates
        ),
        fuzzy_enabled=fuzzy_enabled,
        deterministic_confirmed_findings=confirmed,
        deterministic_probable_findings=probable,
        deterministic_uncertain_findings=uncertain,
        deterministic_rejected_findings=rejected,
        final_findings_total=len(findings),
        final_confirmed_findings=confirmed,
        final_probable_findings=probable,
        final_uncertain_findings=uncertain,
        final_rejected_findings=rejected,
        final_requires_human_review=sum(
            finding.requires_human_review for finding in findings
        ),
        resource_link_matches_total=len(resource_link_matches or []),
        author_check_status=author_check.status if author_check is not None else None,
        author_requires_human_review=(
            author_check.requires_human_review if author_check is not None else False
        ),
    )


def _offline_limitation(enable_fuzzy: bool) -> str:
    return FUZZY_OFFLINE_LIMITATION if enable_fuzzy else OFFLINE_LIMITATION


def _get_registry_snapshot_date(registry_entries: list[RegistryEntry]) -> date | None:
    for entry in registry_entries:
        if entry.registry_snapshot_date is not None:
            return entry.registry_snapshot_date
    return None
