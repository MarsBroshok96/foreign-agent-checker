# Instructions for Codex

## Project role

You are implementing a bounded tool-calling agent for checking Rambler articles against the official Russian Ministry of Justice foreign-agent registry.

This is a compliance-assistance tool. It must be deterministic where possible, auditable, and conservative in final conclusions.

## Architectural constraints

Do not implement a free-form chatbot.

Do not add LangChain, LangGraph, LlamaIndex, Selenium, Playwright, pandas, or database dependencies unless explicitly requested.

Use the existing planned stack:

- Python
- Poetry
- Pydantic
- httpx
- BeautifulSoup
- trafilatura
- rapidfuzz
- openpyxl
- Typer
- Rich
- pytest
- ruff

## Source of truth

The official Ministry of Justice registry is the only source of truth for foreign-agent status.

Auxiliary context profiles may be used only for disambiguation. They must not create new foreign-agent facts.

## LLM policy

Runtime LLM use is currently limited to:

- bounded action selection for weak-candidate review;
- weak candidate disambiguation;

LLM must not:

- browse the web;
- invent registry entries;
- change the source of truth;
- make legal conclusions;
- finalize reports before mandatory checks are complete.

Entity extraction or narrative generation may be added only if explicitly
requested and kept within the same source-of-truth and auditability boundaries.

## Coding style

Prefer small modules with clear responsibilities.

Use Pydantic models for contracts.

Avoid passing unstructured dictionaries between major layers.

Write tests for deterministic logic.

Prefer explicit names over clever abstractions.

Avoid overengineering.

## Current implementation phase

The project is a working MVP. Prefer small, behavior-preserving changes unless
the user explicitly asks for new functionality.

Before finalizing code changes, run:

- `make check`
- `make eval-deterministic`
- `make eval-no-llm`

Agentic eval requires local Ollama; run `make eval-agentic-trace` when
available.

Do not add runtime internet access, change source-of-truth assumptions, or let
the LLM finalize reports outside the bounded review policy.
