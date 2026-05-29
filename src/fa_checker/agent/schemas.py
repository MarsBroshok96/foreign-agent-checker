"""Schemas for future bounded agent review actions."""

from typing import Literal

from pydantic import BaseModel, Field

from fa_checker.domain.models import AgentAction, DisambiguationResult

ContextWindowSize = Literal["small", "medium", "large"]


class AgentReviewAction(BaseModel):
    action_type: Literal[
        "request_context",
        "disambiguate_candidate",
        "finalize",
        "request_human_review",
    ]
    candidate_index: int | None = Field(default=None, ge=0)
    context_window_size: ContextWindowSize | None = None
    reason: str


class AgentReviewPolicyDecision(BaseModel):
    allowed_actions: list[str] = Field(default_factory=list)
    reason: str


__all__ = [
    "AgentAction",
    "AgentReviewAction",
    "AgentReviewPolicyDecision",
    "ContextWindowSize",
    "DisambiguationResult",
]
