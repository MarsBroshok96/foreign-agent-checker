from fa_checker.agent.context_profiles import ContextProfile
from fa_checker.agent.prompts import build_review_action_prompt
from fa_checker.agent.state import build_agent_review_state
from fa_checker.domain.enums import EntityType
from fa_checker.domain.models import Article, RegistryEntry
from fa_checker.pipeline import run_deterministic_analysis


def make_review_state():
    analysis = run_deterministic_analysis(
        Article(
            url="https://www.rambler.ru/example",
            source_domain="www.rambler.ru",
            text="Белый дом выступил с заявлением.",
        ),
        [
            RegistryEntry(
                full_name="Белый Руслан Викторович",
                entity_type=EntityType.PERSON,
                normalized_name="белый руслан викторович",
                registry_source_url="https://minjust.gov.ru/registry",
            )
        ],
    )
    return build_agent_review_state(analysis)


def test_review_action_prompt_contains_allowed_actions() -> None:
    state = make_review_state()
    candidate = state.review_candidates[0]

    prompt = build_review_action_prompt(
        state,
        candidate,
        available_context_texts=[],
        context_profile=None,
        allowed_actions=["request_context", "request_human_review"],
    )

    assert "request_context, request_human_review" in prompt


def test_review_action_prompt_contains_candidate_entity_and_mention() -> None:
    state = make_review_state()
    candidate = state.review_candidates[0]

    prompt = build_review_action_prompt(
        state,
        candidate,
        available_context_texts=["Белый дом выступил с заявлением."],
        context_profile=None,
        allowed_actions=["disambiguate_candidate"],
    )

    assert "Белый Руслан Викторович" in prompt
    assert "mention_text: белый" in prompt


def test_review_action_prompt_contains_context_profile_data() -> None:
    state = make_review_state()
    candidate = state.review_candidates[0]
    profile = ContextProfile(
        entity_name="Белый Руслан Викторович",
        descriptors=["актер"],
    )

    prompt = build_review_action_prompt(
        state,
        candidate,
        available_context_texts=[],
        context_profile=profile,
        allowed_actions=["request_context"],
    )

    assert "актер" in prompt


def test_review_action_prompt_states_boundaries_and_json_only() -> None:
    state = make_review_state()
    candidate = state.review_candidates[0]

    prompt = build_review_action_prompt(
        state,
        candidate,
        available_context_texts=[],
        context_profile=None,
        allowed_actions=["request_context"],
    )

    assert "official registry entry is the only source of truth" in prompt
    assert "context profile data is auxiliary only" in prompt
    assert "Do not browse the internet" in prompt
    assert "Return JSON only" in prompt
