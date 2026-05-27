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

LLM may be used for:

- entity extraction;
- weak candidate disambiguation;
- short narrative explanation from structured findings.

LLM must not:

- browse the web;
- invent registry entries;
- change the source of truth;
- make legal conclusions;
- finalize reports before mandatory checks are complete.

## Coding style

Prefer small modules with clear responsibilities.

Use Pydantic models for contracts.

Avoid passing unstructured dictionaries between major layers.

Write tests for deterministic logic.

Prefer explicit names over clever abstractions.

Avoid overengineering.

## Current implementation phase

The current phase is project scaffolding only.

Do not implement full business logic yet.

Create importable modules, placeholder classes/functions, CLI skeleton, domain models, and tests that verify the skeleton works.
