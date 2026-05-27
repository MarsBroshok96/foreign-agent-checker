from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

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
from fa_checker.domain.models import (
    AgentAction,
    Article,
    CandidateMatch,
    CheckReport,
    ContextProfile,
    DisambiguationResult,
    EvidenceFragment,
    FinalFinding,
    LabelCheckResult,
    RegistryEntry,
)
from fa_checker.pipeline import run_check


def test_domain_models_can_be_instantiated() -> None:
    article = Article(
        url="https://www.rambler.ru/example",
        source_domain="www.rambler.ru",
        title="Example",
        author="Reporter",
        published_at=datetime(2026, 5, 27, tzinfo=UTC),
        text="Article text mentioning an entity.",
        links=["https://example.org"],
    )
    registry_entry = RegistryEntry(
        registry_id="123",
        full_name="Example Entity",
        entity_type=EntityType.ORGANIZATION,
        normalized_name="example entity",
        aliases=["Example"],
        registry_source_url="https://minjust.gov.ru/registry",
        registry_snapshot_date=date(2026, 5, 27),
        raw_fields={"source": "fixture"},
    )
    context_profile = ContextProfile(
        registry_id="123",
        entity_name="Example Entity",
        entity_type="organization",
        known_descriptors=["publisher"],
        known_projects=["Example Project"],
        known_domains=["example.org"],
        notes="Auxiliary context only.",
        sources=["https://context.example"],
        retrieved_at=datetime(2026, 5, 27, tzinfo=UTC),
    )
    evidence = EvidenceFragment(
        source=EvidenceSource.ARTICLE_TEXT,
        text="Example Entity",
        start=0,
        end=14,
    )
    candidate = CandidateMatch(
        mention_text="Example Entity",
        mention_start=0,
        mention_end=14,
        registry_entry=registry_entry,
        match_type=MatchType.EXACT,
        match_score=1.0,
        evidence=[evidence],
        requires_disambiguation=False,
    )
    disambiguation = DisambiguationResult(
        decision=DisambiguationDecision.SAME_ENTITY,
        confidence_score=0.9,
        rationale="Structured evidence matches.",
        requires_human_review=False,
    )
    label_check = LabelCheckResult(
        label_found=False,
        label_fragment=None,
        label_distance=None,
        label_quality=LabelQuality.ABSENT,
    )
    finding = FinalFinding(
        entity_name="Example Entity",
        mention_text="Example Entity",
        status=FindingStatus.CONFIRMED,
        risk_level=RiskLevel.LOW,
        confidence_level=ConfidenceLevel.HIGH,
        label_status=LabelStatus.NOT_CHECKED,
        requires_human_review=False,
        evidence=[evidence],
        rationale="Scaffold finding.",
    )
    report = CheckReport(
        article_url=article.url,
        article_title=article.title,
        article_author=article.author,
        checked_at=datetime(2026, 5, 27, tzinfo=UTC),
        registry_snapshot_date=date(2026, 5, 27),
        status=ReportStatus.CONFIRMED_MATCH_FOUND,
        findings=[finding],
        limitations=[],
    )
    action = AgentAction(
        action_type=AgentActionType.CALL_TOOL,
        tool_name="label_checker",
        arguments={"mention": "Example Entity"},
        reason="Check required label evidence.",
    )

    assert context_profile.entity_name == "Example Entity"
    assert candidate.registry_entry == registry_entry
    assert disambiguation.requires_human_review is False
    assert label_check.label_quality == LabelQuality.ABSENT
    assert report.findings == [finding]
    assert action.tool_name == "label_checker"


def test_models_reject_invalid_scores() -> None:
    registry_entry = RegistryEntry(
        full_name="Example Entity",
        entity_type="organization",
        normalized_name="example entity",
        registry_source_url="https://minjust.gov.ru/registry",
    )

    with pytest.raises(ValidationError):
        CandidateMatch(
            mention_text="Example Entity",
            registry_entry=registry_entry,
            match_type="fuzzy",
            match_score=1.5,
            evidence=[],
            requires_disambiguation=True,
        )


def test_run_check_returns_placeholder_report() -> None:
    report = run_check("https://www.rambler.ru/example")

    assert isinstance(report, CheckReport)
    assert report.article_url == "https://www.rambler.ru/example"
    assert report.status == ReportStatus.NO_MATCH
    assert report.findings == []
    assert report.limitations == [
        "Business logic is not implemented yet; this is a scaffold report."
    ]

