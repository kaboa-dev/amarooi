"""Unit tests for Phase 9: Dynamic Domain Adaptation (domain.py)."""

from __future__ import annotations

import pytest

from amarooi.core.domain import DomainAdapter, DomainInferenceResult, _tokenize


class TestTokenize:
    def test_lowercases(self) -> None:
        assert _tokenize("Hello WORLD") == ["hello", "world"]

    def test_strips_punctuation(self) -> None:
        assert _tokenize("auth, jwt!") == ["auth", "jwt"]

    def test_empty_string(self) -> None:
        assert _tokenize("") == []


class TestDomainAdapter:
    def setup_method(self) -> None:
        self.adapter = DomainAdapter()

    # ------------------------------------------------------------------
    # Web / API domain
    # ------------------------------------------------------------------

    def test_infers_web_api_from_rest_jwt_prompt(self) -> None:
        prompt = (
            "Build a REST API with JWT authentication and a Postgres SQL database. "
            "Expose endpoints for user login, token refresh, and resource CRUD."
        )
        result = self.adapter.infer(prompt)
        assert result.domain == "web_api"

    def test_web_api_compounds_present(self) -> None:
        result = self.adapter.infer(
            "Create a backend web server with REST endpoints, ORM schema, and session tokens."
        )
        assert result.domain == "web_api"
        assert len(result.compounds) > 0
        assert any("Auth" in c or "SQL" in c or "REST" in c for c in result.compounds)

    # ------------------------------------------------------------------
    # Trading domain
    # ------------------------------------------------------------------

    def test_infers_trading_from_order_execution_prompt(self) -> None:
        prompt = (
            "Design an algorithmic trading system that ingests market data via "
            "WebSocket, routes orders to a broker API, and enforces risk limits "
            "with a circuit breaker."
        )
        result = self.adapter.infer(prompt)
        assert result.domain == "trading"

    def test_trading_compounds_include_circuit_breaker(self) -> None:
        result = self.adapter.infer(
            "Trading engine with order execution, position management, and circuit breakers."
        )
        assert result.domain == "trading"
        assert any("Circuit" in c or "Risk" in c or "Order" in c for c in result.compounds)

    # ------------------------------------------------------------------
    # Compiler domain
    # ------------------------------------------------------------------

    def test_infers_compiler_from_ast_prompt(self) -> None:
        prompt = (
            "Write a compiler that tokenizes source code, builds an AST, and emits "
            "bytecode via a code generator."
        )
        result = self.adapter.infer(prompt)
        assert result.domain == "compiler"

    def test_compiler_compounds_include_tokenizer(self) -> None:
        result = self.adapter.infer(
            "Transpiler: lexer, parser, AST visitor, and code generator."
        )
        assert result.domain == "compiler"
        assert any("Tokenizer" in c or "AST" in c or "Code" in c for c in result.compounds)

    # ------------------------------------------------------------------
    # Game engine domain
    # ------------------------------------------------------------------

    def test_infers_game_from_entity_prompt(self) -> None:
        prompt = (
            "Build a 2D game with entities, a frame delta loop, collision detection, "
            "and player input handling."
        )
        result = self.adapter.infer(prompt)
        assert result.domain == "game"

    # ------------------------------------------------------------------
    # Networking domain
    # ------------------------------------------------------------------

    def test_infers_networking_from_microservice_prompt(self) -> None:
        prompt = (
            "Design a microservice mesh with gRPC, rate limiting, retry backoff, "
            "and protobuf serialization."
        )
        result = self.adapter.infer(prompt)
        assert result.domain == "networking"

    def test_networking_compounds_include_retry(self) -> None:
        result = self.adapter.infer(
            "Microservice with rate limiter, retry logic, and RPC protocol."
        )
        assert result.domain == "networking"
        assert any("Retry" in c or "Rate" in c or "RPC" in c for c in result.compounds)

    # ------------------------------------------------------------------
    # Fallback behaviour
    # ------------------------------------------------------------------

    def test_fallback_on_empty_prompt_returns_result(self) -> None:
        result = self.adapter.infer("")
        assert isinstance(result, DomainInferenceResult)
        assert result.domain in self.adapter.list_domains()

    def test_low_signal_prompt_still_returns_result(self) -> None:
        result = self.adapter.infer("Build me a thing.")
        assert isinstance(result, DomainInferenceResult)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def test_list_domains_returns_all_five(self) -> None:
        domains = self.adapter.list_domains()
        assert set(domains) == {"web_api", "trading", "compiler", "game", "networking"}

    def test_compounds_for_known_domain(self) -> None:
        compounds = self.adapter.compounds_for("trading")
        assert isinstance(compounds, list)
        assert len(compounds) > 0

    def test_compounds_for_unknown_domain_raises(self) -> None:
        with pytest.raises(KeyError):
            self.adapter.compounds_for("unknown_domain_xyz")

    def test_confidence_is_float_in_range(self) -> None:
        result = self.adapter.infer(
            "Build a REST API with JWT auth, SQL database, and GraphQL endpoint."
        )
        assert 0.0 <= result.confidence <= 1.0

    def test_prompt_tokens_populated(self) -> None:
        result = self.adapter.infer("REST API with auth")
        assert len(result.prompt_tokens) > 0

    def test_compounds_is_copy(self) -> None:
        """Mutating the returned compounds list must not affect internal state."""
        result = self.adapter.infer("REST API with auth")
        original_len = len(result.compounds)
        result.compounds.append("EXTRA")
        # Re-infer to check internal state is unchanged
        result2 = self.adapter.infer("REST API with auth")
        assert len(result2.compounds) == original_len
