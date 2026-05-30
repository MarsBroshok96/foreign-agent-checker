import json
from datetime import UTC, date, datetime

from fa_checker.domain.enums import (
    ConfidenceLevel,
    EvidenceSource,
    FindingStatus,
    LabelStatus,
    ReportStatus,
    RiskLevel,
)
from fa_checker.domain.models import (
    CheckReport,
    EvidenceFragment,
    FinalFinding,
    ProcessingSummary,
)
from fa_checker.reporting.json_report import report_to_dict, report_to_json


def make_report() -> CheckReport:
    return CheckReport(
        article_url="https://www.rambler.ru/example",
        article_title="Статья о проверке",
        article_author="Редакция",
        checked_at=datetime(2026, 5, 28, 12, 30, tzinfo=UTC),
        registry_snapshot_date=date(2026, 5, 22),
        status=ReportStatus.CONFIRMED_MATCH_FOUND,
        findings=[
            FinalFinding(
                entity_name="Варламов Илья Александрович",
                mention_text="Илья Варламов",
                status=FindingStatus.CONFIRMED,
                risk_level=RiskLevel.LOW,
                confidence_level=ConfidenceLevel.HIGH,
                label_status=LabelStatus.PRESENT,
                requires_human_review=False,
                evidence=[
                    EvidenceFragment(
                        source=EvidenceSource.ARTICLE_TEXT,
                        text="Илья Варламов, признан иностранным агентом",
                        start=0,
                        end=42,
                    )
                ],
                rationale="Strong exact registry match and nearby foreign-agent label found.",
            )
        ],
        limitations=["Offline deterministic check only."],
        processing_summary=ProcessingSummary(
            mode="deterministic",
            deterministic_candidates_total=1,
            deterministic_strong_candidates=1,
            final_findings_total=1,
            final_confirmed_findings=1,
        ),
    )


def test_report_to_dict_returns_json_serializable_dict() -> None:
    result = report_to_dict(make_report())

    assert isinstance(result, dict)
    assert result["status"] == "confirmed_match_found"
    assert result["findings"][0]["risk_level"] == "low"


def test_report_to_json_returns_valid_json() -> None:
    result = report_to_json(make_report())

    parsed = json.loads(result)
    assert parsed["article_url"] == "https://www.rambler.ru/example"


def test_report_to_json_serializes_dates_as_strings() -> None:
    parsed = json.loads(report_to_json(make_report()))

    assert parsed["checked_at"] == "2026-05-28T12:30:00Z"
    assert parsed["registry_snapshot_date"] == "2026-05-22"


def test_report_to_json_preserves_non_ascii_text() -> None:
    result = report_to_json(make_report())

    assert "Варламов Илья Александрович" in result
    assert "\\u0412" not in result


def test_report_to_json_includes_findings() -> None:
    parsed = json.loads(report_to_json(make_report()))

    assert len(parsed["findings"]) == 1
    assert parsed["findings"][0]["evidence"][0]["source"] == "article_text"


def test_report_to_json_includes_processing_summary() -> None:
    parsed = json.loads(report_to_json(make_report()))

    assert parsed["processing_summary"]["mode"] == "deterministic"
    assert parsed["processing_summary"]["deterministic_candidates_total"] == 1


def test_report_to_json_preserves_raw_duplicate_findings_and_review_rationale() -> None:
    report = make_report()
    duplicate = report.findings[0].model_copy(
        update={
            "review_rationale": "Context refers to the White House, not the person.",
        }
    )
    report = report.model_copy(update={"findings": [report.findings[0], duplicate]})

    parsed = json.loads(report_to_json(report))

    assert len(parsed["findings"]) == 2
    assert (
        parsed["findings"][1]["review_rationale"]
        == "Context refers to the White House, not the person."
    )
