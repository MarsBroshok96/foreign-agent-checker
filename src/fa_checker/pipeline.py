"""Top-level deterministic pipeline entry point."""

from datetime import UTC, datetime

from fa_checker.domain.enums import ReportStatus
from fa_checker.domain.models import CheckReport

SCAFFOLD_LIMITATION = "Business logic is not implemented yet; this is a scaffold report."


def run_check(url: str) -> CheckReport:
    """Return a placeholder report while the real pipeline is still scaffolded."""
    return CheckReport(
        article_url=url,
        article_title=None,
        article_author=None,
        checked_at=datetime.now(UTC),
        registry_snapshot_date=None,
        status=ReportStatus.NO_MATCH,
        findings=[],
        limitations=[SCAFFOLD_LIMITATION],
    )

