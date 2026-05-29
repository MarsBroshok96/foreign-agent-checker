"""Prompt constants for future structured LLM calls."""

from fa_checker.agent.context_profiles import ContextProfile
from fa_checker.agent.state import AgentReviewState, ReviewCandidate
from fa_checker.domain.models import RegistryEntry

SYSTEM_PROMPT = (
    "You are a bounded compliance-assistance agent. Use only provided structured state, "
    "respect the official registry as the sole source of truth, and return structured actions."
)


def build_disambiguation_prompt(
    candidate: ReviewCandidate,
    registry_entry: RegistryEntry,
    context_text: str,
    context_profile: ContextProfile | None = None,
) -> str:
    """Build a concise JSON-only prompt for candidate disambiguation."""
    profile_section = _context_profile_section(context_profile)
    return f"""Decide whether the article mention refers to the registry candidate.

Rules:
- Use only the data below. Do not browse the internet.
- The official registry entry is the only source of truth for registry status.
- Local context profile data is auxiliary only and may help disambiguation.
- Do not issue legal conclusions or legal verdicts.
- Base the decision only on the provided article context, registry entry,
  and optional local context profile.
- Do not speculate about unseen article text.
- Do not choose uncertain only because the same word could theoretically refer
  to the candidate elsewhere.
- Use uncertain only when the provided context itself is insufficient or genuinely ambiguous.
- Choose different_entity when the provided context clearly refers to a
  different person, organization, institution, place, common phrase,
  color/adjective/common-word usage, or unrelated grammatical use.
- Return JSON only, with no Markdown or extra text.

Decision meanings:
- same_entity: context clearly refers to the registry entity.
- likely_same_entity: context probably refers to the registry entity, but there is ambiguity.
- uncertain: not enough context to decide.
- different_entity: context clearly refers to something else.

Calibration examples:
- Candidate: Белый Руслан Викторович
  Mention context: Белый дом выступил с заявлением после встречи.
  Expected decision: different_entity
  Reason: Белый дом is an institution/place expression, not the person.
- Candidate: Проект «После»
  Mention context: После дождя случилось событие.
  Expected decision: different_entity
  Reason: после is used as a common word, not as a project name.
- Candidate: Проект «После»
  Mention context: Издание После опубликовало новый материал.
  Expected decision: likely_same_entity
  Reason: context indicates a media/project mention.
- Candidate: Варламов Илья Александрович
  Mention context: Урбанист Варламов прокомментировал благоустройство.
  Expected decision: likely_same_entity
  Reason: surname-only mention is supported by a descriptor consistent with the profile.

Required JSON shape:
{{
  "decision": "same_entity | likely_same_entity | uncertain | different_entity",
  "confidence_score": 0.0,
  "requires_human_review": true,
  "rationale": "short explanation grounded in article context"
}}

Candidate mention:
- index: {candidate.candidate_index}
- mention_text: {candidate.mention_text}
- match_type: {candidate.match_type}
- match_score: {candidate.match_score}

Registry candidate:
- registry_id: {registry_entry.registry_id}
- full_name: {registry_entry.full_name}
- entity_type: {registry_entry.entity_type.value}
- aliases: {", ".join(registry_entry.aliases) if registry_entry.aliases else "none"}

Article context:
{context_text}

{profile_section}
"""


def build_review_action_prompt(
    state: AgentReviewState,
    candidate: ReviewCandidate,
    available_context_texts: list[str],
    context_profile: ContextProfile | None,
    allowed_actions: list[str],
) -> str:
    """Build a concise JSON-only prompt for bounded review action selection."""
    profile_section = _context_profile_section(context_profile)
    context_section = _context_texts_section(available_context_texts)
    return f"""Choose the next bounded review action for one weak candidate.

Rules:
- The deterministic baseline has already run.
- You are reviewing only this weak candidate.
- Choose exactly one action from the allowed actions.
- Never choose request_context if request_context is not in allowed actions.
- After two context requests, choose disambiguate_candidate if context is enough
  or request_human_review if it is unsafe to decide.
- The official registry entry is the only source of truth for registry status.
- Local context profile data is auxiliary only and may help disambiguation.
- Do not browse the internet.
- Do not issue legal conclusions or legal verdicts.
- Return JSON only, with no Markdown or extra text.

Allowed actions:
{", ".join(allowed_actions)}

Decision guidance:
- request_context: choose this if more article context is needed before disambiguation.
- disambiguate_candidate: choose this if the provided context is enough to decide.
- request_human_review: choose this if the case is too ambiguous or unsafe for model decision.
- finalize: choose this only after disambiguation is completed or human review is requested.
- context_window_size must be JSON null for non-request_context actions.

Required JSON shape:
{{
  "action_type": "request_context | disambiguate_candidate | request_human_review | finalize",
  "candidate_index": {candidate.candidate_index},
  "context_window_size": "small | medium | large | null",
  "reason": "short reason"
}}

Review progress:
- weak_candidates_reviewed: {state.weak_candidates_reviewed}
- disambiguation_completed: {state.disambiguation_completed}

Candidate:
- index: {candidate.candidate_index}
- entity_name: {candidate.entity_name}
- mention_text: {candidate.mention_text}
- match_type: {candidate.match_type}
- match_score: {candidate.match_score}

Available article context:
{context_section}

{profile_section}
"""


def _context_profile_section(context_profile: ContextProfile | None) -> str:
    if context_profile is None:
        return "Local context profile: none provided."
    return "\n".join(
        [
            "Local context profile (auxiliary only):",
            f"- entity_name: {context_profile.entity_name}",
            f"- entity_type: {context_profile.entity_type}",
            f"- role_or_category: {context_profile.role_or_category or 'none'}",
            f"- short_description: {context_profile.short_description or 'none'}",
            f"- descriptors: {_join_or_none(context_profile.descriptors)}",
            f"- known_projects: {_join_or_none(context_profile.known_projects)}",
            f"- known_domains: {_join_or_none(context_profile.known_domains)}",
            f"- common_mentions: {_join_or_none(context_profile.common_mentions)}",
            f"- disambiguation_hints: {_join_or_none(context_profile.disambiguation_hints)}",
            f"- negative_context_hints: {_join_or_none(context_profile.negative_context_hints)}",
            f"- primary_language: {context_profile.primary_language or 'none'}",
            f"- confidence: {context_profile.confidence or 'none'}",
            f"- notes: {context_profile.notes or 'none'}",
            f"- sources: {_join_or_none(context_profile.sources)}",
        ]
    )


def _join_or_none(values: list[str]) -> str:
    return ", ".join(values) if values else "none"


def _context_texts_section(context_texts: list[str]) -> str:
    if not context_texts:
        return "none provided."
    return "\n".join(f"- {text}" for text in context_texts)
