from fa_checker.domain.enums import (
    ConfidenceLevel,
    EvidenceSource,
    FindingStatus,
    LabelStatus,
    MatchType,
    ReportStatus,
    RiskLevel,
)
from fa_checker.domain.models import (
    AuthorCheckResult,
    EvidenceFragment,
    FinalFinding,
    ResourceLinkMatch,
)
from fa_checker.reporting.summary import (
    build_processing_summary,
    count_findings,
    derive_report_status,
)


def make_finding(
    status: FindingStatus,
    requires_human_review: bool = False,
) -> FinalFinding:
    return FinalFinding(
        entity_name=f"Entity {status.value}",
        mention_text=status.value,
        match_type=MatchType.EXACT,
        match_score=1.0,
        status=status,
        risk_level=RiskLevel.HIGH,
        confidence_level=ConfidenceLevel.HIGH,
        label_status=LabelStatus.ABSENT,
        requires_human_review=requires_human_review,
        evidence=[
            EvidenceFragment(
                source=EvidenceSource.ARTICLE_TEXT,
                text=f"Evidence for {status.value}",
            )
        ],
        rationale=f"Rationale for {status.value}.",
    )


def make_author_check(status: str) -> AuthorCheckResult:
    return AuthorCheckResult(
        author_name="Author",
        status=status,
        requires_human_review=status == "weak_match",
        rationale=f"Author status is {status}.",
    )


def make_resource_link_match() -> ResourceLinkMatch:
    return ResourceLinkMatch(
        entity_name="Linked Entity",
        article_url="https://example.org/article",
        registry_url="https://example.org/article",
        normalized_article_url="https://example.org/article",
        normalized_registry_url="https://example.org/article",
    )


def test_derive_report_status_no_findings_returns_no_match() -> None:
    assert derive_report_status([]) == ReportStatus.NO_MATCH


def test_derive_report_status_confirmed_finding_returns_confirmed() -> None:
    assert derive_report_status([make_finding(FindingStatus.CONFIRMED)]) == (
        ReportStatus.CONFIRMED_MATCH_FOUND
    )


def test_derive_report_status_probable_finding_returns_potential() -> None:
    assert derive_report_status([make_finding(FindingStatus.PROBABLE)]) == (
        ReportStatus.POTENTIAL_MATCH_FOUND
    )


def test_derive_report_status_uncertain_finding_returns_potential() -> None:
    assert derive_report_status([make_finding(FindingStatus.UNCERTAIN)]) == (
        ReportStatus.POTENTIAL_MATCH_FOUND
    )


def test_derive_report_status_rejected_only_returns_no_match() -> None:
    assert derive_report_status([make_finding(FindingStatus.REJECTED)]) == (
        ReportStatus.NO_MATCH
    )


def test_derive_report_status_resource_link_returns_confirmed() -> None:
    assert derive_report_status([], resource_link_matches=[make_resource_link_match()]) == (
        ReportStatus.CONFIRMED_MATCH_FOUND
    )


def test_derive_report_status_strong_author_returns_confirmed() -> None:
    assert derive_report_status([], author_check=make_author_check("strong_match")) == (
        ReportStatus.CONFIRMED_MATCH_FOUND
    )


def test_derive_report_status_weak_author_returns_potential() -> None:
    assert derive_report_status([], author_check=make_author_check("weak_match")) == (
        ReportStatus.POTENTIAL_MATCH_FOUND
    )


def test_derive_report_status_confirmed_finding_wins_over_weak_author() -> None:
    assert derive_report_status(
        [make_finding(FindingStatus.CONFIRMED)],
        author_check=make_author_check("weak_match"),
    ) == ReportStatus.CONFIRMED_MATCH_FOUND


def test_derive_report_status_rejected_with_resource_link_returns_confirmed() -> None:
    assert derive_report_status(
        [make_finding(FindingStatus.REJECTED)],
        resource_link_matches=[make_resource_link_match()],
    ) == ReportStatus.CONFIRMED_MATCH_FOUND


def test_count_findings_counts_statuses_and_review_flags() -> None:
    counts = count_findings(
        [
            make_finding(FindingStatus.CONFIRMED),
            make_finding(FindingStatus.PROBABLE, requires_human_review=True),
            make_finding(FindingStatus.UNCERTAIN, requires_human_review=True),
            make_finding(FindingStatus.REJECTED),
        ]
    )

    assert counts == {
        "total": 4,
        "confirmed": 1,
        "probable": 1,
        "uncertain": 1,
        "rejected": 1,
        "requires_human_review": 2,
        "active": 2,
        "active_no_human_review": 1,
    }


def test_build_processing_summary_deterministic_fields() -> None:
    findings = [
        make_finding(FindingStatus.CONFIRMED),
        make_finding(FindingStatus.UNCERTAIN, requires_human_review=True),
    ]

    summary = build_processing_summary(
        mode="deterministic",
        deterministic_candidates_total=2,
        deterministic_strong_candidates=1,
        deterministic_weak_candidates=1,
        deterministic_fuzzy_candidates=0,
        fuzzy_enabled=False,
        deterministic_findings=findings,
        final_findings=findings,
    )

    assert summary.mode == "deterministic"
    assert summary.deterministic_candidates_total == 2
    assert summary.deterministic_strong_candidates == 1
    assert summary.deterministic_weak_candidates == 1
    assert summary.deterministic_confirmed_findings == 1
    assert summary.deterministic_uncertain_findings == 1
    assert summary.final_findings_total == 2
    assert summary.final_confirmed_findings == 1
    assert summary.final_uncertain_findings == 1
    assert summary.final_requires_human_review == 1


def test_build_processing_summary_agentic_fields() -> None:
    deterministic_findings = [
        make_finding(FindingStatus.CONFIRMED),
        make_finding(FindingStatus.UNCERTAIN, requires_human_review=True),
    ]
    final_findings = [
        make_finding(FindingStatus.CONFIRMED),
        make_finding(FindingStatus.REJECTED),
    ]

    summary = build_processing_summary(
        mode="agentic",
        deterministic_candidates_total=2,
        deterministic_strong_candidates=1,
        deterministic_weak_candidates=1,
        deterministic_fuzzy_candidates=0,
        fuzzy_enabled=False,
        deterministic_findings=deterministic_findings,
        final_findings=final_findings,
        agentic_review_applied=True,
        agentic_review_candidates_total=1,
        agentic_reviewed_candidates=1,
        agentic_reviewed_candidate_indexes={1},
    )

    assert summary.mode == "agentic"
    assert summary.agentic_review_applied is True
    assert summary.agentic_review_candidates_total == 1
    assert summary.agentic_reviewed_candidates == 1
    assert summary.agentic_rejected_after_review == 1
    assert summary.agentic_confirmed_after_review == 0
    assert summary.final_confirmed_findings == 1
    assert summary.final_rejected_findings == 1


def test_build_processing_summary_propagates_fuzzy_fields() -> None:
    summary = build_processing_summary(
        mode="deterministic",
        deterministic_candidates_total=3,
        deterministic_strong_candidates=1,
        deterministic_weak_candidates=2,
        deterministic_fuzzy_candidates=2,
        fuzzy_enabled=True,
        deterministic_findings=[],
        final_findings=[],
    )

    assert summary.fuzzy_enabled is True
    assert summary.deterministic_fuzzy_candidates == 2


def test_build_processing_summary_propagates_author_and_resource_link_fields() -> None:
    summary = build_processing_summary(
        mode="deterministic",
        deterministic_candidates_total=0,
        deterministic_strong_candidates=0,
        deterministic_weak_candidates=0,
        deterministic_fuzzy_candidates=0,
        fuzzy_enabled=False,
        deterministic_findings=[],
        final_findings=[],
        author_check=make_author_check("weak_match"),
        resource_link_matches=[make_resource_link_match()],
    )

    assert summary.resource_link_matches_total == 1
    assert summary.author_check_status == "weak_match"
    assert summary.author_requires_human_review is True
