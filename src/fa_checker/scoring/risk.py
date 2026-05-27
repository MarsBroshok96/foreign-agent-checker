"""Deterministic risk scoring placeholder."""

from fa_checker.domain.enums import RiskLevel
from fa_checker.domain.models import FinalFinding


def score_finding(finding: FinalFinding) -> RiskLevel:
    """Return the finding's current risk until scoring rules are implemented."""
    return finding.risk_level

