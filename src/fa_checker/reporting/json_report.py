"""Machine-readable JSON report rendering."""

import json
from typing import Any

from fa_checker.domain.models import CheckReport


def report_to_dict(report: CheckReport) -> dict[str, Any]:
    """Convert a report to a JSON-serializable dictionary."""
    return report.model_dump(mode="json")


def report_to_json(report: CheckReport, indent: int = 2) -> str:
    """Render a report as deterministic UTF-8 friendly JSON."""
    return json.dumps(report_to_dict(report), ensure_ascii=False, indent=indent)


def render_json_report(report: CheckReport) -> str:
    return report_to_json(report)
