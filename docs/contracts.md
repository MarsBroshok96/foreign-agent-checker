# Contracts

Stable data crossing major component boundaries is represented with Pydantic
models. Raw dictionaries should stay close to external input parsing.

## Article

`fa_checker.domain.models.Article`

```python
class Article(BaseModel):
    url: str
    source_domain: str
    title: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    text: str
    links: list[str] = []
```

## RegistryEntry

`fa_checker.domain.models.RegistryEntry`

```python
class RegistryEntry(BaseModel):
    registry_id: str | None = None
    full_name: str
    entity_type: EntityType
    normalized_name: str
    aliases: list[str] = []
    registry_source_url: str
    registry_snapshot_date: date | None = None
    raw_fields: dict[str, Any] = {}
```

## ContextProfile

Canonical location: `fa_checker.agent.context_profiles.ContextProfile`.

Context profiles are local auxiliary data for disambiguation only. They are not
a source of foreign-agent status.

```python
class ContextProfile(BaseModel):
    registry_id: str | None = None
    entity_name: str
    entity_type: str | None = None
    role_or_category: str | None = None
    short_description: str | None = None
    descriptors: list[str] = []
    known_projects: list[str] = []
    known_domains: list[str] = []
    common_mentions: list[str] = []
    disambiguation_hints: list[str] = []
    negative_context_hints: list[str] = []
    primary_language: str | None = None
    confidence: str | None = None
    notes: str | None = None
    sources: list[str] = []
```

## CandidateMatch

`fa_checker.domain.models.CandidateMatch`

```python
class CandidateMatch(BaseModel):
    mention_text: str
    mention_start: int | None = None
    mention_end: int | None = None
    registry_entry: RegistryEntry
    match_type: MatchType
    match_score: float
    evidence: list[EvidenceFragment] = []
    requires_disambiguation: bool
```

## EvidenceFragment

`fa_checker.domain.models.EvidenceFragment`

```python
class EvidenceFragment(BaseModel):
    source: EvidenceSource
    text: str
    start: int | None = None
    end: int | None = None
```

## LabelCheckResult

`fa_checker.domain.models.LabelCheckResult`

```python
class LabelCheckResult(BaseModel):
    label_found: bool
    label_fragment: str | None = None
    label_distance: int | None = None
    label_quality: LabelQuality
```

## AuthorCheckResult

`fa_checker.domain.models.AuthorCheckResult`

```python
class AuthorCheckResult(BaseModel):
    author_name: str | None = None
    status: str
    registry_id: str | None = None
    entity_name: str | None = None
    match_type: str | None = None
    match_score: float | None = None
    requires_human_review: bool = False
    rationale: str
```

## ResourceLinkMatch

`fa_checker.domain.models.ResourceLinkMatch`

```python
class ResourceLinkMatch(BaseModel):
    registry_id: str | None = None
    entity_name: str
    entity_type: str | None = None
    article_url: str
    registry_url: str
    normalized_article_url: str
    normalized_registry_url: str
    rationale: str
```

## DisambiguationResult

`fa_checker.domain.models.DisambiguationResult`

```python
class DisambiguationResult(BaseModel):
    decision: DisambiguationDecision
    confidence_score: float
    rationale: str
    requires_human_review: bool
```

## FinalFinding

`fa_checker.domain.models.FinalFinding`

```python
class FinalFinding(BaseModel):
    entity_name: str
    mention_text: str
    match_type: MatchType | None = None
    match_score: float | None = None
    status: FindingStatus
    risk_level: RiskLevel
    confidence_level: ConfidenceLevel
    label_status: LabelStatus
    requires_human_review: bool
    evidence: list[EvidenceFragment] = []
    rationale: str
    review_rationale: str | None = None
```

## ProcessingSummary

`fa_checker.domain.models.ProcessingSummary`

Tracks deterministic candidate counts, deterministic finding counts, optional
agentic review counts, final finding counts, author status, and resource-link
match totals. It is used by Markdown/JSON reports and eval summaries.

## CheckReport

`fa_checker.domain.models.CheckReport`

```python
class CheckReport(BaseModel):
    article_url: str
    article_title: str | None = None
    article_author: str | None = None
    checked_at: datetime
    registry_snapshot_date: date | None = None
    status: ReportStatus
    findings: list[FinalFinding] = []
    resource_link_matches: list[ResourceLinkMatch] = []
    author_check: AuthorCheckResult | None = None
    limitations: list[str] = []
    processing_summary: ProcessingSummary | None = None
```

## AgentReviewState

`fa_checker.agent.state.AgentReviewState`

Holds deterministic analysis, weak review candidates, per-candidate context
request counts, review history, limitations, and final findings for bounded
agentic review.

## AgentReviewAction

`fa_checker.agent.schemas.AgentReviewAction`

```python
class AgentReviewAction(BaseModel):
    action_type: Literal[
        "request_context",
        "disambiguate_candidate",
        "finalize",
        "request_human_review",
    ]
    candidate_index: int | None = None
    context_window_size: Literal["small", "medium", "large"] | None = None
    reason: str
```
