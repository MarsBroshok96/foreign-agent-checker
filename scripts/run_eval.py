"""Lightweight eval runner for deterministic and bounded-agentic checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from fa_checker.agent.context_profiles import ContextProfile
from fa_checker.article.normalizer import normalize_for_matching
from fa_checker.domain.enums import EntityType, FindingStatus
from fa_checker.domain.models import Article, CheckReport, RegistryEntry
from fa_checker.pipeline import run_agentic_review_check, run_offline_check

DEFAULT_EVAL_PATH = Path("tests/eval_cases/basic_eval.json")
RESULT_PASS = "PASS"
RESULT_PASS_LLM = "PASS_LLM"
RESULT_ACCEPTABLE = "ACCEPTABLE"
RESULT_ACCEPTABLE_FALLBACK = "ACCEPTABLE_FALLBACK"
RESULT_FAIL = "FAIL"
RESULT_DANGEROUS_FAIL = "DANGEROUS_FAIL"
RESULT_SKIPPED = "SKIPPED"
ACTION_FALLBACK_MARKERS = (
    "LLM action selection failed",
    "LLM action output could not be parsed safely",
)
DISAMBIGUATION_FALLBACK_MARKERS = (
    "LLM disambiguation failed",
    "LLM output could not be parsed safely",
)


def load_eval_file(path: str | Path) -> dict[str, Any]:
    eval_path = Path(path)
    return json.loads(eval_path.read_text(encoding="utf-8"))


def build_article(data: dict[str, Any]) -> Article:
    return Article.model_validate(data)


def build_registry_entries(items: list[dict[str, Any]]) -> list[RegistryEntry]:
    entries: list[RegistryEntry] = []
    for item in items:
        full_name = item["full_name"]
        entries.append(
            RegistryEntry(
                registry_id=item.get("registry_id"),
                full_name=full_name,
                entity_type=EntityType(item.get("entity_type", "unknown")),
                normalized_name=item.get("normalized_name") or normalize_for_matching(full_name),
                aliases=item.get("aliases", []),
                registry_source_url=item.get("registry_source_url", "eval://registry"),
                registry_snapshot_date=None,
                raw_fields=item.get("raw_fields", {}),
            )
        )
    return entries


def build_context_profiles(items: list[dict[str, Any]] | None) -> list[ContextProfile]:
    return [ContextProfile.model_validate(item) for item in items or []]


def summarize_report(report: CheckReport) -> dict[str, Any]:
    findings = [_summarize_finding(finding) for finding in report.findings]
    summary = report.processing_summary
    return {
        "status": _value(report.status),
        "findings_count": len(report.findings),
        "confirmed_count": _count_findings(report, FindingStatus.CONFIRMED),
        "probable_count": _count_findings(report, FindingStatus.PROBABLE),
        "uncertain_count": _count_findings(report, FindingStatus.UNCERTAIN),
        "rejected_count": _count_findings(report, FindingStatus.REJECTED),
        "human_review_count": sum(
            finding.requires_human_review for finding in report.findings
        ),
        "resource_link_matches_count": len(report.resource_link_matches),
        "author_check_status": (
            report.author_check.status if report.author_check is not None else None
        ),
        "fuzzy_enabled": summary.fuzzy_enabled if summary is not None else False,
        "deterministic_fuzzy_candidates": (
            summary.deterministic_fuzzy_candidates if summary is not None else 0
        ),
        "findings": findings,
    }


def evaluate_case_result(
    case: dict[str, Any],
    report_or_summary: CheckReport | dict[str, Any],
    trace_summary: dict[str, Any] | None = None,
) -> tuple[str, list[str]]:
    summary = (
        summarize_report(report_or_summary)
        if isinstance(report_or_summary, CheckReport)
        else report_or_summary
    )
    trace_summary = trace_summary or empty_trace_summary()
    dangerous_reasons = _dangerous_reasons(
        case.get("dangerous", {}),
        case,
        summary,
        trace_summary,
    )
    if dangerous_reasons:
        return RESULT_DANGEROUS_FAIL, dangerous_reasons

    expected_reasons = _criteria_failures(
        case.get("expected", {}),
        summary,
        trace_summary,
    )
    if not expected_reasons:
        if case.get("mode") == "agentic":
            if _agentic_llm_success(trace_summary):
                return RESULT_PASS_LLM, ["expected checks passed with LLM disambiguation"]
            if _fallback_allowed(case):
                return RESULT_ACCEPTABLE_FALLBACK, [
                    "expected checks passed, but trace indicates fallback or no disambiguation"
                ]
            return RESULT_FAIL, [
                "expected checks passed, but no clean LLM disambiguation was observed"
            ]
        return RESULT_PASS, ["expected checks passed"]

    acceptable_reasons = _acceptable_failures(
        case.get("acceptable", {}),
        summary,
        trace_summary,
    )
    if not acceptable_reasons:
        if case.get("mode") == "agentic" and _trace_indicates_fallback(trace_summary):
            return RESULT_ACCEPTABLE_FALLBACK, [
                "acceptable fallback passed",
                *expected_reasons,
            ]
        return RESULT_ACCEPTABLE, ["acceptable fallback passed", *expected_reasons]

    return RESULT_FAIL, [*expected_reasons, *acceptable_reasons]


def run_case(case: dict[str, Any], trace: list[dict[str, Any]] | None = None) -> CheckReport:
    article = build_article(case["article"])
    registry_entries = build_registry_entries(case.get("registry_entries", []))
    context_profiles = build_context_profiles(case.get("context_profiles", []))
    enable_fuzzy = bool(case.get("enable_fuzzy", False))
    if case.get("mode") == "agentic":
        if trace is not None:
            return _run_agentic_case_with_trace(
                article=article,
                registry_entries=registry_entries,
                context_profiles=context_profiles,
                enable_fuzzy=enable_fuzzy,
                trace=trace,
            )
        return run_agentic_review_check(
            article,
            registry_entries,
            context_profiles=context_profiles,
            enable_fuzzy=enable_fuzzy,
        )
    return run_offline_check(
        article,
        registry_entries,
        enable_fuzzy=enable_fuzzy,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run foreign-agent checker eval cases.")
    parser.add_argument(
        "eval_file",
        nargs="?",
        default=str(DEFAULT_EVAL_PATH),
        help="Path to eval JSON file.",
    )
    parser.add_argument(
        "--mode",
        choices=["deterministic", "agentic", "all"],
        default="all",
        help="Filter eval cases by mode.",
    )
    parser.add_argument(
        "--skip-agentic",
        action="store_true",
        help="Skip agentic cases that may require local Ollama.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print report status and finding summaries.",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Print compact agentic action/disambiguation trace.",
    )
    args = parser.parse_args(argv)

    eval_data = load_eval_file(args.eval_file)
    cases = _filtered_cases(eval_data.get("cases", []), args.mode)
    counts = {
        RESULT_PASS: 0,
        RESULT_PASS_LLM: 0,
        RESULT_ACCEPTABLE: 0,
        RESULT_ACCEPTABLE_FALLBACK: 0,
        RESULT_FAIL: 0,
        RESULT_DANGEROUS_FAIL: 0,
        RESULT_SKIPPED: 0,
    }
    totals = empty_trace_summary()

    for case in cases:
        case_id = case.get("id", "<missing-id>")
        if args.skip_agentic and case.get("mode") == "agentic":
            counts[RESULT_SKIPPED] += 1
            print(f"{RESULT_SKIPPED} {case_id}: agentic case skipped")
            continue
        try:
            trace: list[dict[str, Any]] = []
            report = run_case(case, trace=trace if case.get("mode") == "agentic" else None)
            summary = summarize_report(report)
            trace_summary = summarize_trace(trace, report)
            _add_trace_totals(totals, trace_summary)
            result, reasons = evaluate_case_result(case, report, trace_summary)
        except Exception as exc:  # noqa: BLE001 - eval should continue across cases.
            result = RESULT_FAIL
            reasons = [f"case raised {type(exc).__name__}: {exc}"]
            summary = {}
            trace = []
            trace_summary = empty_trace_summary()

        counts[result] += 1
        print(f"{result} {case_id}: {_first_reason(reasons)}")
        if args.verbose and summary:
            print(f"  summary: {_compact_summary(summary)}")
        if args.trace and trace:
            print(f"  trace: {_compact_trace(trace, trace_summary)}")
        if result in {RESULT_FAIL, RESULT_DANGEROUS_FAIL}:
            for reason in reasons[1:]:
                print(f"  - {reason}")

    total = sum(counts.values())
    print(
        "Summary: "
        f"total={total} pass={counts[RESULT_PASS]} "
        f"pass_llm={counts[RESULT_PASS_LLM]} "
        f"acceptable={counts[RESULT_ACCEPTABLE]} "
        f"acceptable_fallback={counts[RESULT_ACCEPTABLE_FALLBACK]} "
        f"fail={counts[RESULT_FAIL]} "
        f"dangerous={counts[RESULT_DANGEROUS_FAIL]} skipped={counts[RESULT_SKIPPED]} "
        f"llm_calls_total={totals['action_selection_calls']} "
        f"disambiguation_calls_total={totals['disambiguation_calls']} "
        f"fallback_count_total={totals['fallback_count']}"
    )
    return 1 if counts[RESULT_FAIL] or counts[RESULT_DANGEROUS_FAIL] else 0


def _filtered_cases(cases: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    if mode == "all":
        return cases
    return [case for case in cases if case.get("mode") == mode]


def _run_agentic_case_with_trace(
    article: Article,
    registry_entries: list[RegistryEntry],
    context_profiles: list[ContextProfile],
    enable_fuzzy: bool,
    trace: list[dict[str, Any]],
) -> CheckReport:
    from fa_checker.agent import orchestrator

    original_choose = orchestrator.choose_review_action_with_llm
    original_disambiguate = orchestrator.disambiguate_candidate
    original_context = orchestrator.get_candidate_context
    original_repair = orchestrator.normalize_or_repair_action

    def choose_wrapper(*args, **kwargs):
        action = original_choose(*args, **kwargs)
        candidate = kwargs.get("candidate")
        trace.append(
            {
                "event": "action_selected",
                "candidate_index": getattr(candidate, "candidate_index", None),
                "allowed_actions": list(kwargs.get("allowed_actions", [])),
                "action_type": action.action_type,
                "context_window_size": action.context_window_size,
                "reason": action.reason,
                "fallback": _is_action_fallback(action.reason),
            }
        )
        return action

    def repair_wrapper(action, *args, **kwargs):
        repaired = original_repair(action, *args, **kwargs)
        if repaired != action:
            trace.append(
                {
                    "event": "action_repaired",
                    "from_action": action.action_type,
                    "to_action": repaired.action_type,
                    "reason": repaired.reason,
                }
            )
        return repaired

    def context_wrapper(state, candidate_index, window_size="small"):
        trace.append(
            {
                "event": "context_requested",
                "candidate_index": candidate_index,
                "window_size": window_size,
            }
        )
        return original_context(state, candidate_index, window_size=window_size)

    def disambiguate_wrapper(*args, **kwargs):
        result = original_disambiguate(*args, **kwargs)
        trace.append(
            {
                "event": "disambiguation_completed",
                "candidate_index": kwargs.get("candidate_index"),
                "decision": _value(result.decision),
                "confidence_score": result.confidence_score,
                "requires_human_review": result.requires_human_review,
                "rationale": result.rationale,
                "fallback": _is_disambiguation_fallback(result.rationale),
            }
        )
        return result

    orchestrator.choose_review_action_with_llm = choose_wrapper
    orchestrator.normalize_or_repair_action = repair_wrapper
    orchestrator.get_candidate_context = context_wrapper
    orchestrator.disambiguate_candidate = disambiguate_wrapper
    try:
        return run_agentic_review_check(
            article,
            registry_entries,
            context_profiles=context_profiles,
            enable_fuzzy=enable_fuzzy,
        )
    finally:
        orchestrator.choose_review_action_with_llm = original_choose
        orchestrator.normalize_or_repair_action = original_repair
        orchestrator.get_candidate_context = original_context
        orchestrator.disambiguate_candidate = original_disambiguate


def summarize_trace(
    trace: list[dict[str, Any]],
    report: CheckReport | None = None,
) -> dict[str, Any]:
    action_selection_calls = sum(event["event"] == "action_selected" for event in trace)
    disambiguation_calls = sum(
        event["event"] == "disambiguation_completed" for event in trace
    )
    action_selection_fallback_count = sum(
        event["event"] == "action_selected" and event.get("fallback") for event in trace
    )
    disambiguation_fallback_count = sum(
        event["event"] == "disambiguation_completed" and event.get("fallback")
        for event in trace
    )
    repaired_count = sum(event["event"] == "action_repaired" for event in trace)
    limitation_fallback_count = _limitation_fallback_count(report) if report else 0
    fallback_count = (
        action_selection_fallback_count
        + disambiguation_fallback_count
        + limitation_fallback_count
    )
    return {
        "action_selection_calls": action_selection_calls,
        "disambiguation_calls": disambiguation_calls,
        "action_selection_fallback_count": action_selection_fallback_count,
        "disambiguation_fallback_count": disambiguation_fallback_count,
        "repaired_count": repaired_count,
        "fallback_count": fallback_count,
        "selected_actions": [
            event["action_type"]
            for event in trace
            if event["event"] == "action_selected"
        ],
        "disambiguation_decisions": [
            event["decision"]
            for event in trace
            if event["event"] == "disambiguation_completed"
        ],
    }


def empty_trace_summary() -> dict[str, Any]:
    return {
        "action_selection_calls": 0,
        "disambiguation_calls": 0,
        "action_selection_fallback_count": 0,
        "disambiguation_fallback_count": 0,
        "repaired_count": 0,
        "fallback_count": 0,
        "selected_actions": [],
        "disambiguation_decisions": [],
    }


def _add_trace_totals(totals: dict[str, Any], summary: dict[str, Any]) -> None:
    for field in (
        "action_selection_calls",
        "disambiguation_calls",
        "action_selection_fallback_count",
        "disambiguation_fallback_count",
        "repaired_count",
        "fallback_count",
    ):
        totals[field] += summary[field]


def _summarize_finding(finding) -> dict[str, Any]:
    return {
        "entity_name": finding.entity_name,
        "status": _value(finding.status),
        "match_type": _value(finding.match_type),
        "match_score": finding.match_score,
        "risk_level": _value(finding.risk_level),
        "requires_human_review": finding.requires_human_review,
        "label_status": _value(finding.label_status),
    }


def _count_findings(report: CheckReport, status: FindingStatus) -> int:
    return sum(finding.status == status for finding in report.findings)


def _criteria_failures(
    criteria: dict[str, Any],
    summary: dict[str, Any],
    trace_summary: dict[str, Any] | None = None,
) -> list[str]:
    if not criteria:
        return ["no criteria provided"]

    trace_summary = trace_summary or empty_trace_summary()
    failures: list[str] = []
    for field in (
        "status",
        "findings_count",
        "confirmed_count",
        "probable_count",
        "uncertain_count",
        "rejected_count",
        "human_review_count",
        "resource_link_matches_count",
        "author_check_status",
        "deterministic_fuzzy_candidates",
        "fuzzy_enabled",
    ):
        if field in criteria and summary.get(field) != criteria[field]:
            failures.append(
                f"expected {field}={criteria[field]!r}, received {summary.get(field)!r}"
            )

    if "statuses" in criteria and summary.get("status") not in criteria["statuses"]:
        failures.append(
            f"expected status in {criteria['statuses']!r}, received {summary.get('status')!r}"
        )
    if (
        "min_disambiguation_calls" in criteria
        and trace_summary["disambiguation_calls"] < criteria["min_disambiguation_calls"]
    ):
        failures.append(
            "expected disambiguation_calls >= "
            f"{criteria['min_disambiguation_calls']!r}, "
            f"received {trace_summary['disambiguation_calls']!r}"
        )
    if criteria.get("requires_llm_disambiguation") and not _agentic_llm_success(
        trace_summary
    ):
        failures.append("expected clean LLM disambiguation without fallback")

    for expected_finding in criteria.get("must_have_findings", []):
        if not _has_matching_finding(summary["findings"], expected_finding):
            failures.append(f"missing expected finding {expected_finding!r}")

    for forbidden_finding in criteria.get("must_not_have_findings", []):
        if _has_matching_finding(summary["findings"], forbidden_finding):
            failures.append(f"found forbidden finding {forbidden_finding!r}")

    return failures


def _acceptable_failures(
    criteria: dict[str, Any],
    summary: dict[str, Any],
    trace_summary: dict[str, Any] | None = None,
) -> list[str]:
    if not criteria:
        return ["no acceptable fallback provided"]

    trace_summary = trace_summary or empty_trace_summary()
    failures = _criteria_failures(
        {
            key: value
            for key, value in criteria.items()
            if key
            in {
                "status",
                "statuses",
                "must_have_findings",
                "must_not_have_findings",
                "min_disambiguation_calls",
            }
        },
        summary,
        trace_summary,
    )
    if criteria.get("allow_uncertain_human_review") and not any(
        finding["status"] == "uncertain" and finding["requires_human_review"]
        for finding in summary["findings"]
    ):
        failures.append("expected at least one uncertain finding requiring human review")
    if "requires_human_review" in criteria:
        expected = criteria["requires_human_review"]
        actual = summary["human_review_count"] > 0
        if actual != expected:
            failures.append(
                f"expected requires_human_review={expected!r}, received {actual!r}"
            )
    for status in criteria.get("must_not_have_finding_statuses", []):
        if any(finding["status"] == status for finding in summary["findings"]):
            failures.append(f"found forbidden acceptable finding status {status!r}")
    return failures


def _dangerous_reasons(
    dangerous: dict[str, Any],
    case: dict[str, Any],
    summary: dict[str, Any],
    trace_summary: dict[str, Any] | None = None,
) -> list[str]:
    reasons: list[str] = []
    trace_summary = trace_summary or empty_trace_summary()
    if summary.get("status") in dangerous.get("forbid_statuses", []):
        reasons.append(f"dangerous report status {summary['status']!r}")

    for status in dangerous.get("forbid_finding_statuses_without_human_review", []):
        if any(
            finding["status"] == status and not finding["requires_human_review"]
            for finding in summary["findings"]
        ):
            reasons.append(f"dangerous {status!r} finding without human review")

    if dangerous.get("forbid_confirmed_without_expected_entity"):
        expected_entities = _expected_entities(case.get("expected", {}))
        for finding in summary["findings"]:
            if finding["status"] == "confirmed" and finding["entity_name"] not in expected_entities:
                reasons.append(
                    "dangerous confirmed finding for unexpected entity "
                    f"{finding['entity_name']!r}"
                )

    for required_entity in dangerous.get("required_entities", []):
        if not any(finding["entity_name"] == required_entity for finding in summary["findings"]):
            reasons.append(f"dangerous missing required entity {required_entity!r}")

    for forbidden_pair in dangerous.get("forbidden_entity_status_pairs", []):
        if _has_matching_finding(summary["findings"], forbidden_pair):
            reasons.append(f"dangerous forbidden entity/status pair {forbidden_pair!r}")
    if (
        "min_deterministic_fuzzy_candidates" in dangerous
        and summary["deterministic_fuzzy_candidates"]
        < dangerous["min_deterministic_fuzzy_candidates"]
    ):
        reasons.append(
            "dangerous fuzzy candidate count "
            f"{summary['deterministic_fuzzy_candidates']!r} below "
            f"{dangerous['min_deterministic_fuzzy_candidates']!r}"
        )
    if dangerous.get("forbid_llm_fallback") and _trace_indicates_fallback(trace_summary):
        reasons.append("dangerous LLM fallback observed")

    return reasons


def _expected_entities(expected: dict[str, Any]) -> set[str]:
    return {
        finding["entity_name"]
        for finding in expected.get("must_have_findings", [])
        if "entity_name" in finding
    }


def _has_matching_finding(
    findings: list[dict[str, Any]],
    expected: dict[str, Any],
) -> bool:
    return any(_finding_matches(finding, expected) for finding in findings)


def _finding_matches(finding: dict[str, Any], expected: dict[str, Any]) -> bool:
    return all(finding.get(field) == value for field, value in expected.items())


def _agentic_llm_success(trace_summary: dict[str, Any]) -> bool:
    return (
        trace_summary["action_selection_calls"] > 0
        and trace_summary["disambiguation_calls"] > 0
        and trace_summary["fallback_count"] == 0
    )


def _trace_indicates_fallback(trace_summary: dict[str, Any]) -> bool:
    return trace_summary["fallback_count"] > 0 or trace_summary["disambiguation_calls"] == 0


def _fallback_allowed(case: dict[str, Any]) -> bool:
    return bool(case.get("acceptable", {}).get("allow_fallback", False))


def _is_action_fallback(reason: str | None) -> bool:
    text = reason or ""
    return any(marker in text for marker in ACTION_FALLBACK_MARKERS)


def _is_disambiguation_fallback(rationale: str | None) -> bool:
    text = rationale or ""
    return any(marker in text for marker in DISAMBIGUATION_FALLBACK_MARKERS)


def _limitation_fallback_count(report: CheckReport) -> int:
    markers = ("Invalid review action", "exceeded the maximum step limit")
    return sum(
        any(marker in limitation for marker in markers)
        for limitation in report.limitations
    )


def _value(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    return value


def _first_reason(reasons: list[str]) -> str:
    return reasons[0] if reasons else "no details"


def _compact_summary(summary: dict[str, Any]) -> str:
    findings = [
        (
            f"{finding['entity_name']}:{finding['status']}:"
            f"{finding['match_type']}:review={finding['requires_human_review']}"
        )
        for finding in summary["findings"]
    ]
    return (
        f"status={summary['status']} findings={len(findings)} "
        f"human_review={summary['human_review_count']} "
        f"fuzzy={summary['deterministic_fuzzy_candidates']} "
        f"author={summary['author_check_status']} "
        f"links={summary['resource_link_matches_count']} "
        f"items={findings}"
    )


def _compact_trace(trace: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    parts: list[str] = []
    for event in trace:
        if event["event"] == "action_selected":
            fallback = " fallback" if event.get("fallback") else ""
            parts.append(
                "action="
                f"{event['action_type']}"
                f":window={event.get('context_window_size')}"
                f"{fallback}"
            )
        elif event["event"] == "action_repaired":
            parts.append(f"repair={event['from_action']}->{event['to_action']}")
        elif event["event"] == "context_requested":
            parts.append(f"context={event['window_size']}")
        elif event["event"] == "disambiguation_completed":
            fallback = " fallback" if event.get("fallback") else ""
            parts.append(
                "disambiguation="
                f"{event['decision']}:score={event['confidence_score']}"
                f"{fallback}"
            )
    return (
        f"actions={summary['action_selection_calls']} "
        f"disambiguations={summary['disambiguation_calls']} "
        f"repairs={summary['repaired_count']} "
        f"fallbacks={summary['fallback_count']} "
        f"events={parts}"
    )


if __name__ == "__main__":
    sys.exit(main())
