"""Top-level deterministic pipeline entry point."""

from datetime import UTC, date, datetime

from fa_checker.agent.context_profiles import ContextProfile
from fa_checker.agent.state import DeterministicAnalysisResult
from fa_checker.domain.enums import MatchType
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
from fa_checker.reporting.summary import (
    build_processing_summary,
    count_findings,
    derive_report_status,
)
from fa_checker.scoring.risk import ScoringInput, score_candidate_matches

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
    strong_candidates_count = sum(
        not candidate.requires_disambiguation for candidate in candidates
    )
    weak_candidates_count = sum(
        candidate.requires_disambiguation for candidate in candidates
    )
    deterministic_fuzzy_candidates = sum(
        candidate.match_type == MatchType.FUZZY for candidate in candidates
    )
    finding_counts = count_findings(findings)
    base_report = _build_check_report(
        article=article,
        registry_snapshot_date=registry_snapshot_date,
        findings=findings,
        resource_link_matches=resource_link_matches,
        author_check=author_check,
        processing_summary=build_processing_summary(
            mode="deterministic",
            deterministic_candidates_total=len(candidates),
            deterministic_strong_candidates=strong_candidates_count,
            deterministic_weak_candidates=weak_candidates_count,
            deterministic_fuzzy_candidates=deterministic_fuzzy_candidates,
            fuzzy_enabled=enable_fuzzy,
            deterministic_findings=findings,
            final_findings=findings,
            resource_link_matches=resource_link_matches,
            author_check=author_check,
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
        strong_candidates_count=strong_candidates_count,
        weak_candidates_count=weak_candidates_count,
        confirmed_findings_count=finding_counts["confirmed"],
        probable_findings_count=finding_counts["probable"],
        uncertain_findings_count=finding_counts["uncertain"],
        rejected_findings_count=finding_counts["rejected"],
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
        status=derive_report_status(
            findings,
            author_check=author_check,
            resource_link_matches=link_matches,
        ),
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


def _offline_limitation(enable_fuzzy: bool) -> str:
    return FUZZY_OFFLINE_LIMITATION if enable_fuzzy else OFFLINE_LIMITATION


def _get_registry_snapshot_date(registry_entries: list[RegistryEntry]) -> date | None:
    for entry in registry_entries:
        if entry.registry_snapshot_date is not None:
            return entry.registry_snapshot_date
    return None
