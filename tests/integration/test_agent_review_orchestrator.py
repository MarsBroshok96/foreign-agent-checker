from datetime import UTC, datetime

from fa_checker.agent import orchestrator
from fa_checker.agent.action_selection import parse_agent_review_action
from fa_checker.agent.orchestrator import run_bounded_review_check
from fa_checker.agent.schemas import AgentReviewAction
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


def review_action(
    action_type: str,
    candidate_index: int | None = 0,
    context_window_size: str | None = None,
) -> AgentReviewAction:
    return AgentReviewAction(
        action_type=action_type,
        candidate_index=candidate_index,
        context_window_size=context_window_size,
        reason=f"Test action {action_type}.",
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


def patch_action_sequence(monkeypatch, actions: list[AgentReviewAction]) -> list[str]:
    calls: list[str] = []
    remaining = list(actions)

    def fake_choose_review_action_with_llm(*args, **kwargs):
        calls.append(",".join(kwargs["allowed_actions"]))
        if remaining:
            return remaining.pop(0)
        return review_action("finalize")

    monkeypatch.setattr(
        orchestrator,
        "choose_review_action_with_llm",
        fake_choose_review_action_with_llm,
    )
    return calls


def test_no_weak_candidates_returns_deterministic_report(monkeypatch) -> None:
    def fail_action_selection(*args, **kwargs):
        raise AssertionError("Action selector should not be called")

    monkeypatch.setattr(
        orchestrator,
        "choose_review_action_with_llm",
        fail_action_selection,
    )

    report = run_bounded_review_check(
        make_article("Илья Варламов прокомментировал ситуацию."),
        [make_entry("Варламов Илья Александрович")],
    )

    assert report.status == ReportStatus.CONFIRMED_MATCH_FOUND
    assert len(report.findings) == 1
    assert report.findings[0].status == FindingStatus.CONFIRMED


def test_llm_requests_small_context_then_disambiguates_different_entity(
    monkeypatch,
) -> None:
    patch_action_sequence(
        monkeypatch,
        [
            review_action("request_context", context_window_size="small"),
            review_action("disambiguate_candidate"),
        ],
    )
    context_counts = {}
    original_get_candidate_context = orchestrator.get_candidate_context

    def tracking_get_candidate_context(state, candidate_index, window_size="small"):
        updated_state = original_get_candidate_context(state, candidate_index, window_size)
        context_counts.update(updated_state.context_requests_made)
        return updated_state

    def fake_disambiguation(*args, **kwargs):
        return disambiguation_result(DisambiguationDecision.DIFFERENT_ENTITY)

    monkeypatch.setattr(orchestrator, "get_candidate_context", tracking_get_candidate_context)
    monkeypatch.setattr(orchestrator, "disambiguate_candidate", fake_disambiguation)

    report = run_bounded_review_check(
        make_article("Белый дом выступил с заявлением."),
        [make_entry("Белый Руслан Викторович")],
    )

    assert context_counts["0"] == 1
    assert report.status == ReportStatus.NO_MATCH
    assert report.processing_summary is not None
    assert report.processing_summary.mode == "agentic"
    assert report.processing_summary.agentic_reviewed_candidates == 1
    assert report.processing_summary.agentic_rejected_after_review == 1
    finding = report.findings[0]
    assert finding.status == FindingStatus.REJECTED
    assert finding.risk_level == RiskLevel.LOW
    assert finding.requires_human_review is False


def test_llm_requests_small_then_large_context_then_disambiguates(monkeypatch) -> None:
    patch_action_sequence(
        monkeypatch,
        [
            review_action("request_context", context_window_size="small"),
            review_action("request_context", context_window_size="large"),
            review_action("disambiguate_candidate"),
        ],
    )
    context_counts = {}
    original_get_candidate_context = orchestrator.get_candidate_context

    def tracking_get_candidate_context(state, candidate_index, window_size="small"):
        updated_state = original_get_candidate_context(state, candidate_index, window_size)
        context_counts.update(updated_state.context_requests_made)
        return updated_state

    def fake_disambiguation(*args, **kwargs):
        return disambiguation_result(DisambiguationDecision.DIFFERENT_ENTITY)

    monkeypatch.setattr(orchestrator, "get_candidate_context", tracking_get_candidate_context)
    monkeypatch.setattr(orchestrator, "disambiguate_candidate", fake_disambiguation)

    report = run_bounded_review_check(
        make_article("Белый дом выступил с заявлением после встречи."),
        [make_entry("Белый Руслан Викторович")],
    )

    assert context_counts["0"] == 2
    assert report.findings[0].status == FindingStatus.REJECTED


def test_llm_requests_human_review_keeps_uncertain_finding(monkeypatch) -> None:
    calls = patch_action_sequence(
        monkeypatch,
        [review_action("request_human_review", candidate_index=None)],
    )

    report = run_bounded_review_check(
        make_article("Белый дом выступил с заявлением."),
        [make_entry("Белый Руслан Викторович")],
    )

    assert len(calls) == 1
    assert report.status == ReportStatus.POTENTIAL_MATCH_FOUND
    assert report.findings[0].status == FindingStatus.UNCERTAIN
    assert report.findings[0].requires_human_review is True


def test_disambiguate_candidate_is_terminal_and_does_not_require_finalize(
    monkeypatch,
) -> None:
    calls = patch_action_sequence(
        monkeypatch,
        [
            review_action("request_context", context_window_size="small"),
            review_action("disambiguate_candidate"),
            review_action("finalize"),
        ],
    )

    def fake_disambiguation(*args, **kwargs):
        return disambiguation_result(DisambiguationDecision.DIFFERENT_ENTITY)

    monkeypatch.setattr(orchestrator, "disambiguate_candidate", fake_disambiguation)

    report = run_bounded_review_check(
        make_article("Белый дом выступил с заявлением."),
        [make_entry("Белый Руслан Викторович")],
    )

    assert len(calls) == 2
    assert report.findings[0].status == FindingStatus.REJECTED


def test_llm_requests_human_review_is_terminal_without_finalize(monkeypatch) -> None:
    calls = patch_action_sequence(
        monkeypatch,
        [
            review_action("request_human_review", candidate_index=None),
            review_action("finalize", candidate_index=None),
        ],
    )

    report = run_bounded_review_check(
        make_article("Белый дом выступил с заявлением."),
        [make_entry("Белый Руслан Викторович")],
    )

    assert len(calls) == 1
    assert report.findings[0].status == FindingStatus.UNCERTAIN


def test_third_context_request_repairs_to_disambiguation(monkeypatch) -> None:
    patch_action_sequence(
        monkeypatch,
        [
            review_action("request_context", context_window_size="small"),
            review_action("request_context", context_window_size="large"),
            review_action("request_context", context_window_size="large"),
        ],
    )
    context_counts = {}
    original_get_candidate_context = orchestrator.get_candidate_context

    def tracking_get_candidate_context(state, candidate_index, window_size="small"):
        updated_state = original_get_candidate_context(state, candidate_index, window_size)
        context_counts.update(updated_state.context_requests_made)
        return updated_state

    def fake_disambiguation(*args, **kwargs):
        return disambiguation_result(DisambiguationDecision.DIFFERENT_ENTITY)

    monkeypatch.setattr(orchestrator, "get_candidate_context", tracking_get_candidate_context)
    monkeypatch.setattr(orchestrator, "disambiguate_candidate", fake_disambiguation)

    report = run_bounded_review_check(
        make_article("Белый дом выступил с заявлением."),
        [make_entry("Белый Руслан Викторович")],
    )

    assert context_counts["0"] == 2
    assert report.findings[0].status == FindingStatus.REJECTED


def test_disambiguate_action_with_string_null_window_executes(monkeypatch) -> None:
    actions = [
        review_action("request_context", context_window_size="small"),
        parse_agent_review_action(
            """
            {
              "action_type": "disambiguate_candidate",
              "candidate_index": 0,
              "context_window_size": "null",
              "reason": "Context is enough."
            }
            """
        ),
    ]
    patch_action_sequence(monkeypatch, actions)

    def fake_disambiguation(*args, **kwargs):
        return disambiguation_result(DisambiguationDecision.DIFFERENT_ENTITY)

    monkeypatch.setattr(orchestrator, "disambiguate_candidate", fake_disambiguation)

    report = run_bounded_review_check(
        make_article("Белый дом выступил с заявлением."),
        [make_entry("Белый Руслан Викторович")],
    )

    assert report.findings[0].status == FindingStatus.REJECTED


def test_weak_candidate_likely_same_entity_becomes_probable(monkeypatch) -> None:
    patch_action_sequence(
        monkeypatch,
        [
            review_action("request_context", context_window_size="small"),
            review_action("disambiguate_candidate"),
        ],
    )

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
    patch_action_sequence(
        monkeypatch,
        [
            review_action("request_context", context_window_size="small"),
            review_action("disambiguate_candidate"),
        ],
    )

    def fake_disambiguation(*args, **kwargs):
        return disambiguation_result(DisambiguationDecision.SAME_ENTITY)

    monkeypatch.setattr(orchestrator, "disambiguate_candidate", fake_disambiguation)

    report = run_bounded_review_check(
        make_article("Белый выступил с заявлением."),
        [make_entry("Белый Руслан Викторович")],
    )

    assert report.status == ReportStatus.CONFIRMED_MATCH_FOUND
    assert report.findings[0].status == FindingStatus.CONFIRMED


def test_finalize_too_early_repairs_conservatively(monkeypatch) -> None:
    patch_action_sequence(
        monkeypatch,
        [review_action("finalize")],
    )

    report = run_bounded_review_check(
        make_article("Белый дом выступил с заявлением."),
        [make_entry("Белый Руслан Викторович")],
    )

    assert report.status == ReportStatus.POTENTIAL_MATCH_FOUND
    assert report.findings[0].status == FindingStatus.UNCERTAIN
    assert report.findings[0].requires_human_review is True


def test_max_steps_exceeded_falls_back_to_uncertain_human_review(monkeypatch) -> None:
    patch_action_sequence(
        monkeypatch,
        [review_action("request_context", context_window_size="small")],
    )

    report = run_bounded_review_check(
        make_article("Белый дом выступил с заявлением."),
        [make_entry("Белый Руслан Викторович")],
        max_steps_per_candidate=1,
    )

    assert report.status == ReportStatus.POTENTIAL_MATCH_FOUND
    assert report.findings[0].status == FindingStatus.UNCERTAIN
    assert "maximum step limit" in " ".join(report.limitations)


def test_strong_and_weak_candidates_preserve_confirmed_overall_status(monkeypatch) -> None:
    patch_action_sequence(
        monkeypatch,
        [
            review_action("request_context", candidate_index=1, context_window_size="small"),
            review_action("disambiguate_candidate", candidate_index=1),
        ],
    )

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
    patch_action_sequence(
        monkeypatch,
        [
            review_action("request_context", context_window_size="small"),
            review_action("disambiguate_candidate"),
        ],
    )

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


def test_strong_candidates_are_not_reviewed(monkeypatch) -> None:
    def fail_action_selection(*args, **kwargs):
        raise AssertionError("Action selector should not be called for strong candidates")

    monkeypatch.setattr(
        orchestrator,
        "choose_review_action_with_llm",
        fail_action_selection,
    )

    report = run_bounded_review_check(
        make_article("Илья Варламов прокомментировал ситуацию."),
        [make_entry("Варламов Илья Александрович")],
    )

    assert report.status == ReportStatus.CONFIRMED_MATCH_FOUND


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
    patch_action_sequence(
        monkeypatch,
        [review_action("request_human_review", candidate_index=None)],
    )

    report = run_bounded_review_check(
        make_article("Белый дом выступил с заявлением."),
        [make_entry("Белый Руслан Викторович")],
    )

    assert report.status == ReportStatus.POTENTIAL_MATCH_FOUND
    assert report.findings[0].status == FindingStatus.UNCERTAIN
    assert report.findings[0].requires_human_review is True
