"""Foreign-agent label checking placeholder."""

from fa_checker.domain.enums import LabelQuality
from fa_checker.domain.models import LabelCheckResult


def check_label_near_mention(text: str, mention_start: int, mention_end: int) -> LabelCheckResult:
    return LabelCheckResult(
        label_found=False,
        label_fragment=None,
        label_distance=None,
        label_quality=LabelQuality.ABSENT,
    )

