"""Validate local context profile JSON files."""

from __future__ import annotations

import argparse
from pathlib import Path

from fa_checker.agent.context_profiles import ContextProfile, load_context_profiles
from fa_checker.article.normalizer import normalize_for_matching
from fa_checker.domain.models import RegistryEntry
from fa_checker.registry.parser import parse_registry_xlsx


def duplicate_registry_ids(profiles: list[ContextProfile]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for profile in profiles:
        if profile.registry_id is None:
            continue
        if profile.registry_id in seen and profile.registry_id not in duplicates:
            duplicates.append(profile.registry_id)
        seen.add(profile.registry_id)
    return duplicates


def duplicate_entity_names(profiles: list[ContextProfile]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for profile in profiles:
        normalized_name = normalize_for_matching(profile.entity_name)
        if normalized_name in seen and normalized_name not in duplicates:
            duplicates.append(normalized_name)
        seen.add(normalized_name)
    return duplicates


def unknown_registry_ids(
    profiles: list[ContextProfile],
    registry_entries: list[RegistryEntry],
) -> list[str]:
    registry_ids = {
        entry.registry_id for entry in registry_entries if entry.registry_id is not None
    }
    return [
        profile.registry_id
        for profile in profiles
        if profile.registry_id is not None and profile.registry_id not in registry_ids
    ]


def registry_name_mismatches(
    profiles: list[ContextProfile],
    registry_entries: list[RegistryEntry],
) -> list[dict[str, str]]:
    entries_by_registry_id = {
        entry.registry_id: entry
        for entry in registry_entries
        if entry.registry_id is not None
    }
    mismatches: list[dict[str, str]] = []
    for profile in profiles:
        if profile.registry_id is None:
            continue
        registry_entry = entries_by_registry_id.get(profile.registry_id)
        if registry_entry is None:
            continue
        if profile.entity_name != registry_entry.full_name:
            mismatches.append(
                {
                    "registry_id": profile.registry_id,
                    "profile_entity_name": profile.entity_name,
                    "registry_entity_name": registry_entry.full_name,
                }
            )
    return mismatches


def validation_summary(
    profiles: list[ContextProfile],
    registry_entries: list[RegistryEntry] | None = None,
) -> dict[str, object]:
    registry_duplicates = duplicate_registry_ids(profiles)
    name_duplicates = duplicate_entity_names(profiles)
    unknown_ids: list[str] = []
    name_mismatches: list[dict[str, str]] = []
    if registry_entries is not None:
        unknown_ids = unknown_registry_ids(profiles, registry_entries)
        name_mismatches = registry_name_mismatches(profiles, registry_entries)
    with_registry_id = sum(profile.registry_id is not None for profile in profiles)
    return {
        "profiles_count": len(profiles),
        "with_registry_id_count": with_registry_id,
        "without_registry_id_count": len(profiles) - with_registry_id,
        "duplicate_registry_ids": registry_duplicates,
        "duplicate_entity_names": name_duplicates,
        "unknown_registry_ids": unknown_ids,
        "registry_name_mismatches": name_mismatches,
        "valid": not (
            registry_duplicates
            or name_duplicates
            or unknown_ids
            or name_mismatches
        ),
    }


def validate_context_profiles(
    path: str | Path,
    registry_xlsx_path: str | Path | None = None,
) -> dict[str, object]:
    profiles = load_context_profiles(path)
    registry_entries = None
    if registry_xlsx_path is not None:
        registry_entries = parse_registry_xlsx(
            registry_xlsx_path,
            registry_source_url="local_registry_snapshot",
        )
    return validation_summary(profiles, registry_entries)


def print_summary(summary: dict[str, object]) -> None:
    print(f"profiles count: {summary['profiles_count']}")
    print(f"with registry_id count: {summary['with_registry_id_count']}")
    print(f"without registry_id count: {summary['without_registry_id_count']}")
    if summary["duplicate_registry_ids"]:
        print(f"duplicate registry_id values: {summary['duplicate_registry_ids']}")
    if summary["duplicate_entity_names"]:
        print(f"duplicate normalized entity_name values: {summary['duplicate_entity_names']}")
    if summary["unknown_registry_ids"]:
        print(f"registry_id values missing from registry: {summary['unknown_registry_ids']}")
    if summary["registry_name_mismatches"]:
        print("registry_id/entity_name mismatches:")
        for mismatch in summary["registry_name_mismatches"]:
            print(
                "- "
                f"{mismatch['registry_id']}: "
                f"profile={mismatch['profile_entity_name']!r}, "
                f"registry={mismatch['registry_entity_name']!r}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate context profile JSON.")
    parser.add_argument("path", help="Path to context profile JSON.")
    parser.add_argument(
        "--registry-xlsx",
        help="Optional registry XLSX path for registry_id/entity_name validation.",
    )
    args = parser.parse_args()

    try:
        summary = validate_context_profiles(args.path, args.registry_xlsx)
    except ValueError as exc:
        print(f"validation failed: {exc}")
        return 1

    print_summary(summary)
    return 0 if summary["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
