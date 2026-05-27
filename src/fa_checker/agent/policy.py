"""Policy checks for bounded agent actions."""

from fa_checker.agent.state import AgentState
from fa_checker.domain.enums import AgentActionType
from fa_checker.domain.models import AgentAction

ALLOWED_TOOL_NAMES = {
    "get_context_window",
    "alias_search",
    "alias_search_batch",
    "fuzzy_registry_search",
    "entity_extractor",
    "disambiguate_entity",
    "label_checker",
    "author_checker",
    "link_domain_checker",
    "risk_scorer",
    "report_generator",
}


def is_action_allowed(action: AgentAction, state: AgentState, max_steps: int) -> bool:
    if state.tool_call_count >= max_steps:
        return False
    if action.action_type == AgentActionType.CALL_TOOL:
        return action.tool_name in ALLOWED_TOOL_NAMES
    if action.action_type == AgentActionType.FINALIZE:
        return state.ready_to_report
    return action.action_type == AgentActionType.REQUEST_HUMAN_REVIEW

