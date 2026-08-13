"""Unit tests for Phase 9: Verified Knowledge Retrieval (search.py)."""

from __future__ import annotations

import pytest

from amarooi.core.search import KnowledgeEngine, KnowledgeEntry, _tokenize


class TestKnowledgeEntry:
    def test_default_verified_true(self) -> None:
        entry = KnowledgeEntry(
            title="Test", summary="Summary", source="Test Source"
        )
        assert entry.verified is True

    def test_tags_default_empty(self) -> None:
        entry = KnowledgeEntry(title="T", summary="S", source="Src")
        assert entry.tags == []


class TestKnowledgeEngine:
    def setup_method(self) -> None:
        self.engine = KnowledgeEngine()

    # ------------------------------------------------------------------
    # Basic retrieval
    # ------------------------------------------------------------------

    def test_query_returns_list(self) -> None:
        results = self.engine.query("JWT authentication")
        assert isinstance(results, list)

    def test_query_jwt_returns_jwt_entry(self) -> None:
        results = self.engine.query("JWT authentication token")
        assert len(results) > 0
        titles = [r.title for r in results]
        assert any("JWT" in t or "Token" in t for t in titles)

    def test_query_circuit_breaker_returns_relevant_entry(self) -> None:
        results = self.engine.query("circuit breaker pattern trading")
        titles = [r.title for r in results]
        assert any("circuit" in t.lower() or "breaker" in t.lower() for t in titles)

    def test_query_ast_parser_returns_compiler_entry(self) -> None:
        results = self.engine.query("AST parser recursive descent")
        assert len(results) > 0

    def test_query_rate_limiting_returns_rate_entry(self) -> None:
        results = self.engine.query("rate limiting algorithm token bucket")
        assert len(results) > 0
        assert any("rate" in r.title.lower() or "rate" in str(r.tags) for r in results)

    # ------------------------------------------------------------------
    # max_results
    # ------------------------------------------------------------------

    def test_max_results_respected(self) -> None:
        results = self.engine.query("api web auth sql endpoint", max_results=2)
        assert len(results) <= 2

    def test_max_results_default_is_five(self) -> None:
        results = self.engine.query("api auth jwt sql orm rest graphql")
        assert len(results) <= 5

    # ------------------------------------------------------------------
    # verified_only filtering
    # ------------------------------------------------------------------

    def test_verified_only_true_filters_unverified(self) -> None:
        engine = KnowledgeEngine(verified_only=True)
        results = engine.query("auth")
        assert all(r.verified for r in results)

    def test_verified_only_false_allows_all(self) -> None:
        engine = KnowledgeEngine(verified_only=False)
        results = engine.query("auth")
        assert isinstance(results, list)

    # ------------------------------------------------------------------
    # query_for_domain
    # ------------------------------------------------------------------

    def test_query_for_domain_web_api(self) -> None:
        results = self.engine.query_for_domain("web_api")
        assert len(results) > 0
        assert all("web_api" in r.tags for r in results)

    def test_query_for_domain_trading(self) -> None:
        results = self.engine.query_for_domain("trading")
        assert len(results) > 0
        assert all("trading" in r.tags for r in results)

    def test_query_for_domain_compiler(self) -> None:
        results = self.engine.query_for_domain("compiler")
        assert len(results) > 0

    def test_query_for_domain_networking(self) -> None:
        results = self.engine.query_for_domain("networking")
        assert len(results) > 0

    def test_query_for_domain_unknown_returns_empty(self) -> None:
        results = self.engine.query_for_domain("completely_unknown_xyz")
        assert results == []

    def test_query_for_domain_max_results(self) -> None:
        results = self.engine.query_for_domain("web_api", max_results=1)
        assert len(results) <= 1

    # ------------------------------------------------------------------
    # Empty / edge-case queries
    # ------------------------------------------------------------------

    def test_empty_query_returns_list(self) -> None:
        results = self.engine.query("")
        assert isinstance(results, list)

    def test_query_no_match_returns_empty(self) -> None:
        results = self.engine.query("xyzzy_nonexistent_term_12345")
        assert results == []
