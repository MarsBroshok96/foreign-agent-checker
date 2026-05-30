# Contracts

This document defines the stable domain contracts used across the project.

All production data moving between components should be represented by Pydantic models.

## Article

Represents extracted article content and metadata.

```python
class Article(BaseModel):
    url: str
    source_domain: str
    title: str | None
    author: str | None
    published_at: datetime | None
    text: str
    links: list[str]
```
## RegistryEntry

Represents one entity from the official registry.

```python
class RegistryEntry(BaseModel):
    registry_id: str | None
    full_name: str
    entity_type: Literal["person", "organization", "media", "project", "unknown"]
    normalized_name: str
    aliases: list[str]
    registry_source_url: str
    registry_snapshot_date: date | None
    raw_fields: dict[str, Any]
```

## ContextProfile

Auxiliary context used only for disambiguation.

Important: context profiles are not a source of truth for foreign-agent status.

```python
class ContextProfile(BaseModel):
    registry_id: str | None
    entity_name: str
    entity_type: str
    known_descriptors: list[str]
    known_projects: list[str]
    known_domains: list[str]
    notes: str | None
    sources: list[str]
    retrieved_at: datetime | None
```
## EvidenceFragment

Represents an auditable piece of evidence.

```python
class EvidenceFragment(BaseModel):
    source: Literal["article_text", "article_author", "article_link", "registry", "context_profile"]
    text: str
    start: int | None = None
    end: int | None = None
```

## CandidateMatch

Represents a possible match between article mention and registry entity.

```python
class CandidateMatch(BaseModel):
    mention_text: str
    mention_start: int | None
    mention_end: int | None
    registry_entry: RegistryEntry
    match_type: Literal["exact", "alias", "fuzzy", "author", "domain", "llm_entity"]
    match_score: float
    evidence: list[EvidenceFragment]
    requires_disambiguation: bool
```
## DisambiguationResult

Represents LLM-assisted ambiguity resolution.

```python
class DisambiguationResult(BaseModel):
    decision: Literal["same_entity", "likely_same_entity", "uncertain", "different_entity"]
    confidence_score: float
    rationale: str
    requires_human_review: bool
```

## LabelCheckResult

Represents whether a foreign-agent label appears near the mention or in the article.

```python
class LabelCheckResult(BaseModel):
    label_found: bool
    label_fragment: str | None
    label_distance: int | None
    label_quality: Literal["exact", "weak", "absent"]
```

## FinalFinding

Represents one final report finding.

```python
class FinalFinding(BaseModel):
    entity_name: str
    mention_text: str
    status: Literal["confirmed", "probable", "uncertain", "rejected"]
    risk_level: Literal["no_match", "low", "medium", "high"]
    confidence_level: Literal["low", "medium", "high"]
    label_status: Literal["present", "weak", "absent", "not_checked"]
    requires_human_review: bool
    evidence: list[EvidenceFragment]
    rationale: str
```
## CheckReport

Represents final machine-readable output.

```python
class CheckReport(BaseModel):
    article_url: str
    article_title: str | None
    article_author: str | None
    checked_at: datetime
    registry_snapshot_date: date | None
    status: Literal["no_match", "potential_match_found", "confirmed_match_found", "error"]
    findings: list[FinalFinding]
    limitations: list[str]
```

## Design rule

No component should pass unstructured dictionaries across major module boundaries unless the dictionary is raw external data before parsing.
