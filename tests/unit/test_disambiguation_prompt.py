from fa_checker.agent.context_profiles import ContextProfile
from fa_checker.agent.prompts import build_disambiguation_prompt
from fa_checker.agent.state import ReviewCandidate
from fa_checker.domain.enums import EntityType
from fa_checker.domain.models import RegistryEntry


def make_candidate() -> ReviewCandidate:
    return ReviewCandidate(
        candidate_index=0,
        entity_name="Белый Руслан Викторович",
        mention_text="белый",
        match_type="alias",
        match_score=0.55,
        requires_disambiguation=True,
        evidence_texts=["Белый дом выступил с заявлением."],
    )


def make_registry_entry() -> RegistryEntry:
    return RegistryEntry(
        registry_id="42",
        full_name="Белый Руслан Викторович",
        entity_type=EntityType.PERSON,
        normalized_name="белый руслан викторович",
        aliases=["Белый"],
        registry_source_url="https://minjust.gov.ru/registry",
    )


def test_disambiguation_prompt_contains_candidate_entity_name() -> None:
    prompt = build_disambiguation_prompt(
        make_candidate(),
        make_registry_entry(),
        "Белый дом выступил с заявлением.",
    )

    assert "Белый Руслан Викторович" in prompt


def test_disambiguation_prompt_contains_mention_text() -> None:
    prompt = build_disambiguation_prompt(
        make_candidate(),
        make_registry_entry(),
        "Белый дом выступил с заявлением.",
    )

    assert "mention_text: белый" in prompt


def test_disambiguation_prompt_contains_article_context() -> None:
    prompt = build_disambiguation_prompt(
        make_candidate(),
        make_registry_entry(),
        "Белый дом выступил с заявлением.",
    )

    assert "Белый дом выступил с заявлением." in prompt


def test_disambiguation_prompt_contains_profile_descriptors() -> None:
    profile = ContextProfile(
        entity_name="Белый Руслан Викторович",
        descriptors=["актер", "комик"],
    )

    prompt = build_disambiguation_prompt(
        make_candidate(),
        make_registry_entry(),
        "Белый дом выступил с заявлением.",
        context_profile=profile,
    )

    assert "актер, комик" in prompt


def test_disambiguation_prompt_requires_json_only_output() -> None:
    prompt = build_disambiguation_prompt(
        make_candidate(),
        make_registry_entry(),
        "Белый дом выступил с заявлением.",
    )

    assert "Return JSON only" in prompt
    assert '"decision"' in prompt


def test_disambiguation_prompt_states_boundaries() -> None:
    prompt = build_disambiguation_prompt(
        make_candidate(),
        make_registry_entry(),
        "Белый дом выступил с заявлением.",
    )

    assert "official registry entry is the only source of truth" in prompt
    assert "context profile data is auxiliary only" in prompt
    assert "Do not browse the internet" in prompt
    assert "Do not issue legal conclusions or legal verdicts" in prompt


def test_disambiguation_prompt_says_not_to_speculate_about_unseen_context() -> None:
    prompt = build_disambiguation_prompt(
        make_candidate(),
        make_registry_entry(),
        "Белый дом выступил с заявлением.",
    )

    assert "Do not speculate about unseen article text" in prompt


def test_disambiguation_prompt_calibrates_uncertain_decision() -> None:
    prompt = build_disambiguation_prompt(
        make_candidate(),
        make_registry_entry(),
        "Белый дом выступил с заявлением.",
    )

    assert "Use uncertain only when the provided context itself is insufficient" in prompt
    assert "genuinely ambiguous" in prompt


def test_disambiguation_prompt_contains_bely_dom_different_entity_example() -> None:
    prompt = build_disambiguation_prompt(
        make_candidate(),
        make_registry_entry(),
        "Белый дом выступил с заявлением.",
    )

    assert "Белый дом выступил с заявлением после встречи." in prompt
    assert "Expected decision: different_entity" in prompt


def test_disambiguation_prompt_contains_posle_rain_different_entity_example() -> None:
    prompt = build_disambiguation_prompt(
        make_candidate(),
        make_registry_entry(),
        "Белый дом выступил с заявлением.",
    )

    assert "После дождя случилось событие." in prompt
    assert "после is used as a common word" in prompt


def test_disambiguation_prompt_contains_posle_media_likely_same_example() -> None:
    prompt = build_disambiguation_prompt(
        make_candidate(),
        make_registry_entry(),
        "Белый дом выступил с заявлением.",
    )

    assert "Издание После опубликовало новый материал." in prompt
    assert "Expected decision: likely_same_entity" in prompt
