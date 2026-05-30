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
RESULT_ACCEPTABLE = "ACCEPTABLE"
RESULT_FAIL = "FAIL"
RESULT_DANGEROUS_FAIL = "DANGEROUS_FAIL"
RESULT_SKIPPED = "SKIPPED"


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
) -> tuple[str, list[str]]:
    summary = (
        summarize_report(report_or_summary)
        if isinstance(report_or_summary, CheckReport)
        else report_or_summary
    )
    dangerous_reasons = _dangerous_reasons(case.get("dangerous", {}), case, summary)
    if dangerous_reasons:
        return RESULT_DANGEROUS_FAIL, dangerous_reasons

    expected_reasons = _criteria_failures(case.get("expected", {}), summary)
    if not expected_reasons:
        return RESULT_PASS, ["expected checks passed"]

    acceptable_reasons = _acceptable_failures(case.get("acceptable", {}), summary)
    if not acceptable_reasons:
        return RESULT_ACCEPTABLE, ["acceptable fallback passed", *expected_reasons]

    return RESULT_FAIL, [*expected_reasons, *acceptable_reasons]


def run_case(case: dict[str, Any]) -> CheckReport:
    article = build_article(case["article"])
    registry_entries = build_registry_entries(case.get("registry_entries", []))
    context_profiles = build_context_profiles(case.get("context_profiles", []))
    enable_fuzzy = bool(case.get("enable_fuzzy", False))
    if case.get("mode") == "agentic":
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
    args = parser.parse_args(argv)

    eval_data = load_eval_file(args.eval_file)
    cases = _filtered_cases(eval_data.get("cases", []), args.mode)
    counts = {
        RESULT_PASS: 0,
        RESULT_ACCEPTABLE: 0,
        RESULT_FAIL: 0,
        RESULT_DANGEROUS_FAIL: 0,
        RESULT_SKIPPED: 0,
    }

    for case in cases:
        case_id = case.get("id", "<missing-id>")
        if args.skip_agentic and case.get("mode") == "agentic":
            counts[RESULT_SKIPPED] += 1
            print(f"{RESULT_SKIPPED} {case_id}: agentic case skipped")
            continue
        try:
            report = run_case(case)
            result, reasons = evaluate_case_result(case, report)
            summary = summarize_report(report)
        except Exception as exc:  # noqa: BLE001 - eval should continue across cases.
            result = RESULT_FAIL
            reasons = [f"case raised {type(exc).__name__}: {exc}"]
            summary = {}

        counts[result] += 1
        print(f"{result} {case_id}: {_first_reason(reasons)}")
        if args.verbose and summary:
            print(f"  summary: {_compact_summary(summary)}")
        if result in {RESULT_FAIL, RESULT_DANGEROUS_FAIL}:
            for reason in reasons[1:]:
                print(f"  - {reason}")

    total = sum(counts.values())
    print(
        "Summary: "
        f"total={total} pass={counts[RESULT_PASS]} "
        f"acceptable={counts[RESULT_ACCEPTABLE]} fail={counts[RESULT_FAIL]} "
        f"dangerous={counts[RESULT_DANGEROUS_FAIL]} skipped={counts[RESULT_SKIPPED]}"
    )
    return 1 if counts[RESULT_FAIL] or counts[RESULT_DANGEROUS_FAIL] else 0


def _filtered_cases(cases: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    if mode == "all":
        return cases
    return [case for case in cases if case.get("mode") == mode]


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


def _criteria_failures(criteria: dict[str, Any], summary: dict[str, Any]) -> list[str]:
    if not criteria:
        return ["no criteria provided"]

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

    for expected_finding in criteria.get("must_have_findings", []):
        if not _has_matching_finding(summary["findings"], expected_finding):
            failures.append(f"missing expected finding {expected_finding!r}")

    for forbidden_finding in criteria.get("must_not_have_findings", []):
        if _has_matching_finding(summary["findings"], forbidden_finding):
            failures.append(f"found forbidden finding {forbidden_finding!r}")

    return failures


def _acceptable_failures(criteria: dict[str, Any], summary: dict[str, Any]) -> list[str]:
    if not criteria:
        return ["no acceptable fallback provided"]

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
            }
        },
        summary,
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
) -> list[str]:
    reasons: list[str] = []
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


if __name__ == "__main__":
    sys.exit(main())
