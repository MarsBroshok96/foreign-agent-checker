"""Top-level deterministic pipeline entry point."""

from datetime import UTC, date, datetime

from fa_checker.domain.enums import FindingStatus, ReportStatus
from fa_checker.domain.models import Article, CheckReport, FinalFinding, RegistryEntry
from fa_checker.matching.exact import find_exact_matches
from fa_checker.matching.labels import check_label
from fa_checker.scoring.risk import ScoringInput, score_candidate_matches

SCAFFOLD_LIMITATION = "Business logic is not implemented yet; this is a scaffold report."
OFFLINE_LIMITATION = (
    "Offline deterministic check only; fuzzy matching, LLM disambiguation, "
    "and agentic recall pass are not applied."
)


def run_offline_check(article: Article, registry_entries: list[RegistryEntry]) -> CheckReport:
    """Run deterministic offline matching, label checking, and scoring."""
    matches = find_exact_matches(article, registry_entries)
    scoring_inputs = [
        ScoringInput(
            match=match,
            label_result=check_label(article, match),
            disambiguation=None,
        )
        for match in matches
    ]
    findings = score_candidate_matches(scoring_inputs)

    return CheckReport(
        article_url=article.url,
        article_title=article.title,
        article_author=article.author,
        checked_at=datetime.now(UTC),
        registry_snapshot_date=_get_registry_snapshot_date(registry_entries),
        status=_derive_report_status(findings),
        findings=findings,
        limitations=[OFFLINE_LIMITATION],
    )


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


def _derive_report_status(findings: list[FinalFinding]) -> ReportStatus:
    if not findings:
        return ReportStatus.NO_MATCH
    if any(finding.status == FindingStatus.CONFIRMED for finding in findings):
        return ReportStatus.CONFIRMED_MATCH_FOUND
    if any(
        finding.status in {FindingStatus.PROBABLE, FindingStatus.UNCERTAIN}
        for finding in findings
    ):
        return ReportStatus.POTENTIAL_MATCH_FOUND
    return ReportStatus.NO_MATCH


def _get_registry_snapshot_date(registry_entries: list[RegistryEntry]) -> date | None:
    for entry in registry_entries:
        if entry.registry_snapshot_date is not None:
            return entry.registry_snapshot_date
    return None
