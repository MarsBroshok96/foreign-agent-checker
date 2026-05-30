# Architecture

## Purpose

Foreign Agent Checker is a compliance-assistance CLI for checking Rambler
articles against the official Russian Ministry of Justice foreign-agent
registry. It produces evidence-based findings and human-review signals; it does
not make legal conclusions.

## High-Level Flow

```text
CLI
  -> Rambler article loader/extractor
  -> Minjust registry loader/cache/parser
  -> deterministic analysis
       -> exact/alias matching
       -> optional person-only fuzzy recall
       -> label checking
       -> author check
       -> full resource URL check
       -> deterministic risk scoring
  -> optional bounded agentic review for weak text/fuzzy candidates
  -> deterministic Markdown/JSON report
```

## Source Of Truth

The official Ministry of Justice registry is the only source of truth for
foreign-agent status. Context profiles may help disambiguate weak candidates,
but they do not create registry facts and must not override the registry.

## Deterministic Layer

The deterministic layer always runs first in both CLI modes. It is responsible
for article loading/extraction, registry loading/cache parsing, candidate
generation, label checks, author checks, resource-link checks, risk scoring,
and report construction.

Exact and alias matching operate over normalized article text. Optional fuzzy
recall is disabled by default and applies only to person registry entries. Fuzzy
candidates are weak candidates and require disambiguation or human review.

Author checks and full resource URL checks are deterministic side signals. They
can affect final report status, but they are not reviewed by the LLM in the
current MVP.

## Agentic Review

Agentic mode runs the deterministic baseline first, then sends only weak
text/fuzzy candidates to a bounded local Ollama review loop. Strong candidates
are not sent to the LLM by default.

For each weak candidate, the LLM may choose only bounded actions such as
requesting article context, disambiguating the candidate, requesting human
review, or finalizing that candidate review. Python validates and repairs or
rejects actions according to policy. Invalid output, Ollama errors, or unsafe
steps degrade conservatively to human review.

The runtime agent does not browse the internet. Local context profile lookup is
deterministic support data, not an open-ended LLM tool.

## Reporting

Final score, report status, Markdown rendering, and JSON rendering are
deterministic. Markdown is optimized for human review and groups repeated
findings. JSON preserves raw findings for tests and audit.

## Evaluation

The eval runner supports deterministic and agentic checks. Deterministic evals
are strict and require no Ollama. Agentic evals can report clean LLM passes or
safe fallback outcomes with action/disambiguation trace accounting.

## Non-Goals

- Web UI.
- Database.
- LangChain, LangGraph, browser automation, or Selenium/Playwright workflows.
- Runtime internet enrichment.
- Production legal decision-making.
- Automatic enrichment for the whole registry.
