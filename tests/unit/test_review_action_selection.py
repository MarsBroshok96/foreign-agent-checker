from fa_checker.adapters.ollama_client import OllamaClientError
from fa_checker.agent import action_selection
from fa_checker.agent.action_selection import (
    choose_review_action_with_llm,
    parse_agent_review_action,
)
from fa_checker.agent.state import build_agent_review_state
from fa_checker.domain.enums import EntityType
from fa_checker.domain.models import Article, RegistryEntry
from fa_checker.pipeline import run_deterministic_analysis


def make_state():
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


def test_parse_agent_review_action_valid_request_context_json() -> None:
    action = parse_agent_review_action(
        """
        {
          "action_type": "request_context",
          "candidate_index": 0,
          "context_window_size": "small",
          "reason": "Need nearby words."
        }
        """
    )

    assert action.action_type == "request_context"
    assert action.context_window_size == "small"


def test_parse_agent_review_action_valid_disambiguate_json() -> None:
    action = parse_agent_review_action(
        """
        {
          "action_type": "disambiguate_candidate",
          "candidate_index": 0,
          "context_window_size": null,
          "reason": "Context is enough."
        }
        """
    )

    assert action.action_type == "disambiguate_candidate"


def test_parse_agent_review_action_accepts_markdown_code_fence() -> None:
    action = parse_agent_review_action(
        """```json
        {
          "action_type": "finalize",
          "candidate_index": 0,
          "context_window_size": null,
          "reason": "Done."
        }
        ```"""
    )

    assert action.action_type == "finalize"


def test_parse_agent_review_action_invalid_json_returns_fallback() -> None:
    action = parse_agent_review_action("{bad json")

    assert action.action_type == "request_human_review"
    assert action.reason == "LLM action output could not be parsed safely."


def test_parse_agent_review_action_invalid_action_returns_fallback() -> None:
    action = parse_agent_review_action(
        """
        {
          "action_type": "browse_web",
          "candidate_index": 0,
          "context_window_size": null,
          "reason": "Bad."
        }
        """
    )

    assert action.action_type == "request_human_review"


def test_parse_agent_review_action_string_null_window_becomes_none() -> None:
    action = parse_agent_review_action(
        """
        {
          "action_type": "request_context",
          "candidate_index": 0,
          "context_window_size": "null",
          "reason": "Need context."
        }
        """
    )

    assert action.action_type == "request_context"
    assert action.context_window_size is None


def test_parse_agent_review_action_string_none_window_becomes_none() -> None:
    action = parse_agent_review_action(
        """
        {
          "action_type": "request_context",
          "candidate_index": 0,
          "context_window_size": "None",
          "reason": "Need context."
        }
        """
    )

    assert action.context_window_size is None


def test_parse_agent_review_action_disambiguate_with_string_null_does_not_fallback() -> None:
    action = parse_agent_review_action(
        """
        {
          "action_type": "disambiguate_candidate",
          "candidate_index": 0,
          "context_window_size": "null",
          "reason": "Context is enough."
        }
        """
    )

    assert action.action_type == "disambiguate_candidate"
    assert action.context_window_size is None


def test_parse_agent_review_action_coerces_string_candidate_index() -> None:
    action = parse_agent_review_action(
        """
        {
          "action_type": "request_context",
          "candidate_index": "0",
          "context_window_size": "small",
          "reason": "Need context."
        }
        """
    )

    assert action.candidate_index == 0


def test_parse_agent_review_action_invalid_context_window_returns_fallback() -> None:
    action = parse_agent_review_action(
        """
        {
          "action_type": "request_context",
          "candidate_index": 0,
          "context_window_size": "huge",
          "reason": "Bad window."
        }
        """
    )

    assert action.action_type == "request_human_review"


def test_choose_review_action_with_llm_requests_json_and_zero_temperature(monkeypatch) -> None:
    captured = {}

    def fake_generate_ollama_response(
        prompt,
        model,
        base_url,
        format_json=False,
        temperature=None,
    ):
        captured["format_json"] = format_json
        captured["temperature"] = temperature
        return """
        {
          "action_type": "request_context",
          "candidate_index": 0,
          "context_window_size": "small",
          "reason": "Need context."
        }
        """

    monkeypatch.setattr(
        action_selection,
        "generate_ollama_response",
        fake_generate_ollama_response,
    )
    state = make_state()

    action = choose_review_action_with_llm(
        state,
        state.review_candidates[0],
        available_context_texts=[],
        context_profile=None,
        allowed_actions=["request_context"],
        model="test-model",
        base_url="http://ollama.test",
    )

    assert action.action_type == "request_context"
    assert captured == {"format_json": True, "temperature": 0.0}


def test_choose_review_action_with_llm_ollama_error_returns_fallback(monkeypatch) -> None:
    def fake_generate_ollama_response(*args, **kwargs):
        raise OllamaClientError("offline")

    monkeypatch.setattr(
        action_selection,
        "generate_ollama_response",
        fake_generate_ollama_response,
    )
    state = make_state()

    action = choose_review_action_with_llm(
        state,
        state.review_candidates[0],
        available_context_texts=[],
        context_profile=None,
        allowed_actions=["request_context"],
        model="test-model",
        base_url="http://ollama.test",
    )

    assert action.action_type == "request_human_review"
    assert action.reason == "LLM action selection failed; human review required."
