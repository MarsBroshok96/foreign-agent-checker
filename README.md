# Foreign Agent Checker

A bounded tool-calling agent for checking Rambler articles against the official Russian Ministry of Justice foreign-agent registry.

## Purpose

The tool accepts a Rambler article URL, extracts article text and metadata, checks the article against the official registry, and produces a short evidence-based report.

The system is designed for compliance assistance and human review. It does not provide legal conclusions.

## MVP capabilities

- CLI input for Rambler article URL
- article loading and text extraction
- registry loading and local snapshot parsing
- exact, alias, and fuzzy matching
- deterministic article-author check
- deterministic full resource-link check
- optional person-only fuzzy recall
- bounded LLM-agent review through local Ollama
- weak candidate disambiguation
- label checking
- deterministic risk scoring
- Markdown and JSON report output

## Architecture

The project uses a bounded semi-agentic architecture:


deterministic pipeline
→ structured agent state
→ bounded tool-calling loop
→ deterministic risk scoring
→ report generation

See:

docs/architecture.md
docs/contracts.md
docs/agent.md


## Installation
```bash
poetry install
```

Environment

Copy example env file:
```bash
cp .env.example .env
```

Expected local Ollama server:
```bash
ollama serve
```

Default model:
```bash
qwen2.5:14b-instruct
```

## Run
```bash
poetry run fa-checker
```
or:
```bash
make run
```

## CLI modes

Deterministic mode is the default. It does not call an LLM. It loads the
Rambler article and registry, then runs exact/alias matching, label checking,
deterministic author checking, full resource-link checking, and deterministic
risk scoring.

```bash
poetry run fa-checker "URL" --mode deterministic
```

Agentic mode runs the deterministic baseline first, then reviews only weak
candidates through a bounded local Ollama action loop. The LLM may request
article context, ask for disambiguation, request human review, or finalize that
candidate review. Python validates every action, local context profiles are
auxiliary data, there is no internet browsing, and final risk remains
deterministic.

```bash
poetry run fa-checker "URL" --mode agentic
poetry run fa-checker "URL" --mode agentic --context-profiles-path data/context/context_profiles.json
poetry run fa-checker "URL" --registry-path data/samples/registries/minjust_export_sample.xlsx
```

Optional fuzzy recall is disabled by default. When enabled, it applies only to
person registry entries and creates weak candidates that require disambiguation
or human review. It intentionally does not run for organizations, media,
projects, domains, or resource links.

```bash
poetry run fa-checker "URL" --mode deterministic --enable-fuzzy
poetry run fa-checker "URL" --mode agentic --enable-fuzzy
```

## Context Profiles

Context profiles are optional auxiliary data for disambiguation. They are not a
source of foreign-agent status, and the runtime agent does not browse the
internet.

Profiles can be enriched offline by a developer or Codex-assisted workflow.
Useful developer commands:

```bash
poetry run python scripts/validate_context_profiles.py data/context/context_profiles.json --registry-xlsx data/registry/minjust_registry_latest.xlsx
poetry run python scripts/profile_coverage.py data/registry/minjust_registry_latest.xlsx data/context/context_profiles.json --limit 50
```

See [docs/context_profile_enrichment_skill.md](docs/context_profile_enrichment_skill.md).

## Report Interpretation

Markdown reports separate the deterministic layer summary, agentic review
summary, and final finding groups:

- confirmed/probable findings that do not require human review;
- candidates requiring human review;
- candidates rejected after review.

If all weak candidates are rejected, the overall status may be `no_match` while
the report still lists rejected candidates for auditability. The report is a
compliance-assistance artifact, not a legal verdict.

For readability, Markdown groups repeated findings with the same entity and
status while preserving all evidence fragments. JSON output keeps raw findings
unmerged for machine processing and audit.

The report also includes deterministic checks that are not sent to agentic
review in the current MVP:

- article author against strong and weak registry aliases;
- full article-body links against full registry resource URLs.

The resource-link check compares normalized full URLs only. It does not treat a
shared domain as a match. Weak author matches remain deterministic human-review
signals; they are not disambiguated by the LLM in this mode.

## Test
```bash
make test
make lint
```

## Important limitation

The system does not issue a legal verdict. It produces evidence-based findings and highlights cases requiring human review.
