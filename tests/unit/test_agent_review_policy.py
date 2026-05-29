from fa_checker.agent.policy import (
    agent_review_required,
    allowed_actions_for_candidate,
    allowed_review_actions,
    can_finalize_review,
    normalize_or_repair_action,
)
from fa_checker.agent.schemas import AgentReviewAction
from fa_checker.agent.state import build_agent_review_state
from fa_checker.domain.enums import EntityType
from fa_checker.domain.models import Article, RegistryEntry
from fa_checker.pipeline import run_deterministic_analysis


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
        full_name=full_name,
        entity_type=entity_type,
        normalized_name=full_name.lower(),
        aliases=aliases or [],
        registry_source_url="https://minjust.gov.ru/registry",
    )


def strong_analysis():
    return run_deterministic_analysis(
        make_article("Илья Варламов прокомментировал ситуацию."),
        [make_entry("Варламов Илья Александрович")],
    )


def weak_analysis():
    return run_deterministic_analysis(
        make_article("После дождя случилось событие."),
        [make_entry("Проект «После»", entity_type=EntityType.PROJECT, aliases=["После"])],
    )


def test_agent_review_required_false_for_no_weak_candidates() -> None:
    assert agent_review_required(strong_analysis()) is False


def test_agent_review_required_true_for_weak_candidates() -> None:
    assert agent_review_required(weak_analysis()) is True


def test_allowed_review_actions_for_unreviewed_weak_candidates() -> None:
    state = build_agent_review_state(weak_analysis())

    actions = allowed_review_actions(state)

    assert "request_context" in actions
    assert "request_human_review" in actions
    assert "finalize" not in actions


def test_can_finalize_review_false_for_unreviewed_weak_candidates() -> None:
    state = build_agent_review_state(weak_analysis())

    assert can_finalize_review(state) is False


def test_can_finalize_review_true_when_no_review_candidates_exist() -> None:
    state = build_agent_review_state(strong_analysis())

    assert can_finalize_review(state) is True
    assert allowed_review_actions(state) == ["finalize"]


def test_can_finalize_review_true_when_weak_candidates_reviewed() -> None:
    state = build_agent_review_state(weak_analysis())
    state.weak_candidates_reviewed = True

    assert can_finalize_review(state) is True
    assert "finalize" in allowed_review_actions(state)


def test_allowed_actions_for_candidate_without_context() -> None:
    state = build_agent_review_state(weak_analysis())

    actions = allowed_actions_for_candidate(
        state,
        candidate_index=0,
        has_context=False,
        disambiguation_done=False,
        human_review_requested=False,
    )

    assert "request_context" in actions
    assert "request_human_review" in actions
    assert "disambiguate_candidate" not in actions


def test_allowed_actions_for_candidate_with_context() -> None:
    state = build_agent_review_state(weak_analysis())
    state.context_requests_made["0"] = 1

    actions = allowed_actions_for_candidate(
        state,
        candidate_index=0,
        has_context=True,
        disambiguation_done=False,
        human_review_requested=False,
    )

    assert "request_context" in actions
    assert "disambiguate_candidate" in actions


def test_allowed_actions_after_disambiguation_only_finalize() -> None:
    state = build_agent_review_state(weak_analysis())

    actions = allowed_actions_for_candidate(
        state,
        candidate_index=0,
        has_context=True,
        disambiguation_done=True,
        human_review_requested=False,
    )

    assert actions == ["finalize"]


def test_allowed_actions_after_human_review_request_only_finalize() -> None:
    state = build_agent_review_state(weak_analysis())

    actions = allowed_actions_for_candidate(
        state,
        candidate_index=0,
        has_context=True,
        disambiguation_done=False,
        human_review_requested=True,
    )

    assert actions == ["finalize"]


def test_allowed_actions_context_request_limit_prevents_more_context() -> None:
    state = build_agent_review_state(weak_analysis())
    state.context_requests_made["0"] = 2

    actions = allowed_actions_for_candidate(
        state,
        candidate_index=0,
        has_context=True,
        disambiguation_done=False,
        human_review_requested=False,
    )

    assert "request_context" not in actions
    assert "disambiguate_candidate" in actions


def make_action(
    action_type: str,
    context_window_size: str | None = None,
) -> AgentReviewAction:
    return AgentReviewAction(
        action_type=action_type,
        candidate_index=0,
        context_window_size=context_window_size,
        reason="Test action.",
    )


def test_repair_request_context_after_limit_with_context_to_disambiguation() -> None:
    action = normalize_or_repair_action(
        make_action("request_context", "small"),
        allowed_actions=["disambiguate_candidate", "request_human_review"],
        has_context=True,
        context_request_count=2,
        max_context_requests=2,
    )

    assert action.action_type == "disambiguate_candidate"
    assert "limit" in action.reason


def test_repair_human_review_with_context_to_disambiguation() -> None:
    action = normalize_or_repair_action(
        make_action("request_human_review"),
        allowed_actions=["disambiguate_candidate", "request_human_review"],
        has_context=True,
        context_request_count=2,
        max_context_requests=2,
    )

    assert action.action_type == "disambiguate_candidate"
    assert "before disambiguation" in action.reason


def test_repair_request_context_after_limit_without_context_to_human_review() -> None:
    action = normalize_or_repair_action(
        make_action("request_context", "small"),
        allowed_actions=["request_human_review"],
        has_context=False,
        context_request_count=2,
        max_context_requests=2,
    )

    assert action.action_type == "request_human_review"


def test_repair_disambiguate_without_context_to_request_context() -> None:
    action = normalize_or_repair_action(
        make_action("disambiguate_candidate"),
        allowed_actions=["request_context", "request_human_review"],
        has_context=False,
        context_request_count=0,
        max_context_requests=2,
    )

    assert action.action_type == "request_context"
    assert action.context_window_size == "small"


def test_repair_missing_request_context_window_defaults_small() -> None:
    action = normalize_or_repair_action(
        make_action("request_context"),
        allowed_actions=["request_context", "request_human_review"],
        has_context=False,
        context_request_count=0,
        max_context_requests=2,
    )

    assert action.context_window_size == "small"


def test_repair_missing_request_context_window_defaults_large_after_one_request() -> None:
    action = normalize_or_repair_action(
        make_action("request_context"),
        allowed_actions=[
            "request_context",
            "disambiguate_candidate",
            "request_human_review",
        ],
        has_context=True,
        context_request_count=1,
        max_context_requests=2,
    )

    assert action.context_window_size == "large"
