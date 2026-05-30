"""Shared enumerations used by domain models."""

from enum import StrEnum


class EntityType(StrEnum):
    PERSON = "person"
    ORGANIZATION = "organization"
    MEDIA = "media"
    PROJECT = "project"
    UNKNOWN = "unknown"


class EvidenceSource(StrEnum):
    ARTICLE_TEXT = "article_text"
    ARTICLE_AUTHOR = "article_author"
    ARTICLE_LINK = "article_link"
    REGISTRY = "registry"
    CONTEXT_PROFILE = "context_profile"


class MatchType(StrEnum):
    EXACT = "exact"
    ALIAS = "alias"
    FUZZY = "fuzzy"
    AUTHOR = "author"
    DOMAIN = "domain"
    LLM_ENTITY = "llm_entity"


class DisambiguationDecision(StrEnum):
    SAME_ENTITY = "same_entity"
    LIKELY_SAME_ENTITY = "likely_same_entity"
    UNCERTAIN = "uncertain"
    DIFFERENT_ENTITY = "different_entity"


class LabelQuality(StrEnum):
    EXACT = "exact"
    WEAK = "weak"
    ABSENT = "absent"


class FindingStatus(StrEnum):
    CONFIRMED = "confirmed"
    PROBABLE = "probable"
    UNCERTAIN = "uncertain"
    REJECTED = "rejected"


class RiskLevel(StrEnum):
    NO_MATCH = "no_match"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ConfidenceLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class LabelStatus(StrEnum):
    PRESENT = "present"
    WEAK = "weak"
    ABSENT = "absent"
    NOT_CHECKED = "not_checked"


class ReportStatus(StrEnum):
    NO_MATCH = "no_match"
    POTENTIAL_MATCH_FOUND = "potential_match_found"
    CONFIRMED_MATCH_FOUND = "confirmed_match_found"
    ERROR = "error"

