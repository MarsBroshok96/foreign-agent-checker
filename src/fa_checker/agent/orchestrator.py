"""Bounded agent review orchestrator for weak candidate disambiguation."""

from datetime import UTC, datetime

from fa_checker.agent.context_profiles import ContextProfile
from fa_checker.agent.disambiguation import disambiguate_candidate
from fa_checker.agent.state import AgentReviewState, AgentState, build_agent_review_state
from fa_checker.agent.tools import get_candidate_context, lookup_candidate_context_profile
from fa_checker.domain.enums import (
    DisambiguationDecision,
    FindingStatus,
    ReportStatus,
)
from fa_checker.domain.models import (
    Article,
    CheckReport,
    DisambiguationResult,
    FinalFinding,
    RegistryEntry,
)
from fa_checker.pipeline import run_deterministic_analysis
from fa_checker.scoring.risk import score_candidate_match

AGENT_REVIEW_LIMITATION = "Bounded LLM review applied to weak candidates."
NO_ENRICHMENT_LIMITATION = (
    "No fuzzy search, entity extraction, or internet enrichment was applied."
)
DETERMINISTIC_BASELINE_LIMITATION = (
    "Deterministic baseline ran before bounded review; fuzzy matching and "
    "agentic recall pass are not applied."
)


def run_bounded_review_check(
    article: Article,
    registry_entries: list[RegistryEntry],
    context_profiles: list[ContextProfile] | None = None,
    max_review_candidates: int = 20,
) -> CheckReport:
    """Run deterministic baseline and bounded LLM review for weak candidates."""
    analysis = run_deterministic_analysis(article, registry_entries)
    if not analysis.requires_agent_review:
        return _report_without_review(analysis.base_report)

    state = build_agent_review_state(analysis)
    profiles = context_profiles or []
    disambiguation_by_candidate: dict[int, DisambiguationResult] = {}
    limitations = _agent_limitations(analysis.limitations)

    review_candidates = state.review_candidates[: max(0, max_review_candidates)]
    if len(state.review_candidates) > len(review_candidates):
        limitations.append(
            "Some weak candidates were not reviewed because the review limit was reached."
        )

    for review_candidate in review_candidates:
        candidate_index = review_candidate.candidate_index
        context_text = _request_context_or_fallback(state, candidate_index, "small", limitations)
        profile = lookup_candidate_context_profile(state, candidate_index, profiles)
        result = disambiguate_candidate(
            state,
            candidate_index=candidate_index,
            context_text=context_text,
            context_profile=profile,
        )

        if result.decision == DisambiguationDecision.UNCERTAIN:
            context_text = _request_context_or_fallback(
                state,
                candidate_index,
                "large",
                limitations,
            )
            result = disambiguate_candidate(
                state,
                candidate_index=candidate_index,
                context_text=context_text,
                context_profile=profile,
            )

        disambiguation_by_candidate[candidate_index] = result

    state.weak_candidates_reviewed = True
    state.disambiguation_completed = True

    final_findings = _rescore_with_disambiguation(
        analysis.candidates,
        analysis.label_results,
        disambiguation_by_candidate,
    )
    state.final_findings = final_findings

    return CheckReport(
        article_url=article.url,
        article_title=article.title,
        article_author=article.author,
        checked_at=datetime.now(UTC),
        registry_snapshot_date=analysis.registry_snapshot_date,
        status=_derive_report_status(final_findings),
        findings=final_findings,
        limitations=_dedupe_limitations(limitations),
    )


def _report_without_review(report: CheckReport) -> CheckReport:
    limitations = [
        *report.limitations,
        "Agent review was not required because no weak candidates were found.",
    ]
    return report.model_copy(update={"limitations": _dedupe_limitations(limitations)})


def _agent_limitations(baseline_limitations: list[str]) -> list[str]:
    limitations = [
        DETERMINISTIC_BASELINE_LIMITATION,
        AGENT_REVIEW_LIMITATION,
        NO_ENRICHMENT_LIMITATION,
    ]
    for limitation in baseline_limitations:
        if limitation not in limitations and "LLM disambiguation" not in limitation:
            limitations.append(limitation)
    return limitations


def _request_context_or_fallback(
    state: AgentReviewState,
    candidate_index: int,
    window_size: str,
    limitations: list[str],
) -> str:
    try:
        get_candidate_context(state, candidate_index, window_size=window_size)
    except ValueError as exc:
        limitations.append(
            f"Context retrieval failed for candidate {candidate_index}; "
            "available evidence was used."
        )
        state.history.append(str(exc))
    return _get_best_candidate_context(state, candidate_index)


def _get_best_candidate_context(state: AgentReviewState, candidate_index: int) -> str:
    for review_candidate in state.review_candidates:
        if review_candidate.candidate_index == candidate_index:
            if review_candidate.evidence_texts:
                return review_candidate.evidence_texts[-1]
            return review_candidate.mention_text
    msg = f"Review candidate {candidate_index} was not found."
    raise ValueError(msg)


def _rescore_with_disambiguation(
    candidates,
    label_results,
    disambiguation_by_candidate: dict[int, DisambiguationResult],
) -> list[FinalFinding]:
    final_findings: list[FinalFinding] = []
    for candidate_index, candidate in enumerate(candidates):
        label_result = (
            label_results[candidate_index]
            if candidate_index < len(label_results)
            else None
        )
        final_findings.append(
            score_candidate_match(
                candidate,
                label_result=label_result,
                disambiguation=disambiguation_by_candidate.get(candidate_index),
            )
        )
    return final_findings


def _derive_report_status(findings: list[FinalFinding]) -> ReportStatus:
    if not findings:
        return ReportStatus.NO_MATCH
    if any(finding.status == FindingStatus.CONFIRMED for finding in findings):
        return ReportStatus.CONFIRMED_MATCH_FOUND
    if any(
        finding.status in {FindingStatus.PROBABLE, FindingStatus.UNCERTAIN}
        for finding in findings
    ):
        return ReportStatus.POTENTIAL_MATCH_FOUND
    return ReportStatus.NO_MATCH


def _dedupe_limitations(limitations: list[str]) -> list[str]:
    deduped: list[str] = []
    for limitation in limitations:
        if limitation not in deduped:
            deduped.append(limitation)
    return deduped


class AgentOrchestrator:
    """Compatibility wrapper for bounded review checks."""

    def run(self, state: AgentState) -> AgentState:
        return state

    def run_review(
        self,
        article: Article,
        registry_entries: list[RegistryEntry],
        context_profiles: list[ContextProfile] | None = None,
        max_review_candidates: int = 20,
    ) -> CheckReport:
        return run_bounded_review_check(
            article,
            registry_entries,
            context_profiles=context_profiles,
            max_review_candidates=max_review_candidates,
        )
