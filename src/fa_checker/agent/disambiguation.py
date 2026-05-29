"""Bounded candidate disambiguation tool backed by local Ollama."""

import json
import re
from typing import Any

from pydantic import ValidationError

from fa_checker.adapters.ollama_client import OllamaClientError, generate_ollama_response
from fa_checker.agent.context_profiles import ContextProfile
from fa_checker.agent.prompts import build_disambiguation_prompt
from fa_checker.agent.state import AgentReviewState, ReviewCandidate
from fa_checker.config import get_settings
from fa_checker.domain.enums import DisambiguationDecision
from fa_checker.domain.models import DisambiguationResult

CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)
PARSE_FALLBACK_RATIONALE = "LLM output could not be parsed safely."
OLLAMA_FALLBACK_RATIONALE = "LLM disambiguation failed; human review required."


def parse_disambiguation_result(raw_response: str) -> DisambiguationResult:
    """Parse LLM JSON into a safe DisambiguationResult."""
    try:
        data = json.loads(_strip_code_fence(raw_response))
        if not isinstance(data, dict):
            return _fallback_result(PARSE_FALLBACK_RATIONALE)
        if not isinstance(data.get("requires_human_review"), bool):
            return _fallback_result(PARSE_FALLBACK_RATIONALE)
        if not isinstance(data.get("rationale"), str) or not data["rationale"].strip():
            return _fallback_result(PARSE_FALLBACK_RATIONALE)
        return DisambiguationResult.model_validate(data)
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
        return _fallback_result(PARSE_FALLBACK_RATIONALE)


def disambiguate_candidate(
    state: AgentReviewState,
    candidate_index: int,
    context_text: str,
    context_profile: ContextProfile | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> DisambiguationResult:
    """Run bounded local-LLM disambiguation for one review candidate."""
    review_candidate = _find_review_candidate(state, candidate_index)
    candidate = _get_original_candidate(state, candidate_index)
    settings = get_settings()
    prompt = build_disambiguation_prompt(
        candidate=review_candidate,
        registry_entry=candidate.registry_entry,
        context_text=context_text,
        context_profile=context_profile,
    )

    try:
        raw_response = generate_ollama_response(
            prompt=prompt,
            model=model or settings.ollama_model,
            base_url=base_url or settings.ollama_base_url,
            format_json=True,
            temperature=0.0,
        )
    except OllamaClientError:
        state.history.append(f"LLM disambiguation failed for candidate {candidate_index}.")
        return _fallback_result(OLLAMA_FALLBACK_RATIONALE)

    result = parse_disambiguation_result(raw_response)
    state.history.append(f"LLM disambiguation completed for candidate {candidate_index}.")
    return result


def _strip_code_fence(raw_response: str) -> str:
    text = raw_response.strip()
    match = CODE_FENCE_RE.match(text)
    if match:
        return match.group(1).strip()
    return text


def _fallback_result(rationale: str) -> DisambiguationResult:
    return DisambiguationResult(
        decision=DisambiguationDecision.UNCERTAIN,
        confidence_score=0.0,
        requires_human_review=True,
        rationale=rationale,
    )


def _find_review_candidate(state: AgentReviewState, candidate_index: int) -> ReviewCandidate:
    for review_candidate in state.review_candidates:
        if review_candidate.candidate_index == candidate_index:
            return review_candidate
    msg = f"Review candidate {candidate_index} was not found."
    raise ValueError(msg)


def _get_original_candidate(state: AgentReviewState, candidate_index: int) -> Any:
    try:
        return state.deterministic_result.candidates[candidate_index]
    except IndexError as exc:
        msg = f"Candidate {candidate_index} was not found in deterministic result."
        raise ValueError(msg) from exc
