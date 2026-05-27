"""Structured state for the future bounded agent loop."""

from pydantic import BaseModel, Field


class AgentState(BaseModel):
    article_loaded: bool = False
    article_extracted: bool = False
    registry_loaded: bool = False
    candidate_generation_completed: bool = False
    exact_matches_count: int = Field(default=0, ge=0)
    weak_candidates_count: int = Field(default=0, ge=0)
    entities_extracted: bool = False
    recall_pass_completed: bool = False
    disambiguation_completed: bool = False
    label_check_completed: bool = False
    risk_scored: bool = False
    ready_to_report: bool = False
    tool_call_count: int = Field(default=0, ge=0)

