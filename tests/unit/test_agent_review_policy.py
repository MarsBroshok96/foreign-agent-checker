from fa_checker.agent.policy import (
    agent_review_required,
    allowed_review_actions,
    can_finalize_review,
)
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
    assert "disambiguate_candidate" in actions
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
