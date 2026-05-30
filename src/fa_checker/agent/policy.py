"""Policy checks for bounded agent actions."""

from fa_checker.agent.schemas import AgentReviewAction
from fa_checker.agent.state import AgentReviewState, DeterministicAnalysisResult


def agent_review_required(analysis: DeterministicAnalysisResult) -> bool:
    return analysis.requires_agent_review


def allowed_review_actions(state: AgentReviewState) -> list[str]:
    actions: list[str] = []
    if state.review_candidates and not state.weak_candidates_reviewed:
        actions.extend(
            [
                "request_context",
                "request_human_review",
            ]
        )
    if can_finalize_review(state):
        actions.append("finalize")
    return actions


def can_finalize_review(state: AgentReviewState) -> bool:
    return (
        not state.review_candidates
        or state.weak_candidates_reviewed
        or state.disambiguation_completed
    )


def allowed_actions_for_candidate(
    state: AgentReviewState,
    candidate_index: int,
    has_context: bool,
    disambiguation_done: bool,
    human_review_requested: bool,
) -> list[str]:
    """Return allowed bounded actions for one weak candidate review step."""
    if human_review_requested or disambiguation_done:
        return ["finalize"]

    if not has_context:
        return ["request_context", "request_human_review"]

    actions: list[str] = []
    if state.context_requests_made.get(str(candidate_index), 0) < 2:
        actions.append("request_context")
    actions.extend(["disambiguate_candidate", "request_human_review"])
    return actions


def normalize_or_repair_action(
    action: AgentReviewAction,
    allowed_actions: list[str],
    has_context: bool,
    context_request_count: int,
    max_context_requests: int,
) -> AgentReviewAction:
    """Normalize one selected action or repair it to a safe allowed action."""
    if action.action_type in allowed_actions:
        if (
            action.action_type == "request_human_review"
            and has_context
            and "disambiguate_candidate" in allowed_actions
        ):
            return _repaired_action(
                "disambiguate_candidate",
                action,
                "Human review requested before disambiguation; action repaired.",
            )
        if action.action_type == "request_context" and action.context_window_size is None:
            return action.model_copy(
                update={
                    "context_window_size": (
                        "small" if context_request_count == 0 else "large"
                    )
                }
            )
        return action

    if action.action_type == "request_context":
        if (
            context_request_count >= max_context_requests
            and has_context
            and "disambiguate_candidate" in allowed_actions
        ):
            return _repaired_action(
                "disambiguate_candidate",
                action,
                "Context request limit reached; action repaired to disambiguation.",
            )
        if has_context and "disambiguate_candidate" in allowed_actions:
            return _repaired_action(
                "disambiguate_candidate",
                action,
                "Additional context was unavailable; action repaired to disambiguation.",
            )
        return _repaired_action(
            "request_human_review",
            action,
            "Context request was unavailable; human review required.",
        )

    if action.action_type == "disambiguate_candidate":
        if not has_context and "request_context" in allowed_actions:
            return _repaired_action(
                "request_context",
                action,
                "Context is required before disambiguation; action repaired.",
                context_window_size="small",
            )
        return _repaired_action(
            "request_human_review",
            action,
            "Disambiguation was unavailable; human review required.",
        )

    if action.action_type == "finalize":
        if has_context and "disambiguate_candidate" in allowed_actions:
            return _repaired_action(
                "disambiguate_candidate",
                action,
                "Finalize was premature; action repaired to disambiguation.",
            )
        return _repaired_action(
            "request_human_review",
            action,
            "Finalize was premature; human review required.",
        )

    return _repaired_action(
        "request_human_review",
        action,
        "Action was not allowed; human review required.",
    )


def _repaired_action(
    action_type: str,
    original_action: AgentReviewAction,
    reason: str,
    context_window_size: str | None = None,
) -> AgentReviewAction:
    return AgentReviewAction(
        action_type=action_type,
        candidate_index=original_action.candidate_index,
        context_window_size=context_window_size,
        reason=reason,
    )
