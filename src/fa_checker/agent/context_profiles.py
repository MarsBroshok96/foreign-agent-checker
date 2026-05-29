"""Local auxiliary context profiles for future disambiguation."""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from fa_checker.article.normalizer import normalize_for_matching


class ContextProfile(BaseModel):
    registry_id: str | None = None
    entity_name: str
    entity_type: str | None = None
    descriptors: list[str] = Field(default_factory=list)
    known_projects: list[str] = Field(default_factory=list)
    known_domains: list[str] = Field(default_factory=list)
    common_mentions: list[str] = Field(default_factory=list)
    notes: str | None = None
    sources: list[str] = Field(default_factory=list)


def load_context_profiles(path: str | Path) -> list[ContextProfile]:
    """Load local context profiles from JSON, returning [] for a missing file."""
    profile_path = Path(path)
    if not profile_path.exists():
        return []

    try:
        data = json.loads(profile_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"Invalid context profile JSON in {profile_path}: {exc}"
        raise ValueError(msg) from exc

    profiles_data = _profiles_payload(data, profile_path)
    try:
        return [ContextProfile.model_validate(item) for item in profiles_data]
    except ValidationError as exc:
        msg = f"Invalid context profile structure in {profile_path}: {exc}"
        raise ValueError(msg) from exc


def find_context_profile(
    profiles: list[ContextProfile],
    registry_id: str | None = None,
    entity_name: str | None = None,
) -> ContextProfile | None:
    """Find a profile by registry id first, then by normalized entity name."""
    if registry_id:
        for profile in profiles:
            if profile.registry_id == registry_id:
                return profile

    if entity_name:
        normalized_name = normalize_for_matching(entity_name)
        for profile in profiles:
            if normalize_for_matching(profile.entity_name) == normalized_name:
                return profile

    return None


def _profiles_payload(data: Any, path: Path) -> list[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("profiles"), list):
        return data["profiles"]
    msg = f"Context profile JSON in {path} must be a list or contain a 'profiles' list."
    raise ValueError(msg)
