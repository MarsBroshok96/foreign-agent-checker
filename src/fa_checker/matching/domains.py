"""Domain and link matching placeholder."""

from fa_checker.domain.models import Article, CandidateMatch, ContextProfile


def check_link_domains(article: Article, profiles: list[ContextProfile]) -> list[CandidateMatch]:
    raise NotImplementedError("Domain checking is not implemented in the scaffold phase.")

