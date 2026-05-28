"""Deterministic conversion from candidate signals to final findings."""

from pydantic import BaseModel

from fa_checker.domain.enums import (
    ConfidenceLevel,
    DisambiguationDecision,
    FindingStatus,
    LabelQuality,
    LabelStatus,
    RiskLevel,
)
from fa_checker.domain.models import (
    CandidateMatch,
    DisambiguationResult,
    FinalFinding,
    LabelCheckResult,
)


class ScoringInput(BaseModel):
    match: CandidateMatch
    label_result: LabelCheckResult | None = None
    disambiguation: DisambiguationResult | None = None


def score_candidate_match(
    match: CandidateMatch,
    label_result: LabelCheckResult | None = None,
    disambiguation: DisambiguationResult | None = None,
) -> FinalFinding:
    """Score one candidate match without deciding overall article status."""
    label_status = _label_status(label_result)

    if disambiguation is not None:
        status, risk_level, confidence_level, requires_review, rationale = (
            _score_with_disambiguation(label_status, disambiguation)
        )
    elif match.requires_disambiguation:
        status = FindingStatus.UNCERTAIN
        risk_level = RiskLevel.MEDIUM
        confidence_level = ConfidenceLevel.LOW
        requires_review = True
        rationale = "Weak alias match requires disambiguation before confirmation."
    else:
        status, risk_level, confidence_level, requires_review, rationale = (
            _score_strong_match_without_disambiguation(label_status)
        )

    return FinalFinding(
        entity_name=match.registry_entry.full_name,
        mention_text=match.mention_text,
        status=status,
        risk_level=risk_level,
        confidence_level=confidence_level,
        label_status=label_status,
        requires_human_review=requires_review,
        evidence=match.evidence,
        rationale=rationale,
    )


def score_candidate_matches(items: list[ScoringInput]) -> list[FinalFinding]:
    """Score candidates in input order without aggregation."""
    return [
        score_candidate_match(
            item.match,
            label_result=item.label_result,
            disambiguation=item.disambiguation,
        )
        for item in items
    ]


def _label_status(label_result: LabelCheckResult | None) -> LabelStatus:
    if label_result is None:
        return LabelStatus.NOT_CHECKED
    if label_result.label_quality == LabelQuality.EXACT:
        return LabelStatus.PRESENT
    if label_result.label_quality == LabelQuality.WEAK:
        return LabelStatus.WEAK
    return LabelStatus.ABSENT


def _score_strong_match_without_disambiguation(
    label_status: LabelStatus,
) -> tuple[FindingStatus, RiskLevel, ConfidenceLevel, bool, str]:
    if label_status == LabelStatus.PRESENT:
        return (
            FindingStatus.CONFIRMED,
            RiskLevel.LOW,
            ConfidenceLevel.HIGH,
            False,
            "Strong exact registry match and nearby foreign-agent label found.",
        )
    if label_status == LabelStatus.WEAK:
        return (
            FindingStatus.CONFIRMED,
            RiskLevel.MEDIUM,
            ConfidenceLevel.HIGH,
            True,
            "Strong exact registry match found; label appears only at article level.",
        )
    if label_status == LabelStatus.ABSENT:
        return (
            FindingStatus.CONFIRMED,
            RiskLevel.HIGH,
            ConfidenceLevel.HIGH,
            True,
            "Strong exact registry match found, but label not found.",
        )
    return (
        FindingStatus.CONFIRMED,
        RiskLevel.HIGH,
        ConfidenceLevel.HIGH,
        True,
        "Strong exact registry match found, but label check was not performed.",
    )


def _score_with_disambiguation(
    label_status: LabelStatus,
    disambiguation: DisambiguationResult,
) -> tuple[FindingStatus, RiskLevel, ConfidenceLevel, bool, str]:
    if disambiguation.decision == DisambiguationDecision.SAME_ENTITY:
        return _score_same_entity(label_status, disambiguation)
    if disambiguation.decision == DisambiguationDecision.LIKELY_SAME_ENTITY:
        return (
            FindingStatus.PROBABLE,
            _risk_for_likely_same_entity(label_status),
            ConfidenceLevel.MEDIUM,
            True,
            "Candidate is likely the same entity and requires human review.",
        )
    if disambiguation.decision == DisambiguationDecision.UNCERTAIN:
        return (
            FindingStatus.UNCERTAIN,
            RiskLevel.MEDIUM,
            ConfidenceLevel.LOW,
            True,
            "Disambiguation remained uncertain and requires human review.",
        )
    return (
        FindingStatus.REJECTED,
        RiskLevel.LOW,
        ConfidenceLevel.LOW,
        disambiguation.requires_human_review,
        "Candidate rejected by disambiguation.",
    )


def _score_same_entity(
    label_status: LabelStatus,
    disambiguation: DisambiguationResult,
) -> tuple[FindingStatus, RiskLevel, ConfidenceLevel, bool, str]:
    risk_level = _risk_for_confirmed_entity(label_status)
    requires_review = (
        label_status != LabelStatus.PRESENT or disambiguation.requires_human_review
    )
    return (
        FindingStatus.CONFIRMED,
        risk_level,
        ConfidenceLevel.HIGH,
        requires_review,
        _same_entity_rationale(label_status),
    )


def _risk_for_confirmed_entity(label_status: LabelStatus) -> RiskLevel:
    if label_status == LabelStatus.PRESENT:
        return RiskLevel.LOW
    if label_status == LabelStatus.WEAK:
        return RiskLevel.MEDIUM
    return RiskLevel.HIGH


def _risk_for_likely_same_entity(label_status: LabelStatus) -> RiskLevel:
    if label_status in {LabelStatus.PRESENT, LabelStatus.WEAK}:
        return RiskLevel.MEDIUM
    return RiskLevel.HIGH


def _same_entity_rationale(label_status: LabelStatus) -> str:
    if label_status == LabelStatus.PRESENT:
        return "Disambiguation confirmed same entity and nearby label found."
    if label_status == LabelStatus.WEAK:
        return "Disambiguation confirmed same entity; label appears only at article level."
    if label_status == LabelStatus.ABSENT:
        return "Disambiguation confirmed same entity, but label not found."
    return "Disambiguation confirmed same entity, but label check was not performed."


def score_finding(finding: FinalFinding) -> RiskLevel:
    """Return the risk already assigned to a finding."""
    return finding.risk_level
