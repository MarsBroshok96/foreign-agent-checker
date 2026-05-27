"""JSON report rendering placeholder."""

from fa_checker.domain.models import CheckReport


def render_json_report(report: CheckReport) -> str:
    return report.model_dump_json(indent=2)

