"""Deterministic support tools for future bounded agent review."""

from fa_checker.agent.context_profiles import ContextProfile, find_context_profile
from fa_checker.agent.schemas import ContextWindowSize
from fa_checker.agent.state import AgentReviewState, ReviewCandidate
from fa_checker.article.context import get_context_window

WINDOW_SIZES: dict[ContextWindowSize, int] = {
    "small": 160,
    "medium": 400,
    "large": 900,
}
MAX_CONTEXT_REQUESTS_PER_CANDIDATE = 2


def get_candidate_context(
    state: AgentReviewState,
    candidate_index: int,
    window_size: ContextWindowSize = "small",
) -> AgentReviewState:
    """Append bounded article context for a review candidate."""
    review_candidate = _find_review_candidate(state, candidate_index)
    request_key = str(candidate_index)
    request_count = state.context_requests_made.get(request_key, 0)
    if request_count >= MAX_CONTEXT_REQUESTS_PER_CANDIDATE:
        msg = f"Context request limit exceeded for candidate {candidate_index}."
        raise ValueError(msg)

    state.context_requests_made[request_key] = request_count + 1
    candidate = _get_original_candidate(state, candidate_index)
    context_text = _candidate_context_text(state, review_candidate, candidate, window_size)
    if context_text not in review_candidate.evidence_texts:
        review_candidate.evidence_texts.append(context_text)

    state.history.append(
        f"Context requested for candidate {candidate_index} with {window_size} window."
    )
    return state


def lookup_candidate_context_profile(
    state: AgentReviewState,
    candidate_index: int,
    profiles: list[ContextProfile],
) -> ContextProfile | None:
    """Look up a local auxiliary context profile for a review candidate."""
    _find_review_candidate(state, candidate_index)
    candidate = _get_original_candidate(state, candidate_index)
    profile = find_context_profile(
        profiles,
        registry_id=candidate.registry_entry.registry_id,
        entity_name=candidate.registry_entry.full_name,
    )
    if profile is None:
        state.history.append(f"Context profile not found for candidate {candidate_index}.")
    else:
        state.history.append(f"Context profile found for candidate {candidate_index}.")
    return profile


def _find_review_candidate(state: AgentReviewState, candidate_index: int) -> ReviewCandidate:
    for review_candidate in state.review_candidates:
        if review_candidate.candidate_index == candidate_index:
            return review_candidate
    msg = f"Review candidate {candidate_index} was not found."
    raise ValueError(msg)


def _get_original_candidate(state: AgentReviewState, candidate_index: int):
    try:
        return state.deterministic_result.candidates[candidate_index]
    except IndexError as exc:
        msg = f"Candidate {candidate_index} was not found in deterministic result."
        raise ValueError(msg) from exc


def _candidate_context_text(
    state: AgentReviewState,
    review_candidate: ReviewCandidate,
    candidate,
    window_size: ContextWindowSize,
) -> str:
    if candidate.mention_start is not None and candidate.mention_end is not None:
        try:
            fragment = get_context_window(
                state.deterministic_result.article.text,
                candidate.mention_start,
                candidate.mention_end,
                WINDOW_SIZES[window_size],
            )
            return fragment.text
        except ValueError:
            state.history.append(
                f"Context window fallback used for candidate {review_candidate.candidate_index}."
            )

    if review_candidate.evidence_texts:
        return review_candidate.evidence_texts[0]

    msg = f"Candidate {review_candidate.candidate_index} has no usable context evidence."
    raise ValueError(msg)
