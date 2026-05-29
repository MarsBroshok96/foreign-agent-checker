import pytest

from fa_checker.agent.context_profiles import ContextProfile
from fa_checker.agent.state import build_agent_review_state
from fa_checker.agent.tools import get_candidate_context, lookup_candidate_context_profile
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
    registry_id: str | None = None,
    entity_type: EntityType = EntityType.PERSON,
    aliases: list[str] | None = None,
) -> RegistryEntry:
    return RegistryEntry(
        registry_id=registry_id,
        full_name=full_name,
        entity_type=entity_type,
        normalized_name=full_name.lower(),
        aliases=aliases or [],
        registry_source_url="https://minjust.gov.ru/registry",
    )


def weak_review_state(registry_id: str | None = None):
    analysis = run_deterministic_analysis(
        make_article("Белый дом выступил с заявлением после встречи."),
        [make_entry("Белый Руслан Викторович", registry_id=registry_id)],
    )
    return build_agent_review_state(analysis)


def test_get_candidate_context_small_returns_context_and_counts_request() -> None:
    state = weak_review_state()

    updated = get_candidate_context(state, candidate_index=0, window_size="small")

    assert updated is state
    assert state.context_requests_made["0"] == 1
    assert "Белый дом" in state.review_candidates[0].evidence_texts[0]
    assert "Context requested for candidate 0 with small window." in state.history


def test_get_candidate_context_allows_two_requests_for_same_candidate() -> None:
    state = weak_review_state()

    get_candidate_context(state, candidate_index=0, window_size="small")
    get_candidate_context(state, candidate_index=0, window_size="large")

    assert state.context_requests_made["0"] == 2


def test_get_candidate_context_third_request_raises_value_error() -> None:
    state = weak_review_state()
    get_candidate_context(state, candidate_index=0)
    get_candidate_context(state, candidate_index=0)

    with pytest.raises(ValueError, match="Context request limit exceeded"):
        get_candidate_context(state, candidate_index=0)


def test_get_candidate_context_invalid_candidate_index_raises_value_error() -> None:
    state = weak_review_state()

    with pytest.raises(ValueError, match="Review candidate 99 was not found"):
        get_candidate_context(state, candidate_index=99)


def test_get_candidate_context_falls_back_to_existing_evidence_for_invalid_indexes() -> None:
    state = weak_review_state()
    state.deterministic_result.candidates[0].mention_start = 999
    state.deterministic_result.candidates[0].mention_end = 1000

    get_candidate_context(state, candidate_index=0)

    assert state.context_requests_made["0"] == 1
    assert "Белый дом" in state.review_candidates[0].evidence_texts[0]
    assert "Context window fallback used for candidate 0." in state.history


def test_lookup_candidate_context_profile_finds_by_registry_id() -> None:
    state = weak_review_state(registry_id="42")
    profiles = [
        ContextProfile(registry_id="42", entity_name="Другое имя"),
    ]

    profile = lookup_candidate_context_profile(state, candidate_index=0, profiles=profiles)

    assert profile is not None
    assert profile.registry_id == "42"
    assert "Context profile found for candidate 0." in state.history


def test_lookup_candidate_context_profile_finds_by_entity_name_fallback() -> None:
    state = weak_review_state(registry_id="42")
    profiles = [
        ContextProfile(entity_name="Белый Руслан Викторович"),
    ]

    profile = lookup_candidate_context_profile(state, candidate_index=0, profiles=profiles)

    assert profile is not None
    assert profile.entity_name == "Белый Руслан Викторович"


def test_lookup_candidate_context_profile_returns_none_if_missing() -> None:
    state = weak_review_state(registry_id="42")

    profile = lookup_candidate_context_profile(state, candidate_index=0, profiles=[])

    assert profile is None
    assert "Context profile not found for candidate 0." in state.history
