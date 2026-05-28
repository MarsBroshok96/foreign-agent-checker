"""Deterministic exact matching over normalized article text."""

from fa_checker.article.normalizer import normalize_for_matching
from fa_checker.domain.enums import EvidenceSource, MatchType
from fa_checker.domain.models import Article, CandidateMatch, EvidenceFragment, RegistryEntry
from fa_checker.registry.alias_builder import build_aliases


def _find_alias_positions(text: str, alias: str) -> list[int]:
    positions: list[int] = []
    start = 0
    while True:
        position = text.find(alias, start)
        if position == -1:
            return positions
        if _has_text_boundaries(text, position, position + len(alias)):
            positions.append(position)
        start = position + 1


def _has_text_boundaries(text: str, start: int, end: int) -> bool:
    before_is_boundary = start == 0 or not text[start - 1].isalnum()
    after_is_boundary = end == len(text) or not text[end].isalnum()
    return before_is_boundary and after_is_boundary


def _overlaps_existing(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(
        start < existing_end and end > existing_start
        for existing_start, existing_end in spans
    )


def _sorted_aliases(aliases: list[str]) -> list[str]:
    return sorted(aliases, key=len, reverse=True)


def find_exact_matches(
    article: Article,
    registry_entries: list[RegistryEntry],
) -> list[CandidateMatch]:
    normalized_text = normalize_for_matching(article.text)
    matches: list[CandidateMatch] = []

    for entry in registry_entries:
        aliases = build_aliases(entry)
        strong_matches = _find_entry_matches(
            normalized_text=normalized_text,
            entry=entry,
            aliases=aliases.strong,
            match_type=MatchType.EXACT,
            match_score=1.0,
            requires_disambiguation=False,
        )
        if strong_matches:
            matches.extend(strong_matches)
            continue

        matches.extend(
            _find_entry_matches(
                normalized_text=normalized_text,
                entry=entry,
                aliases=aliases.weak,
                match_type=MatchType.ALIAS,
                match_score=0.55,
                requires_disambiguation=True,
            )
        )

    return matches


def _find_entry_matches(
    normalized_text: str,
    entry: RegistryEntry,
    aliases: list[str],
    match_type: MatchType,
    match_score: float,
    requires_disambiguation: bool,
) -> list[CandidateMatch]:
    matches: list[CandidateMatch] = []
    accepted_spans: list[tuple[int, int]] = []
    seen: set[tuple[str, int]] = set()

    for alias in _sorted_aliases(aliases):
        for start in _find_alias_positions(normalized_text, alias):
            if (alias, start) in seen:
                continue
            end = start + len(alias)
            if _overlaps_existing(start, end, accepted_spans):
                continue
            seen.add((alias, start))
            accepted_spans.append((start, end))
            matches.append(
                CandidateMatch(
                    mention_text=normalized_text[start:end],
                    mention_start=start,
                    mention_end=end,
                    registry_entry=entry,
                    match_type=match_type,
                    match_score=match_score,
                    evidence=[
                        EvidenceFragment(
                            source=EvidenceSource.ARTICLE_TEXT,
                            text=normalized_text[start:end],
                            start=start,
                            end=end,
                        )
                    ],
                    requires_disambiguation=requires_disambiguation,
                )
            )

    return matches
