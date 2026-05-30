# Foreign Agent Checker

Compliance-assistance CLI for checking Rambler articles against the official
Russian Ministry of Justice foreign-agent registry.

The tool loads a Rambler article URL, loads or refreshes a Minjust registry
snapshot, runs deterministic checks, and renders a Markdown or JSON report. It
helps surface text mentions, author signals, and full resource-link matches
that may require human review. It does not provide legal conclusions.

## Modes

### Deterministic

Deterministic mode is the default and does not call an LLM. It performs:

- Rambler article loading and extraction;
- Minjust registry loading, caching, and XLSX parsing;
- exact and alias text matching;
- optional person-only fuzzy recall with `--enable-fuzzy`;
- foreign-agent label proximity/article-level checking;
- article-author checks against registry aliases;
- full resource URL checks against registry resource URLs;
- deterministic risk scoring and report generation.

```bash
poetry run fa-checker "https://www.rambler.ru/..." --mode deterministic
```

### Agentic

Agentic mode always runs the deterministic baseline first. It then reviews only
weak text/fuzzy candidates through a bounded local Ollama action loop. Strong
deterministic findings, author checks, and resource-link checks are not sent to
the LLM.

The LLM may request bounded article context, choose disambiguation, request
human review, or finalize a candidate review. Python validates actions, local
context profiles are auxiliary only, the runtime agent does not browse the
internet, and final scoring/reporting remain deterministic.

```bash
poetry run fa-checker "https://www.rambler.ru/..." --mode agentic
```

## Quickstart

Install dependencies:

```bash
poetry install
```

Copy optional environment defaults:

```bash
cp .env.example .env
```

For agentic mode, run a local Ollama server. The default model is
`qwen2.5:14b-instruct`.

```bash
ollama serve
```

Common runs:

```bash
poetry run fa-checker "URL" --mode deterministic
poetry run fa-checker "URL" --mode agentic
poetry run fa-checker "URL" --registry-path data/samples/registries/minjust_export_sample.xlsx
poetry run fa-checker "URL" --mode deterministic --enable-fuzzy
poetry run fa-checker "URL" --mode agentic --enable-fuzzy
poetry run fa-checker "URL" --output-format json
poetry run fa-checker "URL" --mode agentic --context-profiles-path data/context/context_profiles.json
```

Equivalent Make targets include:

```bash
make run-deterministic
make run-agentic
make run-json
make run-deterministic-fuzzy
make run-agentic-fuzzy
```

## Context Profiles

Context profiles are local JSON files used only to help disambiguate weak
candidates in agentic mode. They are not a source of foreign-agent status and
must not override the official registry.

Runtime agentic review does not browse the internet. Profile enrichment is an
offline/developer workflow documented in
[docs/context_profile_enrichment_skill.md](docs/context_profile_enrichment_skill.md).

Useful profile commands:

```bash
poetry run python scripts/profile_coverage.py data/registry/minjust_registry_latest.xlsx data/context/context_profiles.json --limit 50
poetry run python scripts/validate_context_profiles.py data/context/context_profiles.json --registry-xlsx data/registry/minjust_registry_latest.xlsx
```

## Reports

Markdown reports include metadata, a short summary, deterministic-layer counts,
agentic-review counts when applicable, resource-link matches, grouped findings,
and limitations.

JSON reports preserve raw findings for tests, integration, and audit. Markdown
groups repeated findings for readability.

## Evaluation

The eval set lives at `tests/eval_cases/basic_eval.json`; the runner is
`scripts/run_eval.py`.

```bash
make eval-deterministic
make eval-no-llm
make eval-agentic-trace
```

`PASS` is a strict deterministic pass. `PASS_LLM` means an agentic case passed
with clean LLM action/disambiguation calls. `ACCEPTABLE_FALLBACK` means the
product stayed conservative, but the trace showed fallback or missing clean LLM
disambiguation. Dangerous failures are outcomes that weaken the compliance
posture, such as confirming a false positive without human review.

## Test

```bash
make check
```

## Limitations

- The report is not a legal verdict.
- The tool is conservative but cannot guarantee full recall.
- Fuzzy recall is person-only.
- Runtime agentic review does not browse the internet.
- Character offsets may be approximate after text normalization.
- Agentic outcomes depend on local model quality and may safely degrade to
  human review.
