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


def test_weak_candidates_become_review_candidates() -> None:
    analysis = run_deterministic_analysis(
        make_article("После дождя случилось событие."),
        [make_entry("Проект «После»", entity_type=EntityType.PROJECT, aliases=["После"])],
    )

    state = build_agent_review_state(analysis)

    assert len(state.review_candidates) == 1
    review_candidate = state.review_candidates[0]
    assert review_candidate.candidate_index == 0
    assert review_candidate.entity_name == "Проект «После»"
    assert review_candidate.mention_text == "после"
    assert review_candidate.match_type == "alias"
    assert review_candidate.requires_disambiguation is True
    assert review_candidate.finding_status == "uncertain"
    assert review_candidate.risk_level == "medium"
    assert review_candidate.evidence_texts
    assert "После дождя" in review_candidate.evidence_texts[0]
    assert state.history == ["Built agent review state from deterministic analysis."]


def test_strong_only_analysis_creates_no_review_candidates() -> None:
    analysis = run_deterministic_analysis(
        make_article("Илья Варламов прокомментировал ситуацию."),
        [make_entry("Варламов Илья Александрович")],
    )

    state = build_agent_review_state(analysis)

    assert state.review_candidates == []

