"""Ollama client placeholder."""

from fa_checker.domain.models import AgentAction


class OllamaClient:
    """Placeholder client for future structured local LLM calls."""

    def choose_action(self, prompt: str) -> AgentAction:
        raise NotImplementedError("Ollama calls are not implemented in the scaffold phase.")

