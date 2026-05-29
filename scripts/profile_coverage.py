"""Compare registry entries with local context profile coverage."""

from __future__ import annotations

import argparse
from pathlib import Path

from fa_checker.agent.context_profiles import (
    ContextProfile,
    find_context_profile,
    load_context_profiles,
)
from fa_checker.domain.models import RegistryEntry
from fa_checker.registry.parser import parse_registry_xlsx


def missing_profile_entries(
    registry_entries: list[RegistryEntry],
    profiles: list[ContextProfile],
) -> list[RegistryEntry]:
    missing: list[RegistryEntry] = []
    for entry in registry_entries:
        profile = find_context_profile(
            profiles,
            registry_id=entry.registry_id,
            entity_name=entry.full_name,
        )
        if profile is None:
            missing.append(entry)
    return missing


def coverage_summary(
    registry_xlsx_path: str | Path,
    profiles_path: str | Path,
    limit: int = 20,
    registry_source_url: str = "local_registry_snapshot",
) -> dict[str, object]:
    registry_entries = parse_registry_xlsx(
        registry_xlsx_path,
        registry_source_url=registry_source_url,
    )
    profiles = load_context_profiles(profiles_path)
    missing = missing_profile_entries(registry_entries, profiles)
    return {
        "registry_entries_count": len(registry_entries),
        "profiles_count": len(profiles),
        "matched_profiles_count": len(registry_entries) - len(missing),
        "missing_profiles_count": len(missing),
        "missing_entries": missing[:limit],
    }


def print_coverage_summary(summary: dict[str, object]) -> None:
    print(f"registry entries count: {summary['registry_entries_count']}")
    print(f"profiles count: {summary['profiles_count']}")
    print(f"matched profiles count: {summary['matched_profiles_count']}")
    print(f"missing profiles count: {summary['missing_profiles_count']}")
    print("missing entries:")
    for entry in summary["missing_entries"]:
        registry_id = entry.registry_id or "no registry_id"
        print(f"- {registry_id}: {entry.full_name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Report context profile coverage.")
    parser.add_argument("registry_xlsx_path", help="Path to local registry XLSX.")
    parser.add_argument("profiles_path", help="Path to context profile JSON.")
    parser.add_argument("--limit", type=int, default=20, help="Missing entries to print.")
    args = parser.parse_args()

    summary = coverage_summary(
        args.registry_xlsx_path,
        args.profiles_path,
        limit=args.limit,
    )
    print_coverage_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
