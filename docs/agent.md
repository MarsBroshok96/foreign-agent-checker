# Agent Design

## Agent type

The project uses a bounded tool-calling agent.

The agent is not fully autonomous. It operates under strict policy constraints and is not allowed to replace deterministic compliance logic.

## Agent responsibility

The agent is responsible for choosing additional checks when deterministic matching is insufficient or incomplete.

The agent may:

- request entity extraction;
- request context windows;
- request alias search;
- request fuzzy search;
- request disambiguation;
- request label checking;
- request risk scoring;
- request final report generation.

The agent must not:

- browse the web;
- change the registry source;
- invent registry entities;
- ignore mandatory recall checks;
- produce a legal verdict;
- finalize the report before policy allows it.

## Agent state

The agent receives structured state.

Example:

```json
{
  "article_loaded": true,
  "article_extracted": true,
  "registry_loaded": true,
  "candidate_generation_completed": true,
  "exact_matches_count": 0,
  "weak_candidates_count": 2,
  "entities_extracted": false,
  "recall_pass_completed": false,
  "disambiguation_completed": false,
  "label_check_completed": false,
  "risk_scored": false,
  "ready_to_report": false,
  "tool_call_count": 0
}
```

## Deterministic-first boundary

The deterministic layer always runs before any LLM review. It loads the already
available Article and RegistryEntry objects into mandatory exact matching, label
checking, and base risk scoring. The LLM agent must not decide whether these
checks run.

The future review layer receives a structured DeterministicAnalysisResult and
focuses first on weak candidate disambiguation. Strong confirmed findings do not
require agent review by default.

Context profile lookup will be deterministic support data in a later step. The
runtime agent must not browse the internet. Any broader context profile
enrichment should be performed offline by a developer workflow, not by the
bounded runtime agent.

## Context Profiles

Context profiles are local auxiliary JSON data for disambiguation. They may
contain descriptors, known projects, domains, and common mention forms, but they
do not determine foreign-agent status and must not override the official
registry. The source of truth remains the Ministry of Justice registry.

The runtime agent does not browse the internet. Future profile enrichment may be
performed offline by a developer or Codex workflow, then reviewed before use.

## Bounded review mode

Agentic CLI mode still runs the deterministic layer first. The bounded review
orchestrator reviews only weak candidates that require disambiguation; strong
deterministic findings are not sent to the LLM by default.

The LLM may only help decide whether a weak article mention refers to the
registry candidate. Local context profiles are auxiliary support data, not a
source of foreign-agent status. Ollama failures or invalid model output degrade
to uncertain findings that require human review.

# Available tools
get_context_window

Returns text around a mention.

## alias_search

Searches aliases for one mention.

## alias_search_batch

Searches aliases for multiple extracted entities.

## fuzzy_registry_search

Searches registry entries with fuzzy matching.

## entity_extractor

Extracts persons, organizations, media projects, domains, and suspicious mentions from article text.

May use LLM.

## disambiguate_entity

Determines whether a weak mention and registry candidate refer to the same entity.

Uses LLM and must return structured output.

## label_checker

Checks whether a foreign-agent label appears near the mention or elsewhere in the article.

## author_checker

Checks article author against registry.

## link_domain_checker

Checks article links and domains against known context profile domains.

## risk_scorer

Computes deterministic final risk level.

## report_generator

Generates Markdown and JSON reports from structured findings.

## Tool-call loop

The orchestrator runs a bounded loop:

```python
while not ready_to_report and step_count < max_steps:
    agent observes state
    agent returns structured action
    orchestrator validates action
    orchestrator executes tool
    orchestrator updates state
```

## Mandatory gates

The report cannot be finalized until:

1. candidate generation is completed;
2. recall pass is completed;
3. all weak candidates are disambiguated or marked for human review;
4. labels are checked for confirmed/probable findings;
5. risk scoring is completed.

## Policy violations

If the agent attempts to finalize too early, call an unavailable tool, or exceed max tool calls, the orchestrator must reject the action and either:

ask the agent for a valid next action;
or mark the report as requiring human review.

## Prompting principles

The LLM prompt must:

emphasize source-of-truth boundaries;
require structured JSON output;
prohibit legal conclusions;
require uncertainty escalation;
require short rationales grounded in evidence.

## Model assumptions

The initial local model is expected to run through Ollama.

Default model:

qwen2.5:14b-instruct

Model choice must be configurable via environment variable.
