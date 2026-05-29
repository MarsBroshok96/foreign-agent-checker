"""Merge human-reviewed context profile batches."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from fa_checker.agent.context_profiles import ContextProfile, load_context_profiles
from fa_checker.article.normalizer import normalize_for_matching


def merge_profiles(
    existing_profiles: list[ContextProfile],
    new_profiles: list[ContextProfile],
) -> list[ContextProfile]:
    merged_by_key = {_profile_key(profile): profile for profile in existing_profiles}
    for new_profile in new_profiles:
        key = _profile_key(new_profile)
        old_profile = merged_by_key.get(key)
        if old_profile is None:
            merged_by_key[key] = new_profile
        else:
            merged_by_key[key] = _merge_profile(old_profile, new_profile)
    return sorted(merged_by_key.values(), key=_sort_key)


def merge_context_profile_files(
    existing_path: str | Path,
    new_path: str | Path,
    output_path: str | Path,
) -> list[ContextProfile]:
    existing_profiles = load_context_profiles(existing_path)
    new_profiles = load_context_profiles(new_path)
    merged_profiles = merge_profiles(existing_profiles, new_profiles)
    write_profiles(output_path, merged_profiles)
    return merged_profiles


def write_profiles(path: str | Path, profiles: list[ContextProfile]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "profiles": [
            profile.model_dump(mode="json", exclude_none=True)
            for profile in profiles
        ]
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _merge_profile(old_profile: ContextProfile, new_profile: ContextProfile) -> ContextProfile:
    merged_data = old_profile.model_dump(mode="json")
    for field_name, new_value in new_profile.model_dump(mode="json").items():
        if _has_value(new_value):
            merged_data[field_name] = new_value
    return ContextProfile.model_validate(merged_data)


def _has_value(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def _profile_key(profile: ContextProfile) -> str:
    if profile.registry_id:
        return f"registry:{profile.registry_id}"
    return f"name:{normalize_for_matching(profile.entity_name)}"


def _sort_key(profile: ContextProfile) -> tuple[int, int, str, str]:
    registry_id = profile.registry_id or ""
    if registry_id.isdigit():
        return (0, int(registry_id), "", profile.entity_name)
    if registry_id:
        return (1, 0, registry_id, profile.entity_name)
    return (2, 0, "", profile.entity_name)


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge context profile JSON files.")
    parser.add_argument("existing_profiles_json", help="Existing context profiles JSON.")
    parser.add_argument("new_profiles_json", help="New batch context profiles JSON.")
    parser.add_argument("output_path", help="Output path for merged profiles JSON.")
    args = parser.parse_args()

    merged = merge_context_profile_files(
        args.existing_profiles_json,
        args.new_profiles_json,
        args.output_path,
    )
    print(f"merged profiles count: {len(merged)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
