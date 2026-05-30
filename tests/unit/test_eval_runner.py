import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

from fa_checker.domain.enums import (
    ConfidenceLevel,
    EntityType,
    EvidenceSource,
    FindingStatus,
    LabelStatus,
    MatchType,
    ReportStatus,
    RiskLevel,
)
from fa_checker.domain.models import (
    CheckReport,
    EvidenceFragment,
    FinalFinding,
    ProcessingSummary,
)

RUN_EVAL_PATH = Path(__file__).resolve().parents[2] / "scripts" / "run_eval.py"
SPEC = importlib.util.spec_from_file_location("run_eval", RUN_EVAL_PATH)
assert SPEC is not None
run_eval = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(run_eval)


def make_finding(
    entity_name: str = "Варламов Илья Александрович",
    status: FindingStatus = FindingStatus.CONFIRMED,
    requires_human_review: bool = False,
    match_type: MatchType = MatchType.EXACT,
) -> FinalFinding:
    return FinalFinding(
        entity_name=entity_name,
        mention_text="Илья Варламов",
        match_type=match_type,
        match_score=1.0,
        status=status,
        risk_level=RiskLevel.LOW,
        confidence_level=ConfidenceLevel.HIGH,
        label_status=LabelStatus.PRESENT,
        requires_human_review=requires_human_review,
        evidence=[
            EvidenceFragment(
                source=EvidenceSource.ARTICLE_TEXT,
                text="Илья Варламов, признан иностранным агентом",
            )
        ],
        rationale="Test rationale.",
    )


def make_report(findings: list[FinalFinding] | None = None) -> CheckReport:
    return CheckReport(
        article_url="https://news.rambler.ru/eval/test",
        checked_at=datetime(2026, 5, 30, tzinfo=UTC),
        status=ReportStatus.CONFIRMED_MATCH_FOUND,
        findings=findings or [make_finding()],
        processing_summary=ProcessingSummary(
            mode="deterministic",
            deterministic_candidates_total=1,
            deterministic_strong_candidates=1,
            deterministic_fuzzy_candidates=0,
            fuzzy_enabled=False,
            final_findings_total=1,
            final_confirmed_findings=1,
        ),
    )


def test_build_article_creates_article() -> None:
    article = run_eval.build_article(
        {
            "url": "https://news.rambler.ru/eval/test",
            "source_domain": "news.rambler.ru",
            "text": "Текст.",
            "links": [],
        }
    )

    assert article.url == "https://news.rambler.ru/eval/test"
    assert article.text == "Текст."


def test_build_registry_entries_creates_entries_with_entity_type() -> None:
    entries = run_eval.build_registry_entries(
        [
            {
                "registry_id": "1",
                "full_name": "Варламов Илья Александрович",
                "entity_type": "person",
                "aliases": [],
                "raw_fields": {},
            }
        ]
    )

    assert entries[0].entity_type == EntityType.PERSON
    assert entries[0].normalized_name == "варламов илья александрович"


def test_summarize_report_returns_counts() -> None:
    summary = run_eval.summarize_report(make_report())

    assert summary["status"] == "confirmed_match_found"
    assert summary["confirmed_count"] == 1
    assert summary["human_review_count"] == 0
    assert summary["findings"][0]["match_type"] == "exact"


def test_evaluate_case_result_passes_when_expected_matches() -> None:
    result, reasons = run_eval.evaluate_case_result(
        {
            "expected": {
                "status": "confirmed_match_found",
                "confirmed_count": 1,
                "must_have_findings": [
                    {
                        "entity_name": "Варламов Илья Александрович",
                        "status": "confirmed",
                    }
                ],
            }
        },
        make_report(),
    )

    assert result == run_eval.RESULT_PASS
    assert reasons


def test_evaluate_case_result_returns_acceptable() -> None:
    result, reasons = run_eval.evaluate_case_result(
        {
            "expected": {"status": "no_match"},
            "acceptable": {
                "statuses": ["confirmed_match_found"],
                "must_have_findings": [
                    {
                        "entity_name": "Варламов Илья Александрович",
                        "status": "confirmed",
                    }
                ],
            },
        },
        make_report(),
    )

    assert result == run_eval.RESULT_ACCEPTABLE
    assert reasons


def test_evaluate_case_result_returns_dangerous_fail() -> None:
    result, reasons = run_eval.evaluate_case_result(
        {
            "expected": {"status": "confirmed_match_found"},
            "dangerous": {"forbid_statuses": ["confirmed_match_found"]},
        },
        make_report(),
    )

    assert result == run_eval.RESULT_DANGEROUS_FAIL
    assert "dangerous" in reasons[0]


def test_evaluate_case_result_returns_fail() -> None:
    result, reasons = run_eval.evaluate_case_result(
        {
            "expected": {"status": "no_match"},
            "acceptable": {"statuses": ["potential_match_found"]},
        },
        make_report(),
    )

    assert result == run_eval.RESULT_FAIL
    assert reasons


def test_load_eval_file_loads_json(tmp_path) -> None:
    path = tmp_path / "eval.json"
    path.write_text(json.dumps({"version": 1, "cases": []}), encoding="utf-8")

    data = run_eval.load_eval_file(path)

    assert data["version"] == 1
