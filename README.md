# Foreign Agent Checker

Compliance-assistance CLI for checking Rambler articles against the official
Russian Ministry of Justice foreign-agent registry.

The tool loads a Rambler article URL, loads or refreshes a Minjust registry
snapshot, runs deterministic checks, and renders a Markdown or JSON report. It
helps surface text mentions, author signals, and full resource-link matches
that may require human review. It does not provide legal conclusions.

## Requirements

Required:

- Python 3.11+
- Poetry
- Make

Optional but required for agentic mode:

- Ollama running locally
- Local model available in Ollama, recommended: `qwen2.5:14b-instruct`

Deterministic mode does not require Ollama.
Agentic mode requires Ollama because weak candidates are reviewed by a local LLM.

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
poetry run fa-checker "https://www.rambler.ru/..." --mode deterministic --enable-fuzzy
```
or equivalent Make target:

```bash
make run-deterministic-fuzzy URL=https://www.rambler.ru/...
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
poetry run fa-checker "https://www.rambler.ru/..." --mode agentic --enable-fuzzy
```

or equivalent Make target:

```bash
make run-agentic-fuzzy URL=https://www.rambler.ru/...
```

## Quickstart

Clone the repository:

```bash
git clone git@github.com:MarsBroshok96/foreign-agent-checker.git
cd foreign-agent-checker
```

Install dependencies:

```bash
poetry install
```

Run checks that do not require Ollama:

```bash
make check
make eval-deterministic
```

Run deterministic mode on a Rambler article:

```bash
make run-deterministic-fuzzy URL=https://news.rambler.ru/...
```
Deterministic mode downloads and caches the Minjust registry automatically.


## Ollama setup for agentic mode

Agentic mode uses the local Ollama API.

Copy optional environment defaults:

```bash
cp .env.example .env
```

For agentic mode, run a local Ollama server. The default model is
`qwen2.5:14b-instruct`.
Any Ollama-compatible local model can be used, but agentic quality is model-dependent. Run make eval-agentic-trace after changing OLLAMA_MODEL.
Agentic mode uses Ollama local API at OLLAMA_BASE_URL.
Default: http://localhost:11434.

Install or start Ollama according to your operating system, then pull the recommended model:

Install Ollama server:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Pull ollama model:

```bash
ollama pull qwen2.5:14b-instruct
```

Start the Ollama server:

```bash
ollama serve
```

In another terminal, verify that the model is available:

```bash
ollama list
```
Then run agentic mode (without or with fuzzy mode):

```bash
make run-agentic URL=https://news.rambler.ru/...
make run-agentic-fuzzy URL=https://news.rambler.ru/...
```

Agentic eval with trace:

```bash
make eval-agentic-trace
```

## Common runs:

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
make run-agentic-json
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
Its tested with Open AI CODEX (docs/context-profile-enrichment/SKILL.md)



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
make eval-agentic
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

## Recommended verification flow

For a quick review without LLM:

```bash
poetry install
make check
make eval-deterministic
make eval-no-llm
make run-deterministic-fuzzy URL=https://news.rambler.ru/...
```
For full agentic review:

```bash
ollama pull qwen2.5:14b-instruct
ollama serve
make eval-agentic-trace
make run-agentic-fuzzy URL=https://news.rambler.ru/...
```

Expected behavior:

make check should pass without Ollama.
make eval-deterministic should pass without Ollama.
make eval-no-llm should skip agentic cases.
make eval-agentic-trace requires Ollama and shows whether cases used clean LLM calls or conservative fallback.


## Project structure

Important paths:

| Path | Purpose |
|---|---|
| `src/fa_checker/pipeline.py` | Deterministic and agentic entry points. |
| `src/fa_checker/matching/` | Exact, fuzzy, label, author, and resource-link checks. |
| `src/fa_checker/agent/` | Bounded LLM review, action selection, disambiguation, context profiles. |
| `src/fa_checker/reporting/` | Markdown/JSON report rendering and summary helpers. |
| `scripts/run_eval.py` | Lightweight eval runner. |
| `tests/eval_cases/basic_eval.json` | Machine-readable eval cases. |
| `docs/architecture.md` | Runtime architecture. |
| `docs/agent.md` | Agentic review behavior. |
| `docs/eval_plan.md` | Eval design and criteria. |