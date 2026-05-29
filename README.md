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
and deterministic risk scoring.

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
poetry run fa-checker "URL" --mode agentic --context-profiles-path data/context/context_profiles.example.json
poetry run fa-checker "URL" --registry-path data/samples/registries/minjust_export_sample.xlsx
```

## Test
```bash
make test
make lint
```

## Important limitation

The system does not issue a legal verdict. It produces evidence-based findings and highlights cases requiring human review.
