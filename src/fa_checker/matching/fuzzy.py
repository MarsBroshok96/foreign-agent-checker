"""Conservative person-only fuzzy recall matching."""

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from fa_checker.article.context import get_context_window
from fa_checker.article.normalizer import normalize_for_matching
from fa_checker.domain.enums import EntityType, EvidenceSource, MatchType
from fa_checker.domain.models import Article, CandidateMatch, EvidenceFragment, RegistryEntry
from fa_checker.registry.alias_builder import build_aliases


@dataclass(frozen=True)
class _Token:
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class _FuzzyRecord:
    registry_index: int
    start: int
    end: int
    score: float
    candidate: CandidateMatch


def find_fuzzy_person_matches(
    article: Article,
    registry_entries: list[RegistryEntry],
    existing_matches: list[CandidateMatch] | None = None,
    min_single_token_score: float = 0.86,
    min_multi_token_score: float = 0.84,
) -> list[CandidateMatch]:
    """Find weak fuzzy person candidates without touching non-person entries."""
    normalized_text = normalize_for_matching(article.text)
    tokens = _tokenize(normalized_text)
    if not tokens:
        return []

    existing_spans = _existing_spans_by_entry(existing_matches or [])
    records: list[_FuzzyRecord] = []
    accepted_spans: dict[tuple[str | None, str], list[tuple[int, int]]] = {}
    best_by_span: dict[tuple[tuple[str | None, str], int, int], _FuzzyRecord] = {}

    for registry_index, entry in enumerate(registry_entries):
        if entry.entity_type != EntityType.PERSON:
            continue
        entry_key = _entry_key(entry)
        aliases = _candidate_aliases(entry)
        for alias in aliases:
            for start, end, mention_text, score in _match_alias(
                alias=alias,
                tokens=tokens,
                normalized_text=normalized_text,
                min_single_token_score=min_single_token_score,
                min_multi_token_score=min_multi_token_score,
            ):
                if _overlaps_existing(start, end, existing_spans.get(entry_key, [])):
                    continue
                if _overlaps_existing(start, end, accepted_spans.get(entry_key, [])):
                    continue
                record = _make_record(
                    article_text=article.text,
                    normalized_text=normalized_text,
                    entry=entry,
                    registry_index=registry_index,
                    start=start,
                    end=end,
                    mention_text=mention_text,
                    score=score,
                )
                key = (entry_key, start, end)
                current = best_by_span.get(key)
                if current is None or record.score > current.score:
                    best_by_span[key] = record

        entry_records = [
            record
            for (key, _, _), record in best_by_span.items()
            if key == entry_key
        ]
        for record in sorted(entry_records, key=lambda item: (item.start, -item.score)):
            if _overlaps_existing(
                record.start,
                record.end,
                accepted_spans.get(entry_key, []),
            ):
                continue
            accepted_spans.setdefault(entry_key, []).append((record.start, record.end))
            records.append(record)

    return [
        record.candidate
        for record in sorted(records, key=lambda item: (item.start, item.registry_index))
    ]


def _candidate_aliases(entry: RegistryEntry) -> list[str]:
    aliases = build_aliases(entry)
    values: list[str] = []
    for alias in [*aliases.strong, *aliases.weak]:
        normalized = normalize_for_matching(alias)
        if normalized and normalized not in values and len(normalized) >= 6:
            values.append(normalized)
    return sorted(values, key=len, reverse=True)


def _match_alias(
    alias: str,
    tokens: list[_Token],
    normalized_text: str,
    min_single_token_score: float,
    min_multi_token_score: float,
) -> list[tuple[int, int, str, float]]:
    alias_tokens = alias.split()
    if len(alias_tokens) == 1:
        if len(alias_tokens[0]) < 6:
            return []
        return _match_single_token_alias(
            alias,
            tokens,
            min_single_token_score,
        )
    return _match_multi_token_alias(
        alias,
        tokens,
        normalized_text,
        min_multi_token_score,
    )


def _match_single_token_alias(
    alias: str,
    tokens: list[_Token],
    min_score: float,
) -> list[tuple[int, int, str, float]]:
    matches: list[tuple[int, int, str, float]] = []
    for token in tokens:
        if len(token.text) < 6:
            continue
        score = fuzz.ratio(alias, token.text) / 100
        if score >= min_score:
            matches.append((token.start, token.end, token.text, score))
    return matches


def _match_multi_token_alias(
    alias: str,
    tokens: list[_Token],
    normalized_text: str,
    min_score: float,
) -> list[tuple[int, int, str, float]]:
    matches: list[tuple[int, int, str, float]] = []
    token_count = len(alias.split())
    for size in {token_count, token_count + 1}:
        if size > len(tokens):
            continue
        for index in range(0, len(tokens) - size + 1):
            start = tokens[index].start
            end = tokens[index + size - 1].end
            mention_text = normalized_text[start:end]
            score = fuzz.token_sort_ratio(alias, mention_text) / 100
            if score >= min_score:
                matches.append((start, end, mention_text, score))
    return matches


def _make_record(
    article_text: str,
    normalized_text: str,
    entry: RegistryEntry,
    registry_index: int,
    start: int,
    end: int,
    mention_text: str,
    score: float,
) -> _FuzzyRecord:
    return _FuzzyRecord(
        registry_index=registry_index,
        start=start,
        end=end,
        score=score,
        candidate=CandidateMatch(
            mention_text=mention_text,
            mention_start=start,
            mention_end=end,
            registry_entry=entry,
            match_type=MatchType.FUZZY,
            match_score=round(score, 4),
            evidence=[
                _make_context_evidence(
                    article_text=article_text,
                    normalized_text=normalized_text,
                    start=start,
                    end=end,
                )
            ],
            requires_disambiguation=True,
        ),
    )


def _make_context_evidence(
    article_text: str,
    normalized_text: str,
    start: int,
    end: int,
    window_size: int = 160,
) -> EvidenceFragment:
    try:
        return get_context_window(article_text, start, end, window_size)
    except ValueError:
        pass
    try:
        return get_context_window(normalized_text, start, end, window_size)
    except ValueError:
        return EvidenceFragment(
            source=EvidenceSource.ARTICLE_TEXT,
            text=normalized_text[start:end],
            start=start,
            end=end,
        )


def _tokenize(normalized_text: str) -> list[_Token]:
    return [
        _Token(match.group(0), match.start(), match.end())
        for match in re.finditer(r"[a-zа-я0-9]+", normalized_text)
    ]


def _entry_key(entry: RegistryEntry) -> tuple[str | None, str]:
    return (entry.registry_id, entry.full_name)


def _existing_spans_by_entry(
    existing_matches: list[CandidateMatch],
) -> dict[tuple[str | None, str], list[tuple[int, int]]]:
    spans: dict[tuple[str | None, str], list[tuple[int, int]]] = {}
    for match in existing_matches:
        if match.mention_start is None or match.mention_end is None:
            continue
        spans.setdefault(_entry_key(match.registry_entry), []).append(
            (match.mention_start, match.mention_end)
        )
    return spans


def _overlaps_existing(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(
        start < existing_end and end > existing_start
        for existing_start, existing_end in spans
    )
