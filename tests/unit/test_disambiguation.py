from fa_checker.adapters.ollama_client import OllamaClientError
from fa_checker.agent import disambiguation
from fa_checker.agent.disambiguation import (
    disambiguate_candidate,
    parse_disambiguation_result,
)
from fa_checker.agent.state import build_agent_review_state
from fa_checker.domain.enums import DisambiguationDecision, EntityType
from fa_checker.domain.models import Article, RegistryEntry
from fa_checker.pipeline import run_deterministic_analysis


def weak_review_state():
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


def test_parse_disambiguation_result_accepts_valid_clean_json() -> None:
    result = parse_disambiguation_result(
        """
        {
          "decision": "same_entity",
          "confidence_score": 0.8,
          "requires_human_review": false,
          "rationale": "Article context names the person."
        }
        """
    )

    assert result.decision == DisambiguationDecision.SAME_ENTITY
    assert result.confidence_score == 0.8
    assert result.requires_human_review is False


def test_parse_disambiguation_result_accepts_markdown_code_fence() -> None:
    result = parse_disambiguation_result(
        """```json
        {
          "decision": "different_entity",
          "confidence_score": 0.9,
          "requires_human_review": false,
          "rationale": "Context refers to the White House."
        }
        ```"""
    )

    assert result.decision == DisambiguationDecision.DIFFERENT_ENTITY
    assert result.confidence_score == 0.9


def test_parse_disambiguation_result_invalid_json_returns_uncertain_fallback() -> None:
    result = parse_disambiguation_result("{bad json")

    assert result.decision == DisambiguationDecision.UNCERTAIN
    assert result.confidence_score == 0.0
    assert result.requires_human_review is True
    assert result.rationale == "LLM output could not be parsed safely."


def test_parse_disambiguation_result_invalid_decision_returns_fallback() -> None:
    result = parse_disambiguation_result(
        """
        {
          "decision": "invalid",
          "confidence_score": 0.8,
          "requires_human_review": false,
          "rationale": "Bad decision."
        }
        """
    )

    assert result.decision == DisambiguationDecision.UNCERTAIN


def test_parse_disambiguation_result_invalid_confidence_returns_fallback() -> None:
    result = parse_disambiguation_result(
        """
        {
          "decision": "same_entity",
          "confidence_score": 1.2,
          "requires_human_review": false,
          "rationale": "Too high."
        }
        """
    )

    assert result.decision == DisambiguationDecision.UNCERTAIN


def test_parse_disambiguation_result_missing_rationale_returns_fallback() -> None:
    result = parse_disambiguation_result(
        """
        {
          "decision": "same_entity",
          "confidence_score": 0.8,
          "requires_human_review": false
        }
        """
    )

    assert result.decision == DisambiguationDecision.UNCERTAIN


def test_disambiguate_candidate_returns_parsed_ollama_result(monkeypatch) -> None:
    def fake_generate_ollama_response(
        prompt,
        model,
        base_url,
        format_json=False,
        temperature=None,
    ):
        return """
        {
          "decision": "different_entity",
          "confidence_score": 0.9,
          "requires_human_review": false,
          "rationale": "Context refers to the White House, not the person."
        }
        """

    monkeypatch.setattr(
        disambiguation,
        "generate_ollama_response",
        fake_generate_ollama_response,
    )
    state = weak_review_state()

    result = disambiguate_candidate(
        state,
        candidate_index=0,
        context_text="Белый дом выступил с заявлением.",
        model="test-model",
        base_url="http://ollama.test",
    )

    assert result.decision == DisambiguationDecision.DIFFERENT_ENTITY
    assert result.confidence_score == 0.9
    assert result.requires_human_review is False


def test_disambiguate_candidate_requests_json_and_zero_temperature(monkeypatch) -> None:
    captured_options = {}

    def fake_generate_ollama_response(
        prompt,
        model,
        base_url,
        format_json=False,
        temperature=None,
    ):
        captured_options["format_json"] = format_json
        captured_options["temperature"] = temperature
        return """
        {
          "decision": "different_entity",
          "confidence_score": 0.9,
          "requires_human_review": false,
          "rationale": "Context refers to the White House, not the person."
        }
        """

    monkeypatch.setattr(
        disambiguation,
        "generate_ollama_response",
        fake_generate_ollama_response,
    )
    state = weak_review_state()

    disambiguate_candidate(
        state,
        candidate_index=0,
        context_text="Белый дом выступил с заявлением.",
        model="test-model",
        base_url="http://ollama.test",
    )

    assert captured_options == {"format_json": True, "temperature": 0.0}


def test_disambiguate_candidate_returns_fallback_on_ollama_error(monkeypatch) -> None:
    def fake_generate_ollama_response(
        prompt,
        model,
        base_url,
        format_json=False,
        temperature=None,
    ):
        raise OllamaClientError("offline")

    monkeypatch.setattr(
        disambiguation,
        "generate_ollama_response",
        fake_generate_ollama_response,
    )
    state = weak_review_state()

    result = disambiguate_candidate(
        state,
        candidate_index=0,
        context_text="Белый дом выступил с заявлением.",
        model="test-model",
        base_url="http://ollama.test",
    )

    assert result.decision == DisambiguationDecision.UNCERTAIN
    assert result.confidence_score == 0.0
    assert result.requires_human_review is True
    assert result.rationale == "LLM disambiguation failed; human review required."


def test_disambiguate_candidate_invalid_candidate_index_raises_value_error() -> None:
    state = weak_review_state()

    try:
        disambiguate_candidate(
            state,
            candidate_index=99,
            context_text="Белый дом выступил с заявлением.",
            model="test-model",
            base_url="http://ollama.test",
        )
    except ValueError as exc:
        assert "Review candidate 99 was not found" in str(exc)
    else:
        raise AssertionError("ValueError was not raised")
