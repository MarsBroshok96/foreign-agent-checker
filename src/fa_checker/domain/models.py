"""Pydantic models that define stable boundaries between components."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from fa_checker.domain.enums import (
    AgentActionType,
    ConfidenceLevel,
    DisambiguationDecision,
    EntityType,
    EvidenceSource,
    FindingStatus,
    LabelQuality,
    LabelStatus,
    MatchType,
    ReportStatus,
    RiskLevel,
)


class Article(BaseModel):
    url: str
    source_domain: str
    title: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    text: str
    links: list[str] = Field(default_factory=list)

    @field_validator("url", "source_domain")
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        if not value.strip():
            msg = "value must not be empty"
            raise ValueError(msg)
        return value


class RegistryEntry(BaseModel):
    registry_id: str | None = None
    full_name: str
    entity_type: EntityType
    normalized_name: str
    aliases: list[str] = Field(default_factory=list)
    registry_source_url: str
    registry_snapshot_date: date | None = None
    raw_fields: dict[str, Any] = Field(default_factory=dict)

    @field_validator("full_name", "normalized_name", "registry_source_url")
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        if not value.strip():
            msg = "value must not be empty"
            raise ValueError(msg)
        return value


class ContextProfile(BaseModel):
    registry_id: str | None = None
    entity_name: str
    entity_type: str
    known_descriptors: list[str] = Field(default_factory=list)
    known_projects: list[str] = Field(default_factory=list)
    known_domains: list[str] = Field(default_factory=list)
    notes: str | None = None
    sources: list[str] = Field(default_factory=list)
    retrieved_at: datetime | None = None


class EvidenceFragment(BaseModel):
    source: EvidenceSource
    text: str
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, ge=0)

    @field_validator("text")
    @classmethod
    def require_text(cls, value: str) -> str:
        if not value.strip():
            msg = "evidence text must not be empty"
            raise ValueError(msg)
        return value


class CandidateMatch(BaseModel):
    mention_text: str
    mention_start: int | None = Field(default=None, ge=0)
    mention_end: int | None = Field(default=None, ge=0)
    registry_entry: RegistryEntry
    match_type: MatchType
    match_score: float = Field(ge=0.0, le=1.0)
    evidence: list[EvidenceFragment] = Field(default_factory=list)
    requires_disambiguation: bool


class DisambiguationResult(BaseModel):
    decision: DisambiguationDecision
    confidence_score: float = Field(ge=0.0, le=1.0)
    rationale: str
    requires_human_review: bool


class LabelCheckResult(BaseModel):
    label_found: bool
    label_fragment: str | None = None
    label_distance: int | None = Field(default=None, ge=0)
    label_quality: LabelQuality


class ResourceLinkMatch(BaseModel):
    registry_id: str | None = None
    entity_name: str
    entity_type: str | None = None
    article_url: str
    registry_url: str
    normalized_article_url: str
    normalized_registry_url: str
    rationale: str = "Article contains a full link matching a registry resource URL."


class AuthorCheckResult(BaseModel):
    author_name: str | None = None
    status: str
    registry_id: str | None = None
    entity_name: str | None = None
    match_type: str | None = None
    match_score: float | None = Field(default=None, ge=0.0, le=1.0)
    requires_human_review: bool = False
    rationale: str


class FinalFinding(BaseModel):
    entity_name: str
    mention_text: str
    status: FindingStatus
    risk_level: RiskLevel
    confidence_level: ConfidenceLevel
    label_status: LabelStatus
    requires_human_review: bool
    evidence: list[EvidenceFragment] = Field(default_factory=list)
    rationale: str
    review_rationale: str | None = None


class ProcessingSummary(BaseModel):
    mode: str = "deterministic"
    deterministic_candidates_total: int = Field(default=0, ge=0)
    deterministic_strong_candidates: int = Field(default=0, ge=0)
    deterministic_weak_candidates: int = Field(default=0, ge=0)
    deterministic_confirmed_findings: int = Field(default=0, ge=0)
    deterministic_probable_findings: int = Field(default=0, ge=0)
    deterministic_uncertain_findings: int = Field(default=0, ge=0)
    deterministic_rejected_findings: int = Field(default=0, ge=0)
    agentic_review_applied: bool = False
    agentic_review_candidates_total: int = Field(default=0, ge=0)
    agentic_reviewed_candidates: int = Field(default=0, ge=0)
    agentic_confirmed_after_review: int = Field(default=0, ge=0)
    agentic_probable_after_review: int = Field(default=0, ge=0)
    agentic_uncertain_after_review: int = Field(default=0, ge=0)
    agentic_rejected_after_review: int = Field(default=0, ge=0)
    final_findings_total: int = Field(default=0, ge=0)
    final_confirmed_findings: int = Field(default=0, ge=0)
    final_probable_findings: int = Field(default=0, ge=0)
    final_uncertain_findings: int = Field(default=0, ge=0)
    final_rejected_findings: int = Field(default=0, ge=0)
    final_requires_human_review: int = Field(default=0, ge=0)
    resource_link_matches_total: int = Field(default=0, ge=0)
    author_check_status: str | None = None
    author_requires_human_review: bool = False


class CheckReport(BaseModel):
    article_url: str
    article_title: str | None = None
    article_author: str | None = None
    checked_at: datetime
    registry_snapshot_date: date | None = None
    status: ReportStatus
    findings: list[FinalFinding] = Field(default_factory=list)
    resource_link_matches: list[ResourceLinkMatch] = Field(default_factory=list)
    author_check: AuthorCheckResult | None = None
    limitations: list[str] = Field(default_factory=list)
    processing_summary: ProcessingSummary | None = None


class AgentAction(BaseModel):
    action_type: AgentActionType
    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    reason: str
