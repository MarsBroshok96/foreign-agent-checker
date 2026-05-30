# Agentic Review

## Scope

Agentic mode is a bounded review layer for weak text/fuzzy candidates. It is
not a free-form chatbot and it does not replace deterministic compliance logic.

The deterministic baseline always runs first. The review layer receives
structured `DeterministicAnalysisResult` and `AgentReviewState` data built from
that baseline.

## What Is Reviewed

Reviewed by the LLM:

- weak alias candidates;
- optional person-only fuzzy candidates.

Not reviewed by the LLM in the current MVP:

- strong deterministic text findings;
- article-author checks;
- full resource URL matches;
- registry loading/parsing;
- final risk/status/report generation.

## Allowed Actions

For each weak candidate, the LLM may choose one bounded action:

- `request_context`;
- `disambiguate_candidate`;
- `request_human_review`;
- `finalize`.

Python validates every action before it is applied. Context requests are
limited to two per candidate. `request_human_review` and
`disambiguate_candidate` are terminal candidate actions; the model does not need
to emit `finalize` afterward.

## Context

Article context is retrieved deterministically from already-loaded article
text. Local context profiles are optional auxiliary JSON data for
disambiguation. They may include descriptors, projects, domains, common mention
forms, and false-positive hints.

Context profiles are not a source of foreign-agent status. The official
Ministry of Justice registry remains the source of truth. Runtime agentic
review does not browse the internet.

## Failure And Fallback

Malformed model JSON, invalid actions, unavailable Ollama, exceeded context
limits, and unsafe premature finalization all degrade conservatively. The
candidate is marked uncertain or requiring human review rather than broadening
the tool scope or inventing a fact.

LLM action outputs may be normalized or repaired only when there is a safe
bounded action. For example, a context request beyond the limit can be repaired
to disambiguation when context is already available.

## Scoring And Reporting

Disambiguation results are fed back into deterministic scoring. Final risk,
report status, Markdown rendering, and JSON rendering are deterministic.

Agentic review can reject weak candidates. If all weak candidates are rejected
and no author/resource-link signal exists, final status can be `no_match`;
rejected candidates remain visible in the report for auditability.

## Evaluation Trace

`make eval-agentic-trace` runs agentic eval cases and prints compact trace
information for action selection, disambiguation calls, repairs, and fallbacks.
`PASS_LLM` indicates clean LLM-assisted behavior. `ACCEPTABLE_FALLBACK`
indicates conservative fallback behavior.

## Prompting Rules

Prompts must:

- keep the official registry as source of truth;
- prohibit runtime web browsing;
- require structured JSON output;
- avoid legal conclusions;
- escalate uncertainty to human review;
- ground rationales in provided article context, registry entry, and optional
  local context profile data.
