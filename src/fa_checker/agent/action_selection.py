"""LLM-backed bounded action selection for weak candidate review."""

import json
import re

from pydantic import ValidationError

from fa_checker.adapters.ollama_client import OllamaClientError, generate_ollama_response
from fa_checker.agent.context_profiles import ContextProfile
from fa_checker.agent.prompts import build_review_action_prompt
from fa_checker.agent.schemas import AgentReviewAction
from fa_checker.agent.state import AgentReviewState, ReviewCandidate
from fa_checker.config import get_settings

CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)
ACTION_PARSE_FALLBACK_REASON = "LLM action output could not be parsed safely."
ACTION_SELECTION_FALLBACK_REASON = "LLM action selection failed; human review required."


def parse_agent_review_action(raw_response: str) -> AgentReviewAction:
    """Parse model JSON into a safe AgentReviewAction."""
    try:
        data = json.loads(_strip_code_fence(raw_response))
        if not isinstance(data, dict):
            return _fallback_action(ACTION_PARSE_FALLBACK_REASON)
        data = _normalize_action_payload(data)
        if not isinstance(data.get("reason"), str) or not data["reason"].strip():
            return _fallback_action(ACTION_PARSE_FALLBACK_REASON)
        return AgentReviewAction.model_validate(data)
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
        return _fallback_action(ACTION_PARSE_FALLBACK_REASON)


def choose_review_action_with_llm(
    state: AgentReviewState,
    candidate: ReviewCandidate,
    available_context_texts: list[str],
    context_profile: ContextProfile | None,
    allowed_actions: list[str],
    model: str | None = None,
    base_url: str | None = None,
) -> AgentReviewAction:
    """Ask local Ollama to choose one bounded review action."""
    settings = get_settings()
    prompt = build_review_action_prompt(
        state=state,
        candidate=candidate,
        available_context_texts=available_context_texts,
        context_profile=context_profile,
        allowed_actions=allowed_actions,
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
        return _fallback_action(ACTION_SELECTION_FALLBACK_REASON)
    return parse_agent_review_action(raw_response)


def _strip_code_fence(raw_response: str) -> str:
    text = raw_response.strip()
    match = CODE_FENCE_RE.match(text)
    if match:
        return match.group(1).strip()
    return text


def _fallback_action(reason: str) -> AgentReviewAction:
    return AgentReviewAction(
        action_type="request_human_review",
        candidate_index=None,
        context_window_size=None,
        reason=reason,
    )


def _normalize_action_payload(data: dict) -> dict:
    normalized = dict(data)
    action_type = normalized.get("action_type")
    if isinstance(action_type, str):
        normalized["action_type"] = action_type.strip().lower()

    candidate_index = normalized.get("candidate_index")
    if isinstance(candidate_index, str):
        stripped_index = candidate_index.strip()
        if stripped_index.isdigit():
            normalized["candidate_index"] = int(stripped_index)

    context_window_size = normalized.get("context_window_size")
    if isinstance(context_window_size, str):
        stripped_window = context_window_size.strip()
        if stripped_window in {"", "null", "None", "none", "NULL"}:
            normalized["context_window_size"] = None
        else:
            normalized["context_window_size"] = stripped_window.lower()

    if normalized.get("action_type") != "request_context":
        window = normalized.get("context_window_size")
        if window not in {"small", "medium", "large"}:
            normalized["context_window_size"] = None

    return normalized
