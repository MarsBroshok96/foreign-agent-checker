from datetime import UTC, datetime

from fa_checker.agent import orchestrator
from fa_checker.agent.orchestrator import run_bounded_review_check
from fa_checker.domain.enums import (
    DisambiguationDecision,
    EntityType,
    FindingStatus,
    ReportStatus,
    RiskLevel,
)
from fa_checker.domain.models import (
    Article,
    CheckReport,
    DisambiguationResult,
    RegistryEntry,
)


def make_article(text: str) -> Article:
    return Article(
        url="https://www.rambler.ru/example",
        source_domain="www.rambler.ru",
        text=text,
    )


def make_entry(
    full_name: str,
    entity_type: EntityType = EntityType.PERSON,
    aliases: list[str] | None = None,
) -> RegistryEntry:
    return RegistryEntry(
        registry_id=full_name,
        full_name=full_name,
        entity_type=entity_type,
        normalized_name=full_name.lower(),
        aliases=aliases or [],
        registry_source_url="https://minjust.gov.ru/registry",
    )


def disambiguation_result(
    decision: DisambiguationDecision,
    requires_human_review: bool = False,
) -> DisambiguationResult:
    return DisambiguationResult(
        decision=decision,
        confidence_score=0.9,
        requires_human_review=requires_human_review,
        rationale="Test disambiguation result.",
    )


def test_no_weak_candidates_returns_deterministic_report(monkeypatch) -> None:
    def fail_disambiguation(*args, **kwargs):
        raise AssertionError("LLM disambiguation should not be called")

    monkeypatch.setattr(orchestrator, "disambiguate_candidate", fail_disambiguation)

    report = run_bounded_review_check(
        make_article("Илья Варламов прокомментировал ситуацию."),
        [make_entry("Варламов Илья Александрович")],
    )

    assert report.status == ReportStatus.CONFIRMED_MATCH_FOUND
    assert len(report.findings) == 1
    assert report.findings[0].status == FindingStatus.CONFIRMED


def test_weak_candidate_different_entity_becomes_rejected(monkeypatch) -> None:
    def fake_disambiguation(*args, **kwargs):
        return disambiguation_result(DisambiguationDecision.DIFFERENT_ENTITY)

    monkeypatch.setattr(orchestrator, "disambiguate_candidate", fake_disambiguation)

    report = run_bounded_review_check(
        make_article("Белый дом выступил с заявлением."),
        [make_entry("Белый Руслан Викторович")],
    )

    assert report.status == ReportStatus.NO_MATCH
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.status == FindingStatus.REJECTED
    assert finding.risk_level == RiskLevel.LOW
    assert finding.requires_human_review is False


def test_weak_candidate_likely_same_entity_becomes_probable(monkeypatch) -> None:
    def fake_disambiguation(*args, **kwargs):
        return disambiguation_result(
            DisambiguationDecision.LIKELY_SAME_ENTITY,
            requires_human_review=True,
        )

    monkeypatch.setattr(orchestrator, "disambiguate_candidate", fake_disambiguation)

    report = run_bounded_review_check(
        make_article("Издание После опубликовало материал."),
        [make_entry("Проект «После»", entity_type=EntityType.PROJECT, aliases=["После"])],
    )

    assert report.status == ReportStatus.POTENTIAL_MATCH_FOUND
    assert report.findings[0].status == FindingStatus.PROBABLE
    assert report.findings[0].requires_human_review is True


def test_weak_candidate_same_entity_becomes_confirmed(monkeypatch) -> None:
    def fake_disambiguation(*args, **kwargs):
        return disambiguation_result(DisambiguationDecision.SAME_ENTITY)

    monkeypatch.setattr(orchestrator, "disambiguate_candidate", fake_disambiguation)

    report = run_bounded_review_check(
        make_article("Белый выступил с заявлением."),
        [make_entry("Белый Руслан Викторович")],
    )

    assert report.status == ReportStatus.CONFIRMED_MATCH_FOUND
    assert report.findings[0].status == FindingStatus.CONFIRMED


def test_uncertain_triggers_second_larger_context_request(monkeypatch) -> None:
    calls = []
    context_counts = {}
    original_get_candidate_context = orchestrator.get_candidate_context

    def fake_disambiguation(*args, **kwargs):
        calls.append(kwargs["context_text"])
        if len(calls) == 1:
            return disambiguation_result(
                DisambiguationDecision.UNCERTAIN,
                requires_human_review=True,
            )
        return disambiguation_result(DisambiguationDecision.DIFFERENT_ENTITY)

    def tracking_get_candidate_context(state, candidate_index, window_size="small"):
        updated_state = original_get_candidate_context(
            state,
            candidate_index,
            window_size,
        )
        context_counts.update(updated_state.context_requests_made)
        return updated_state

    monkeypatch.setattr(orchestrator, "disambiguate_candidate", fake_disambiguation)
    monkeypatch.setattr(
        orchestrator,
        "get_candidate_context",
        tracking_get_candidate_context,
    )

    report = run_bounded_review_check(
        make_article("Белый дом выступил с заявлением после встречи."),
        [make_entry("Белый Руслан Викторович")],
    )

    assert len(calls) == 2
    assert context_counts["0"] == 2
    assert report.findings[0].status == FindingStatus.REJECTED


def test_uncertain_remains_uncertain_after_second_call(monkeypatch) -> None:
    def fake_disambiguation(*args, **kwargs):
        return disambiguation_result(
            DisambiguationDecision.UNCERTAIN,
            requires_human_review=True,
        )

    monkeypatch.setattr(orchestrator, "disambiguate_candidate", fake_disambiguation)

    report = run_bounded_review_check(
        make_article("Белый выступил с заявлением."),
        [make_entry("Белый Руслан Викторович")],
    )

    assert report.status == ReportStatus.POTENTIAL_MATCH_FOUND
    assert report.findings[0].status == FindingStatus.UNCERTAIN
    assert report.findings[0].requires_human_review is True


def test_strong_and_weak_candidates_preserve_confirmed_overall_status(monkeypatch) -> None:
    def fake_disambiguation(*args, **kwargs):
        return disambiguation_result(DisambiguationDecision.DIFFERENT_ENTITY)

    monkeypatch.setattr(orchestrator, "disambiguate_candidate", fake_disambiguation)

    report = run_bounded_review_check(
        make_article("Илья Варламов и Белый дом упоминаются в статье."),
        [
            make_entry("Варламов Илья Александрович"),
            make_entry("Белый Руслан Викторович"),
        ],
    )

    assert report.status == ReportStatus.CONFIRMED_MATCH_FOUND
    assert [finding.status for finding in report.findings] == [
        FindingStatus.CONFIRMED,
        FindingStatus.REJECTED,
    ]


def test_max_review_candidates_limit_leaves_unreviewed_weak_candidate_uncertain(
    monkeypatch,
) -> None:
    calls = []

    def fake_disambiguation(*args, **kwargs):
        calls.append(kwargs["candidate_index"])
        return disambiguation_result(DisambiguationDecision.DIFFERENT_ENTITY)

    monkeypatch.setattr(orchestrator, "disambiguate_candidate", fake_disambiguation)

    report = run_bounded_review_check(
        make_article("Белый и Черный упоминаются рядом."),
        [
            make_entry("Белый Руслан Викторович"),
            make_entry("Черный Иван Иванович"),
        ],
        max_review_candidates=1,
    )

    assert calls == [0]
    assert "not reviewed" in " ".join(report.limitations)
    assert [finding.status for finding in report.findings] == [
        FindingStatus.REJECTED,
        FindingStatus.UNCERTAIN,
    ]
    assert report.findings[1].requires_human_review is True


def test_run_agentic_review_check_delegates_to_orchestrator(monkeypatch) -> None:
    from fa_checker import pipeline

    expected_report = CheckReport(
        article_url="https://www.rambler.ru/example",
        checked_at=datetime.now(UTC),
        status=ReportStatus.NO_MATCH,
    )

    def fake_run_bounded_review_check(*args, **kwargs):
        return expected_report

    monkeypatch.setattr(
        orchestrator,
        "run_bounded_review_check",
        fake_run_bounded_review_check,
    )

    report = pipeline.run_agentic_review_check(
        make_article("Текст без совпадений."),
        [],
    )

    assert report is expected_report


def test_llm_fallback_uncertain_path_stays_conservative(monkeypatch) -> None:
    def fake_disambiguation(*args, **kwargs):
        return DisambiguationResult(
            decision=DisambiguationDecision.UNCERTAIN,
            confidence_score=0.0,
            requires_human_review=True,
            rationale="LLM disambiguation failed; human review required.",
        )

    monkeypatch.setattr(orchestrator, "disambiguate_candidate", fake_disambiguation)

    report = run_bounded_review_check(
        make_article("Белый дом выступил с заявлением."),
        [make_entry("Белый Руслан Викторович")],
    )

    assert report.status == ReportStatus.POTENTIAL_MATCH_FOUND
    assert report.findings[0].status == FindingStatus.UNCERTAIN
    assert report.findings[0].requires_human_review is True
