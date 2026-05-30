"""Structured state for the future bounded agent loop."""

from datetime import date

from pydantic import BaseModel, Field

from fa_checker.domain.models import (
    Article,
    AuthorCheckResult,
    CandidateMatch,
    CheckReport,
    FinalFinding,
    LabelCheckResult,
    ResourceLinkMatch,
)


class DeterministicAnalysisResult(BaseModel):
    article: Article
    registry_snapshot_date: date | None = None
    candidates: list[CandidateMatch] = Field(default_factory=list)
    label_results: list[LabelCheckResult] = Field(default_factory=list)
    resource_link_matches: list[ResourceLinkMatch] = Field(default_factory=list)
    author_check: AuthorCheckResult | None = None
    findings: list[FinalFinding] = Field(default_factory=list)
    base_report: CheckReport
    strong_candidates_count: int = Field(ge=0)
    weak_candidates_count: int = Field(ge=0)
    confirmed_findings_count: int = Field(ge=0)
    probable_findings_count: int = Field(ge=0)
    uncertain_findings_count: int = Field(ge=0)
    rejected_findings_count: int = Field(ge=0)
    requires_agent_review: bool
    limitations: list[str] = Field(default_factory=list)


class ReviewCandidate(BaseModel):
    candidate_index: int = Field(ge=0)
    entity_name: str
    mention_text: str
    match_type: str
    match_score: float = Field(ge=0.0, le=1.0)
    requires_disambiguation: bool
    risk_level: str | None = None
    finding_status: str | None = None
    evidence_texts: list[str] = Field(default_factory=list)


class AgentReviewState(BaseModel):
    deterministic_result: DeterministicAnalysisResult
    review_candidates: list[ReviewCandidate] = Field(default_factory=list)
    weak_candidates_reviewed: bool = False
    context_requests_made: dict[str, int] = Field(default_factory=dict)
    disambiguation_completed: bool = False
    final_findings: list[FinalFinding] = Field(default_factory=list)
    history: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


def build_agent_review_state(analysis: DeterministicAnalysisResult) -> AgentReviewState:
    """Build initial state for future weak-candidate review."""
    review_candidates: list[ReviewCandidate] = []
    for candidate_index, candidate in enumerate(analysis.candidates):
        if not candidate.requires_disambiguation:
            continue
        finding = (
            analysis.findings[candidate_index]
            if candidate_index < len(analysis.findings)
            else None
        )
        review_candidates.append(
            ReviewCandidate(
                candidate_index=candidate_index,
                entity_name=candidate.registry_entry.full_name,
                mention_text=candidate.mention_text,
                match_type=candidate.match_type.value,
                match_score=candidate.match_score,
                requires_disambiguation=candidate.requires_disambiguation,
                risk_level=finding.risk_level.value if finding is not None else None,
                finding_status=finding.status.value if finding is not None else None,
                evidence_texts=_collect_evidence_texts(candidate, finding),
            )
        )

    return AgentReviewState(
        deterministic_result=analysis,
        review_candidates=review_candidates,
        final_findings=list(analysis.findings),
        history=["Built agent review state from deterministic analysis."],
        limitations=list(analysis.limitations),
    )


def _collect_evidence_texts(
    candidate: CandidateMatch,
    finding: FinalFinding | None,
) -> list[str]:
    evidence_texts: list[str] = []
    for evidence in candidate.evidence:
        if evidence.text not in evidence_texts:
            evidence_texts.append(evidence.text)
    if finding is not None:
        for evidence in finding.evidence:
            if evidence.text not in evidence_texts:
                evidence_texts.append(evidence.text)
    return evidence_texts
