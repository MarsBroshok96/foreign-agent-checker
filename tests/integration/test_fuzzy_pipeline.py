from fa_checker.agent import orchestrator
from fa_checker.domain.enums import DisambiguationDecision, EntityType, FindingStatus, ReportStatus
from fa_checker.domain.models import Article, DisambiguationResult, RegistryEntry
from fa_checker.pipeline import run_agentic_review_check, run_offline_check


def make_article(text: str) -> Article:
    return Article(
        url="https://www.rambler.ru/example",
        source_domain="www.rambler.ru",
        text=text,
    )


def make_entry(full_name: str) -> RegistryEntry:
    return RegistryEntry(
        registry_id=full_name,
        full_name=full_name,
        entity_type=EntityType.PERSON,
        normalized_name=full_name.lower(),
        registry_source_url="https://minjust.gov.ru/registry",
    )


def test_run_offline_check_fuzzy_disabled_by_default() -> None:
    report = run_offline_check(
        make_article("Слова Варламова вызвали дискуссию."),
        [make_entry("Варламов Илья Александрович")],
    )

    assert report.status == ReportStatus.NO_MATCH
    assert report.findings == []
    assert report.processing_summary is not None
    assert report.processing_summary.fuzzy_enabled is False
    assert report.processing_summary.deterministic_fuzzy_candidates == 0


def test_run_offline_check_fuzzy_enabled_adds_weak_candidate() -> None:
    report = run_offline_check(
        make_article("Слова Варламова вызвали дискуссию."),
        [make_entry("Варламов Илья Александрович")],
        enable_fuzzy=True,
    )

    assert report.status == ReportStatus.POTENTIAL_MATCH_FOUND
    assert len(report.findings) == 1
    assert report.findings[0].status == FindingStatus.UNCERTAIN
    assert report.findings[0].match_type == "fuzzy"
    assert report.findings[0].requires_human_review is True
    assert report.processing_summary is not None
    assert report.processing_summary.fuzzy_enabled is True
    assert report.processing_summary.deterministic_fuzzy_candidates == 1


def test_run_agentic_review_check_reviews_fuzzy_candidate(monkeypatch) -> None:
    calls = []

    def fake_choose_review_action_with_llm(*args, **kwargs):
        calls.append(kwargs["candidate"].match_type)
        if len(calls) == 1:
            from fa_checker.agent.schemas import AgentReviewAction

            return AgentReviewAction(
                action_type="request_context",
                candidate_index=0,
                context_window_size="small",
                reason="Need context.",
            )
        from fa_checker.agent.schemas import AgentReviewAction

        return AgentReviewAction(
            action_type="disambiguate_candidate",
            candidate_index=0,
            reason="Context is enough.",
        )

    def fake_disambiguate_candidate(*args, **kwargs):
        return DisambiguationResult(
            decision=DisambiguationDecision.LIKELY_SAME_ENTITY,
            confidence_score=0.8,
            requires_human_review=True,
            rationale="Похожий контекст, требуется ручная проверка.",
        )

    monkeypatch.setattr(
        orchestrator,
        "choose_review_action_with_llm",
        fake_choose_review_action_with_llm,
    )
    monkeypatch.setattr(orchestrator, "disambiguate_candidate", fake_disambiguate_candidate)

    report = run_agentic_review_check(
        make_article("Слова Варламова вызвали дискуссию."),
        [make_entry("Варламов Илья Александрович")],
        enable_fuzzy=True,
    )

    assert calls == ["fuzzy", "fuzzy"]
    assert report.status == ReportStatus.POTENTIAL_MATCH_FOUND
    assert report.findings[0].status == FindingStatus.PROBABLE
    limitations = " ".join(report.limitations)
    assert "person-only fuzzy recall enabled" in limitations
    assert "No fuzzy search" not in limitations
    assert "No person-only fuzzy recall" not in limitations
