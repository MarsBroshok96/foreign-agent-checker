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

Inside each weak-candidate review, the LLM may choose only these actions:

- request_context;
- disambiguate_candidate;
- request_human_review;
- finalize.

The Python orchestrator validates every action before execution. Context profile
lookup is automatic deterministic support data; it is not an LLM tool and it is
not a source of foreign-agent status. Final scoring remains deterministic.
Ollama failures, invalid actions, or invalid model output degrade to uncertain
findings that require human review.

LLM action outputs are parsed tolerantly for common JSON mistakes, then repaired
only when there is a safe bounded action to take. For example, a third
request_context action can be repaired to disambiguate_candidate when context is
already available and the two-request context limit has been reached.

request_human_review and disambiguate_candidate are terminal candidate actions;
the model does not need to emit finalize afterward. Context requests are limited
to two per candidate. Invalid or unsafe actions degrade to human review rather
than crashing or broadening the tool scope.

Agentic review can reject weak candidates. If all candidates are rejected, the
overall report status can become `no_match`; rejected candidates remain in the
report for auditability.

When available, the disambiguation rationale from agentic review is shown in
the final report separately from deterministic risk-scoring rationale.

Author checks and resource-link checks are deterministic side checks. The
author check compares the article author to registry aliases, and the
resource-link check compares full article-body URLs to full registry resource
URLs. These signals can affect the final report status, but they are not sent to
the LLM review loop in the current MVP. Agentic review remains limited to weak
text candidates.

Fuzzy matching is also a deterministic recall pass, not an LLM tool. It is
disabled by default and can be enabled explicitly for person entries only.
Fuzzy candidates are always weak candidates that require disambiguation or human
review. The MVP intentionally does not fuzzy-match organizations, projects,
media, domains, or resource links.

The runtime agent does not browse the internet.

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

## Future general tool-call loop

The current implemented loop is intentionally narrower than a general agent. A
future broader orchestrator may run a bounded loop:

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
