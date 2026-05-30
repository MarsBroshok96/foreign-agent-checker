# Architecture

## Purpose

This project implements a bounded tool-calling agent that checks a Rambler article for mentions of entities listed in the official Russian Ministry of Justice foreign-agent registry.

The system is designed as a compliance-assistance tool, not as a legal decision-maker. It produces evidence-based findings and highlights cases that require human review.

## Core architectural principle

The solution is not a free-form LLM chatbot. It is a bounded semi-agentic system:

1. A deterministic pipeline performs source loading, article extraction, registry parsing, normalization, and first-pass candidate generation.
2. A bounded LLM agent receives structured state and may call a limited set of tools.
3. Python orchestrator validates every tool call against policy, state, and schemas.
4. Final risk scoring is deterministic.
5. Ambiguous cases are escalated to human review.

## High-level flow

```text
CLI
 ↓
URL validation
 ↓
Article loading
 ↓
Article text and metadata extraction
 ↓
Registry loading and parsing
 ↓
Candidate generation
   ├─ exact matching
   ├─ alias matching
   ├─ fuzzy matching
   ├─ author checking
   └─ optional domain/link checking
 ↓
Bounded agentic review
   ├─ decides next tool call
   ├─ receives observation
   ├─ updates state
   └─ stops only when completion criteria are satisfied
 ↓
Risk scoring
 ↓
Markdown and JSON report generation
```

## What is deterministic

The following components must be deterministic and covered by tests:

URL validation
article loading
text extraction fallback logic
text normalization
registry parsing
alias generation
exact matching
fuzzy matching
label checking
risk scoring
report schema generation

## What may use LLM

LLM may be used only for bounded reasoning tasks:

extracting named entities from article text;
disambiguating weak candidate matches;
generating human-readable explanation from structured findings.

## LLM must not:

replace the official registry as source of truth;
browse the internet;
invent registry entries;
issue a legal verdict;
finalize a report before mandatory checks are complete.

## Agentic design

The implemented review loop receives structured deterministic analysis state
and bounded review-candidate state.

At each step it must return one of the following structured actions:

call a tool;
request human review;
finalize report.

The orchestrator decides whether the requested action is allowed.

## Completion criteria

The agent cannot finalize a report until:

1. article text has been extracted;
2. registry has been loaded;
3. deterministic candidate generation has completed;
4. recall pass has completed;
5. weak candidates have been disambiguated or escalated;
6. labels have been checked for confirmed/probable findings;
7. risk scoring has completed.

## Risk posture

The system is optimized for high recall in candidate generation and conservative precision in final confirmed findings.

Uncertain cases must be marked as requiring human review.

## Output formats

The system produces:

1. Markdown report for human review.
2. JSON report for tests, integration, and auditability.

## Non-goals for MVP

The MVP does not include:

web UI;
database;
LangChain or LangGraph;
browser automation;
continuous monitoring of multiple articles;
production-grade legal compliance;
automatic biographical enrichment for the whole registry.
