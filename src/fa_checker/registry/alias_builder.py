"""Deterministic alias generation for registry entries."""

import re

from pydantic import BaseModel, Field

from fa_checker.article.normalizer import normalize_for_matching
from fa_checker.domain.enums import EntityType
from fa_checker.domain.models import RegistryEntry


class AliasSet(BaseModel):
    strong: list[str] = Field(default_factory=list)
    weak: list[str] = Field(default_factory=list)


LEGAL_PREFIXES = {"ооо", "ао", "пао", "нко", "фонд"}
ANGLE_QUOTED_RE = re.compile(r"«[^»]+»")
DOUBLE_QUOTED_RE = re.compile(r'"[^"]+"')


def _add_unique_raw(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def _add_unique_normalized(items: list[str], value: str) -> None:
    _add_unique_raw(items, normalize_for_matching(value))


def _token_count(alias: str) -> int:
    return len(alias.split())


def _is_single_token(alias: str) -> bool:
    return _token_count(alias) == 1


def _add_alias(strong: list[str], weak: list[str], value: str) -> None:
    normalized = normalize_for_matching(value).replace('"', "")
    normalized = normalize_for_matching(normalized)
    if not normalized:
        return
    if _is_single_token(normalized):
        _add_unique_raw(weak, normalized)
    else:
        _add_unique_raw(strong, normalized)


def _remove_quoted_fragments(text: str) -> str:
    without_angle_quotes = ANGLE_QUOTED_RE.sub(" ", text)
    return DOUBLE_QUOTED_RE.sub(" ", without_angle_quotes)


def _normalize_name_keep_quoted_text(text: str) -> str:
    return normalize_for_matching(text).replace('"', "")


def _simplify_legal_name(normalized_name: str) -> str:
    tokens = normalized_name.split()
    if len(tokens) < 2 or tokens[0] not in LEGAL_PREFIXES:
        return ""
    return " ".join(tokens[1:])


def _build_person_aliases(entry: RegistryEntry) -> AliasSet:
    strong: list[str] = []
    weak: list[str] = []

    full_name = normalize_for_matching(_remove_quoted_fragments(entry.full_name))
    _add_unique_raw(strong, full_name)

    tokens = full_name.split()
    surname = tokens[0] if tokens else ""

    for alias in entry.aliases:
        _add_alias(strong, weak, alias)

    if len(tokens) >= 2:
        _add_unique_raw(strong, f"{tokens[0]} {tokens[1]}")
        _add_unique_raw(strong, f"{tokens[1]} {tokens[0]}")
    if len(tokens) >= 3:
        _add_unique_raw(strong, f"{tokens[0]} {tokens[1]} {tokens[2]}")
    if len(surname) >= 4 and surname not in strong:
        _add_unique_raw(weak, surname)
    if len(tokens) >= 2:
        _add_person_initial_aliases(weak, tokens)

    return AliasSet(strong=strong, weak=weak)


def _add_person_initial_aliases(weak: list[str], tokens: list[str]) -> None:
    surname = tokens[0]
    name_initial = tokens[1][0]

    _add_unique_normalized(weak, f"{surname} {name_initial}.")
    _add_unique_normalized(weak, f"{name_initial}. {surname}")

    if len(tokens) >= 3:
        patronymic_initial = tokens[2][0]
        _add_unique_normalized(weak, f"{surname} {name_initial}.{patronymic_initial}.")
        _add_unique_normalized(weak, f"{surname} {name_initial}. {patronymic_initial}.")
        _add_unique_normalized(weak, f"{name_initial}.{patronymic_initial}. {surname}")
        _add_unique_normalized(weak, f"{name_initial}. {patronymic_initial}. {surname}")


def _build_non_person_aliases(entry: RegistryEntry) -> AliasSet:
    strong: list[str] = []
    weak: list[str] = []

    full_name = _normalize_name_keep_quoted_text(entry.full_name)
    if _is_single_token(full_name):
        _add_unique_raw(weak, full_name)
    else:
        _add_unique_raw(strong, full_name)

    for alias in entry.aliases:
        _add_alias(strong, weak, alias)

    simplified = _simplify_legal_name(full_name)
    if simplified:
        if _is_single_token(simplified):
            _add_unique_raw(weak, simplified)
        else:
            _add_unique_raw(strong, simplified)

    return AliasSet(strong=strong, weak=weak)


def build_aliases(entry: RegistryEntry) -> AliasSet:
    """Build ordered strong and weak aliases for deterministic matching."""
    if entry.entity_type == EntityType.PERSON:
        return _build_person_aliases(entry)
    return _build_non_person_aliases(entry)
