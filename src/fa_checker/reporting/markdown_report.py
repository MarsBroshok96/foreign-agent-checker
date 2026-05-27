"""Markdown report rendering placeholder."""

from fa_checker.domain.models import CheckReport


def render_markdown_report(report: CheckReport) -> str:
    lines = [
        "# Foreign Agent Checker Report",
        "",
        f"- Article URL: {report.article_url}",
        f"- Status: {report.status.value}",
    ]
    if report.limitations:
        lines.append("")
        lines.append("## Limitations")
        lines.extend(f"- {limitation}" for limitation in report.limitations)
    return "\n".join(lines)

