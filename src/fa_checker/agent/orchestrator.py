"""Bounded agent orchestrator placeholder."""

from fa_checker.agent.state import AgentState


class AgentOrchestrator:
    """Placeholder for the policy-validated tool-calling loop."""

    def run(self, state: AgentState) -> AgentState:
        raise NotImplementedError("Agent orchestration is not implemented in the scaffold phase.")

