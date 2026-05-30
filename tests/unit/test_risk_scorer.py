from fa_checker.domain.enums import (
    ConfidenceLevel,
    DisambiguationDecision,
    EntityType,
    EvidenceSource,
    FindingStatus,
    LabelQuality,
    LabelStatus,
    MatchType,
    RiskLevel,
)
from fa_checker.domain.models import (
    CandidateMatch,
    DisambiguationResult,
    EvidenceFragment,
    LabelCheckResult,
    RegistryEntry,
)
from fa_checker.scoring.risk import (
    ScoringInput,
    score_candidate_match,
    score_candidate_matches,
)


def make_match(
    mention_text: str = "Илья Варламов",
    requires_disambiguation: bool = False,
    match_type: MatchType = MatchType.EXACT,
    score: float = 1.0,
) -> CandidateMatch:
    registry_entry = RegistryEntry(
        full_name="Варламов Илья Александрович",
        entity_type=EntityType.PERSON,
        normalized_name="варламов илья александрович",
        registry_source_url="https://minjust.gov.ru/registry",
    )
    return CandidateMatch(
        mention_text=mention_text,
        mention_start=0,
        mention_end=len(mention_text),
        registry_entry=registry_entry,
        match_type=match_type,
        match_score=score,
        evidence=[
            EvidenceFragment(
                source=EvidenceSource.ARTICLE_TEXT,
                text=mention_text,
                start=0,
                end=len(mention_text),
            )
        ],
        requires_disambiguation=requires_disambiguation,
    )


def make_label(label_quality: LabelQuality) -> LabelCheckResult:
    return LabelCheckResult(
        label_found=label_quality != LabelQuality.ABSENT,
        label_fragment="label" if label_quality != LabelQuality.ABSENT else None,
        label_distance=5 if label_quality == LabelQuality.EXACT else None,
        label_quality=label_quality,
    )


def make_disambiguation(
    decision: DisambiguationDecision,
    requires_human_review: bool = False,
) -> DisambiguationResult:
    return DisambiguationResult(
        decision=decision,
        confidence_score=0.8,
        rationale="Structured disambiguation fixture.",
        requires_human_review=requires_human_review,
    )


def assert_finding(
    *,
    finding,
    status: FindingStatus,
    risk_level: RiskLevel,
    confidence_level: ConfidenceLevel,
    label_status: LabelStatus,
    requires_human_review: bool,
) -> None:
    assert finding.status == status
    assert finding.risk_level == risk_level
    assert finding.confidence_level == confidence_level
    assert finding.label_status == label_status
    assert finding.requires_human_review is requires_human_review
    assert finding.entity_name == "Варламов Илья Александрович"
    assert finding.evidence


def test_exact_match_with_exact_label_scores_low_risk_confirmed() -> None:
    finding = score_candidate_match(make_match(), make_label(LabelQuality.EXACT))

    assert_finding(
        finding=finding,
        status=FindingStatus.CONFIRMED,
        risk_level=RiskLevel.LOW,
        confidence_level=ConfidenceLevel.HIGH,
        label_status=LabelStatus.PRESENT,
        requires_human_review=False,
    )


def test_exact_match_with_weak_label_scores_medium_risk_confirmed() -> None:
    finding = score_candidate_match(make_match(), make_label(LabelQuality.WEAK))

    assert_finding(
        finding=finding,
        status=FindingStatus.CONFIRMED,
        risk_level=RiskLevel.MEDIUM,
        confidence_level=ConfidenceLevel.HIGH,
        label_status=LabelStatus.WEAK,
        requires_human_review=True,
    )


def test_exact_match_with_absent_label_scores_high_risk_confirmed() -> None:
    finding = score_candidate_match(make_match(), make_label(LabelQuality.ABSENT))

    assert_finding(
        finding=finding,
        status=FindingStatus.CONFIRMED,
        risk_level=RiskLevel.HIGH,
        confidence_level=ConfidenceLevel.HIGH,
        label_status=LabelStatus.ABSENT,
        requires_human_review=True,
    )


def test_exact_match_without_label_check_scores_high_risk_not_checked() -> None:
    finding = score_candidate_match(make_match(), label_result=None)

    assert_finding(
        finding=finding,
        status=FindingStatus.CONFIRMED,
        risk_level=RiskLevel.HIGH,
        confidence_level=ConfidenceLevel.HIGH,
        label_status=LabelStatus.NOT_CHECKED,
        requires_human_review=True,
    )


def test_weak_alias_without_disambiguation_scores_uncertain() -> None:
    finding = score_candidate_match(
        make_match(
            mention_text="Варламов",
            requires_disambiguation=True,
            match_type=MatchType.ALIAS,
            score=0.55,
        ),
        make_label(LabelQuality.EXACT),
    )

    assert_finding(
        finding=finding,
        status=FindingStatus.UNCERTAIN,
        risk_level=RiskLevel.MEDIUM,
        confidence_level=ConfidenceLevel.LOW,
        label_status=LabelStatus.PRESENT,
        requires_human_review=True,
    )


def test_same_entity_disambiguation_with_absent_label_scores_high_risk() -> None:
    finding = score_candidate_match(
        make_match(requires_disambiguation=True, match_type=MatchType.ALIAS, score=0.55),
        make_label(LabelQuality.ABSENT),
        make_disambiguation(DisambiguationDecision.SAME_ENTITY),
    )

    assert_finding(
        finding=finding,
        status=FindingStatus.CONFIRMED,
        risk_level=RiskLevel.HIGH,
        confidence_level=ConfidenceLevel.HIGH,
        label_status=LabelStatus.ABSENT,
        requires_human_review=True,
    )


def test_same_entity_disambiguation_with_exact_label_can_skip_human_review() -> None:
    finding = score_candidate_match(
        make_match(requires_disambiguation=True, match_type=MatchType.ALIAS, score=0.55),
        make_label(LabelQuality.EXACT),
        make_disambiguation(DisambiguationDecision.SAME_ENTITY),
    )

    assert_finding(
        finding=finding,
        status=FindingStatus.CONFIRMED,
        risk_level=RiskLevel.LOW,
        confidence_level=ConfidenceLevel.HIGH,
        label_status=LabelStatus.PRESENT,
        requires_human_review=False,
    )


def test_likely_same_entity_with_exact_label_scores_probable_medium_risk() -> None:
    finding = score_candidate_match(
        make_match(requires_disambiguation=True, match_type=MatchType.ALIAS, score=0.55),
        make_label(LabelQuality.EXACT),
        make_disambiguation(DisambiguationDecision.LIKELY_SAME_ENTITY),
    )

    assert_finding(
        finding=finding,
        status=FindingStatus.PROBABLE,
        risk_level=RiskLevel.MEDIUM,
        confidence_level=ConfidenceLevel.MEDIUM,
        label_status=LabelStatus.PRESENT,
        requires_human_review=True,
    )


def test_uncertain_disambiguation_scores_uncertain_medium_risk() -> None:
    finding = score_candidate_match(
        make_match(requires_disambiguation=True, match_type=MatchType.ALIAS, score=0.55),
        make_label(LabelQuality.ABSENT),
        make_disambiguation(DisambiguationDecision.UNCERTAIN),
    )

    assert_finding(
        finding=finding,
        status=FindingStatus.UNCERTAIN,
        risk_level=RiskLevel.MEDIUM,
        confidence_level=ConfidenceLevel.LOW,
        label_status=LabelStatus.ABSENT,
        requires_human_review=True,
    )


def test_different_entity_disambiguation_scores_rejected_low_risk() -> None:
    finding = score_candidate_match(
        make_match(requires_disambiguation=True, match_type=MatchType.ALIAS, score=0.55),
        make_label(LabelQuality.EXACT),
        make_disambiguation(DisambiguationDecision.DIFFERENT_ENTITY),
    )

    assert_finding(
        finding=finding,
        status=FindingStatus.REJECTED,
        risk_level=RiskLevel.LOW,
        confidence_level=ConfidenceLevel.LOW,
        label_status=LabelStatus.PRESENT,
        requires_human_review=False,
    )
    assert finding.review_rationale == "Structured disambiguation fixture."


def test_batch_scoring_with_empty_list_returns_empty_list() -> None:
    assert score_candidate_matches([]) == []


def test_batch_scoring_preserves_order_without_aggregation() -> None:
    first_match = make_match(mention_text="Первый")
    second_match = make_match(mention_text="Второй")

    findings = score_candidate_matches(
        [
            ScoringInput(
                match=first_match,
                label_result=make_label(LabelQuality.EXACT),
            ),
            ScoringInput(
                match=second_match,
                label_result=make_label(LabelQuality.ABSENT),
            ),
        ]
    )

    assert len(findings) == 2
    assert findings[0].mention_text == "Первый"
    assert findings[1].mention_text == "Второй"
    assert findings[0].risk_level == RiskLevel.LOW
    assert findings[1].risk_level == RiskLevel.HIGH
