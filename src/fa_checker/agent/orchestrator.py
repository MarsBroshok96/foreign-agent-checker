"""Bounded agent review orchestrator for weak candidate disambiguation."""

from datetime import UTC, datetime

from fa_checker.agent.action_selection import choose_review_action_with_llm
from fa_checker.agent.context_profiles import ContextProfile
from fa_checker.agent.disambiguation import disambiguate_candidate
from fa_checker.agent.policy import allowed_actions_for_candidate, normalize_or_repair_action
from fa_checker.agent.schemas import AgentReviewAction
from fa_checker.agent.state import AgentReviewState, build_agent_review_state
from fa_checker.agent.tools import (
    MAX_CONTEXT_REQUESTS_PER_CANDIDATE,
    get_candidate_context,
    lookup_candidate_context_profile,
)
from fa_checker.domain.enums import (
    DisambiguationDecision,
    MatchType,
)
from fa_checker.domain.models import (
    Article,
    CheckReport,
    DisambiguationResult,
    FinalFinding,
    RegistryEntry,
)
from fa_checker.pipeline import run_deterministic_analysis
from fa_checker.reporting.summary import build_processing_summary, derive_report_status
from fa_checker.scoring.risk import score_candidate_match

AGENT_REVIEW_LIMITATION = "Bounded LLM review applied to weak candidates."
NO_ENRICHMENT_LIMITATION = "No entity extraction or internet enrichment was applied."
NO_FUZZY_ENRICHMENT_LIMITATION = (
    "No person-only fuzzy recall, entity extraction, or internet enrichment was applied."
)
DETERMINISTIC_BASELINE_WITH_FUZZY_LIMITATION = (
    "Deterministic baseline ran before bounded review with person-only fuzzy recall enabled."
)
DETERMINISTIC_BASELINE_WITHOUT_FUZZY_LIMITATION = (
    "Deterministic baseline ran before bounded review; person-only fuzzy recall was not enabled."
)


def run_bounded_review_check(
    article: Article,
    registry_entries: list[RegistryEntry],
    context_profiles: list[ContextProfile] | None = None,
    max_review_candidates: int = 20,
    max_steps_per_candidate: int = 5,
    enable_fuzzy: bool = False,
) -> CheckReport:
    """Run deterministic baseline and bounded LLM review for weak candidates."""
    analysis = run_deterministic_analysis(
        article,
        registry_entries,
        enable_fuzzy=enable_fuzzy,
    )
    if not analysis.requires_agent_review:
        return _report_without_review(analysis.base_report)

    state = build_agent_review_state(analysis)
    profiles = context_profiles or []
    disambiguation_by_candidate: dict[int, DisambiguationResult] = {}
    limitations = _agent_limitations(
        analysis.limitations,
        fuzzy_enabled=_analysis_fuzzy_enabled(analysis),
    )

    review_candidates = state.review_candidates[: max(0, max_review_candidates)]
    reviewed_candidate_indexes = [
        review_candidate.candidate_index for review_candidate in review_candidates
    ]
    if len(state.review_candidates) > len(review_candidates):
        limitations.append(
            "Some weak candidates were not reviewed because the review limit was reached."
        )

    for review_candidate in review_candidates:
        candidate_index = review_candidate.candidate_index
        profile = lookup_candidate_context_profile(state, candidate_index, profiles)
        result = _run_candidate_action_loop(
            state=state,
            review_candidate=review_candidate,
            context_profile=profile,
            max_steps=max_steps_per_candidate,
            limitations=limitations,
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
        status=derive_report_status(
            final_findings,
            author_check=analysis.author_check,
            resource_link_matches=analysis.resource_link_matches,
        ),
        findings=final_findings,
        resource_link_matches=analysis.resource_link_matches,
        author_check=analysis.author_check,
        limitations=_dedupe_limitations(limitations),
        processing_summary=build_processing_summary(
            mode="agentic",
            deterministic_candidates_total=len(analysis.candidates),
            deterministic_strong_candidates=analysis.strong_candidates_count,
            deterministic_weak_candidates=analysis.weak_candidates_count,
            deterministic_fuzzy_candidates=sum(
                candidate.match_type == MatchType.FUZZY for candidate in analysis.candidates
            ),
            fuzzy_enabled=_analysis_fuzzy_enabled(analysis),
            deterministic_findings=analysis.findings,
            final_findings=final_findings,
            author_check=analysis.author_check,
            resource_link_matches=analysis.resource_link_matches,
            agentic_review_applied=bool(analysis.requires_agent_review),
            agentic_review_candidates_total=analysis.weak_candidates_count,
            agentic_reviewed_candidates=len(reviewed_candidate_indexes),
            agentic_reviewed_candidate_indexes=set(reviewed_candidate_indexes),
        ),
    )


def _report_without_review(report: CheckReport) -> CheckReport:
    limitations = [
        *report.limitations,
        "Agent review was not required because no weak candidates were found.",
    ]
    return report.model_copy(update={"limitations": _dedupe_limitations(limitations)})


def _agent_limitations(
    baseline_limitations: list[str],
    fuzzy_enabled: bool,
) -> list[str]:
    limitations = [
        (
            DETERMINISTIC_BASELINE_WITH_FUZZY_LIMITATION
            if fuzzy_enabled
            else DETERMINISTIC_BASELINE_WITHOUT_FUZZY_LIMITATION
        ),
        AGENT_REVIEW_LIMITATION,
        NO_ENRICHMENT_LIMITATION if fuzzy_enabled else NO_FUZZY_ENRICHMENT_LIMITATION,
    ]
    for limitation in baseline_limitations:
        if limitation not in limitations and "LLM disambiguation" not in limitation:
            limitations.append(limitation)
    return limitations


def _analysis_fuzzy_enabled(analysis) -> bool:
    summary = analysis.base_report.processing_summary
    return summary.fuzzy_enabled if summary is not None else False


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


def _run_candidate_action_loop(
    state: AgentReviewState,
    review_candidate,
    context_profile: ContextProfile | None,
    max_steps: int,
    limitations: list[str],
) -> DisambiguationResult:
    candidate_index = review_candidate.candidate_index
    available_context_texts: list[str] = []
    disambiguation_result: DisambiguationResult | None = None
    human_review_requested = False

    for _ in range(max(0, max_steps)):
        has_context = bool(available_context_texts)
        context_request_count = state.context_requests_made.get(str(candidate_index), 0)
        allowed_actions = allowed_actions_for_candidate(
            state,
            candidate_index=candidate_index,
            has_context=has_context,
            disambiguation_done=disambiguation_result is not None,
            human_review_requested=human_review_requested,
        )
        selected_action = choose_review_action_with_llm(
            state=state,
            candidate=review_candidate,
            available_context_texts=available_context_texts,
            context_profile=context_profile,
            allowed_actions=allowed_actions,
        )
        state.history.append(
            f"LLM requested action {selected_action.action_type} "
            f"for candidate {candidate_index}."
        )
        action = normalize_or_repair_action(
            selected_action,
            allowed_actions=allowed_actions,
            has_context=has_context,
            context_request_count=context_request_count,
            max_context_requests=MAX_CONTEXT_REQUESTS_PER_CANDIDATE,
        )
        if action != selected_action:
            state.history.append(
                f"Action repaired from {selected_action.action_type} to "
                f"{action.action_type} for candidate {candidate_index}: {action.reason}"
            )

        if not _is_valid_action(action, candidate_index, allowed_actions):
            limitations.append(
                f"Invalid review action for candidate {candidate_index}; "
                "human review required."
            )
            state.history.append(f"Invalid review action for candidate {candidate_index}.")
            return _conservative_disambiguation(
                "LLM action selection failed; human review required."
            )

        if action.action_type == "request_context":
            context_text = _request_context_or_fallback(
                state,
                candidate_index,
                action.context_window_size or "small",
                limitations,
            )
            if context_text not in available_context_texts:
                available_context_texts.append(context_text)
            continue

        if action.action_type == "disambiguate_candidate":
            context_text = (
                available_context_texts[-1]
                if available_context_texts
                else _get_best_candidate_context(state, candidate_index)
            )
            disambiguation_result = disambiguate_candidate(
                state,
                candidate_index=candidate_index,
                context_text=context_text,
                context_profile=context_profile,
            )
            state.history.append(
                "Candidate "
                f"{candidate_index} review ended with disambiguation decision "
                f"{disambiguation_result.decision}."
            )
            return disambiguation_result

        if action.action_type == "request_human_review":
            human_review_requested = True
            disambiguation_result = _conservative_disambiguation(
                "LLM review requested human review."
            )
            state.history.append(
                f"Candidate {candidate_index} review ended with human review request."
            )
            return disambiguation_result

        if action.action_type == "finalize":
            return disambiguation_result or _conservative_disambiguation(
                "LLM review requested human review."
            )

    limitations.append(
        f"Candidate {candidate_index} review exceeded the maximum step limit; "
        "human review required."
    )
    return disambiguation_result or _conservative_disambiguation(
        "LLM action selection failed; human review required."
    )


def _is_valid_action(
    action: AgentReviewAction,
    candidate_index: int,
    allowed_actions: list[str],
) -> bool:
    if action.action_type not in allowed_actions:
        return False
    if action.candidate_index not in {None, candidate_index}:
        return False
    return not (
        action.action_type == "request_context"
        and action.context_window_size is None
    )


def _conservative_disambiguation(rationale: str) -> DisambiguationResult:
    return DisambiguationResult(
        decision=DisambiguationDecision.UNCERTAIN,
        confidence_score=0.0,
        requires_human_review=True,
        rationale=rationale,
    )


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


def _dedupe_limitations(limitations: list[str]) -> list[str]:
    deduped: list[str] = []
    for limitation in limitations:
        if limitation not in deduped:
            deduped.append(limitation)
    return deduped
