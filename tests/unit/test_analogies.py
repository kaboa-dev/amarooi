"""Unit tests for Phase 9: Analogy Translator & Trade-Off Cards (analogies.py)."""

from __future__ import annotations

import pytest

from amarooi.core.analogies import AnalogyEntry, AnalogyTranslator, TradeOffCard


class TestAnalogyEntry:
    def test_fields_accessible(self) -> None:
        entry = AnalogyEntry(
            term="invariant",
            icon="🚪",
            name="The Vault Door",
            analogy="A rule that can never be broken.",
        )
        assert entry.term == "invariant"
        assert entry.icon == "🚪"
        assert entry.name == "The Vault Door"


class TestTradeOffCard:
    def test_fields_accessible(self) -> None:
        card = TradeOffCard(
            decision="async_sql_pool",
            description="Use async SQL.",
            gains=["High concurrency"],
            costs=["Harder to debug"],
        )
        assert card.decision == "async_sql_pool"
        assert "High concurrency" in card.gains
        assert "Harder to debug" in card.costs

    def test_default_empty_lists(self) -> None:
        card = TradeOffCard(decision="x", description="y")
        assert card.gains == []
        assert card.costs == []


class TestAnalogyTranslator:
    def setup_method(self) -> None:
        self.translator = AnalogyTranslator()

    # ------------------------------------------------------------------
    # translate – exact terms
    # ------------------------------------------------------------------

    def test_translate_invariant(self) -> None:
        entry = self.translator.translate("invariant")
        assert entry is not None
        assert entry.icon == "🚪"
        assert "Vault Door" in entry.name

    def test_translate_state_register(self) -> None:
        entry = self.translator.translate("state_register")
        assert entry is not None
        assert "Scoreboard" in entry.name

    def test_translate_degradation_mode(self) -> None:
        entry = self.translator.translate("degradation_mode")
        assert entry is not None
        assert "Generator" in entry.name or "Backup" in entry.name

    def test_translate_interface_contract(self) -> None:
        entry = self.translator.translate("interface_contract")
        assert entry is not None
        assert "Wall Plug" in entry.name

    # ------------------------------------------------------------------
    # translate – partial / alias keys
    # ------------------------------------------------------------------

    def test_translate_alias_register(self) -> None:
        entry = self.translator.translate("register")
        assert entry is not None
        assert entry.term == "state_register"

    def test_translate_alias_circuit(self) -> None:
        entry = self.translator.translate("circuit")
        assert entry is not None
        assert entry.term == "circuit_breaker"

    def test_translate_alias_cache(self) -> None:
        entry = self.translator.translate("cache")
        assert entry is not None
        assert entry.term == "caching"

    def test_translate_case_insensitive(self) -> None:
        entry = self.translator.translate("INVARIANT")
        assert entry is not None
        assert entry.term == "invariant"

    def test_translate_unknown_returns_none(self) -> None:
        assert self.translator.translate("nonexistent_xyz_term") is None

    # ------------------------------------------------------------------
    # translate_all
    # ------------------------------------------------------------------

    def test_translate_all_known_terms(self) -> None:
        entries = self.translator.translate_all(["invariant", "state_register", "caching"])
        assert len(entries) == 3

    def test_translate_all_skips_unknown(self) -> None:
        entries = self.translator.translate_all(["invariant", "unknown_xyz", "caching"])
        assert len(entries) == 2

    def test_translate_all_empty(self) -> None:
        assert self.translator.translate_all([]) == []

    # ------------------------------------------------------------------
    # list_terms
    # ------------------------------------------------------------------

    def test_list_terms_returns_canonical_keys(self) -> None:
        terms = self.translator.list_terms()
        assert "invariant" in terms
        assert "state_register" in terms
        assert "circuit_breaker" in terms
        assert len(terms) >= 5

    # ------------------------------------------------------------------
    # trade_off_cards_for – exact match
    # ------------------------------------------------------------------

    def test_trade_off_card_async_sql_pool(self) -> None:
        cards = self.translator.trade_off_cards_for("async_sql_pool")
        assert len(cards) == 1
        card = cards[0]
        assert len(card.gains) > 0
        assert len(card.costs) > 0

    def test_trade_off_card_redis_cache(self) -> None:
        cards = self.translator.trade_off_cards_for("redis_cache_vs_db")
        assert len(cards) == 1
        assert len(cards[0].gains) > 0
        assert len(cards[0].costs) > 0

    def test_trade_off_card_eventual_consistency(self) -> None:
        cards = self.translator.trade_off_cards_for("eventual_consistency_vs_acid")
        assert len(cards) == 1
        gains_text = " ".join(cards[0].gains)
        assert "partition" in gains_text.lower() or "availability" in gains_text.lower()

    def test_trade_off_card_jwt(self) -> None:
        cards = self.translator.trade_off_cards_for("jwt_stateless_vs_session_store")
        assert len(cards) == 1

    # ------------------------------------------------------------------
    # trade_off_cards_for – partial match
    # ------------------------------------------------------------------

    def test_partial_match_returns_cards(self) -> None:
        cards = self.translator.trade_off_cards_for("redis")
        assert len(cards) >= 1

    def test_unknown_decision_returns_empty(self) -> None:
        cards = self.translator.trade_off_cards_for("nonexistent_decision_xyz")
        assert cards == []

    # ------------------------------------------------------------------
    # all_trade_off_cards
    # ------------------------------------------------------------------

    def test_all_trade_off_cards_returns_list(self) -> None:
        all_cards = self.translator.all_trade_off_cards()
        assert len(all_cards) >= 4
        assert all(isinstance(c, TradeOffCard) for c in all_cards)
