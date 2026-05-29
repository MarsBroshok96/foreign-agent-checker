"""Prompt constants for future structured LLM calls."""

from fa_checker.agent.context_profiles import ContextProfile
from fa_checker.agent.state import ReviewCandidate
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
- Return JSON only, with no Markdown or extra text.

Decision meanings:
- same_entity: context clearly refers to the registry entity.
- likely_same_entity: context probably refers to the registry entity, but there is ambiguity.
- uncertain: not enough context to decide.
- different_entity: context clearly refers to something else.

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


def _context_profile_section(context_profile: ContextProfile | None) -> str:
    if context_profile is None:
        return "Local context profile: none provided."
    return "\n".join(
        [
            "Local context profile (auxiliary only):",
            f"- entity_name: {context_profile.entity_name}",
            f"- entity_type: {context_profile.entity_type}",
            f"- descriptors: {_join_or_none(context_profile.descriptors)}",
            f"- known_projects: {_join_or_none(context_profile.known_projects)}",
            f"- known_domains: {_join_or_none(context_profile.known_domains)}",
            f"- common_mentions: {_join_or_none(context_profile.common_mentions)}",
            f"- notes: {context_profile.notes or 'none'}",
        ]
    )


def _join_or_none(values: list[str]) -> str:
    return ", ".join(values) if values else "none"
