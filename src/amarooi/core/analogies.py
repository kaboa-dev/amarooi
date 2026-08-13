"""Analogy-Driven Jargon Translator & Trade-Off Cards.

Bridges the gap between senior engineers and non-technical stakeholders by
providing plain-English analogies for formal software terms and interactive
trade-off cards for common architectural decisions.

Example::

    from amarooi.core.analogies import AnalogyTranslator, TradeOffCard
    translator = AnalogyTranslator()

    # Translate a single term
    entry = translator.translate("invariant")
    print(entry.analogy)  # 🚪 The Vault Door

    # Generate trade-off cards for a decision
    cards = translator.trade_off_cards_for("async_sql_pool")
    for card in cards:
        print(card.decision, card.gains, card.costs)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class AnalogyEntry:
    """Plain-English analogy for a formal software concept.

    Attributes:
        term: The formal software term (lower-case normalised, e.g.
            ``'invariant'``).
        icon: Emoji visual shorthand for the concept.
        name: Short descriptive label (e.g. ``'The Vault Door'``).
        analogy: One-sentence plain-English description of what the term means
            in a real-world context.
    """

    term: str
    icon: str
    name: str
    analogy: str


@dataclass
class TradeOffCard:
    """Explicit trade-off card for an architectural decision.

    Attributes:
        decision: Short label identifying the architectural choice.
        description: One-sentence summary of what the decision involves.
        gains: List of concrete benefits gained by making this choice.
        costs: List of concrete costs or risks incurred by this choice.
    """

    decision: str
    description: str
    gains: list[str] = field(default_factory=list)
    costs: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Built-in analogy dictionary
# ---------------------------------------------------------------------------

_ANALOGIES: list[AnalogyEntry] = [
    AnalogyEntry(
        term="invariant",
        icon="🚪",
        name="The Vault Door",
        analogy=(
            "A rule that can never be broken; if cash isn't locked in, "
            "the door refuses to shut."
        ),
    ),
    AnalogyEntry(
        term="state_register",
        icon="📋",
        name="The Scoreboard",
        analogy=(
            "Memory holding critical variables like balances or scores "
            "across rounds."
        ),
    ),
    AnalogyEntry(
        term="degradation_mode",
        icon="⚡",
        name="The Backup Generator",
        analogy=(
            "Emergency fallback logic triggered during API or network failures."
        ),
    ),
    AnalogyEntry(
        term="interface_contract",
        icon="🔌",
        name="The Wall Plug",
        analogy=(
            "The exact size and shape of data passed between modules."
        ),
    ),
    AnalogyEntry(
        term="circuit_breaker",
        icon="🔒",
        name="The Safety Switch",
        analogy=(
            "Automatically cuts power to a failing service so the rest of "
            "the system stays alive – just like a fuse in your home."
        ),
    ),
    AnalogyEntry(
        term="event_loop",
        icon="🔄",
        name="The Spinning Plate",
        analogy=(
            "A single thread that keeps all tasks in the air by checking "
            "each one in rapid rotation, never blocking on any single task."
        ),
    ),
    AnalogyEntry(
        term="idempotency",
        icon="🖨️",
        name="The Stamp Machine",
        analogy=(
            "Pressing the stamp twice produces the same single mark – running "
            "the operation multiple times has the same effect as running it once."
        ),
    ),
    AnalogyEntry(
        term="eventual_consistency",
        icon="📬",
        name="The Post Office",
        analogy=(
            "Every node will receive the same letter eventually, but not "
            "necessarily at the same moment."
        ),
    ),
    AnalogyEntry(
        term="sharding",
        icon="🗄️",
        name="The Filing Cabinet",
        analogy=(
            "Instead of one enormous drawer, data is split across multiple "
            "smaller drawers so each one can be opened independently."
        ),
    ),
    AnalogyEntry(
        term="rate_limiter",
        icon="🚦",
        name="The Traffic Light",
        analogy=(
            "Controls the flow of requests so fast clients cannot overwhelm "
            "the server – just as traffic lights prevent gridlock."
        ),
    ),
    AnalogyEntry(
        term="message_queue",
        icon="📥",
        name="The Inbox Tray",
        analogy=(
            "Tasks pile up in a tray when the worker is busy; the worker "
            "processes them one by one at its own pace."
        ),
    ),
    AnalogyEntry(
        term="caching",
        icon="🗃️",
        name="The Desktop Sticky Note",
        analogy=(
            "Frequently needed information is kept on your desk so you don't "
            "have to fetch it from the filing room every time."
        ),
    ),
]

# Build a lookup dict for O(1) access.
_ANALOGY_MAP: dict[str, AnalogyEntry] = {e.term: e for e in _ANALOGIES}

# Also index by partial term for convenience (e.g. "register" → "state_register").
_PARTIAL_MAP: dict[str, str] = {
    "invariant": "invariant",
    "state": "state_register",
    "register": "state_register",
    "state_register": "state_register",
    "degradation": "degradation_mode",
    "fallback": "degradation_mode",
    "interface": "interface_contract",
    "contract": "interface_contract",
    "circuit": "circuit_breaker",
    "breaker": "circuit_breaker",
    "loop": "event_loop",
    "event_loop": "event_loop",
    "idempotent": "idempotency",
    "idempotency": "idempotency",
    "eventual": "eventual_consistency",
    "consistency": "eventual_consistency",
    "shard": "sharding",
    "sharding": "sharding",
    "rate": "rate_limiter",
    "rate_limiter": "rate_limiter",
    "queue": "message_queue",
    "message_queue": "message_queue",
    "cache": "caching",
    "caching": "caching",
}


# ---------------------------------------------------------------------------
# Built-in trade-off cards
# ---------------------------------------------------------------------------

_TRADEOFF_CARDS: list[TradeOffCard] = [
    TradeOffCard(
        decision="async_sql_pool",
        description="Use an async SQL connection pool (e.g. asyncpg) instead of synchronous drivers.",
        gains=[
            "High concurrency without spawning OS threads",
            "Lower memory footprint under many simultaneous requests",
            "Native integration with async frameworks (FastAPI, Starlette)",
        ],
        costs=[
            "Cannot use sync ORM calls inside async code without thread offloading",
            "Harder to debug: stack traces span multiple event loop ticks",
            "Requires async-aware migration tooling",
        ],
    ),
    TradeOffCard(
        decision="redis_cache_vs_db",
        description="Serve reads from Redis in-memory cache instead of querying the database directly.",
        gains=[
            "Sub-millisecond read latency for hot data",
            "Significant reduction in database load",
            "Supports TTL-based expiry out of the box",
        ],
        costs=[
            "Cache invalidation complexity – stale reads possible",
            "Additional infrastructure component to operate and monitor",
            "Data loss risk if Redis is not persisted (AOF/RDB)",
        ],
    ),
    TradeOffCard(
        decision="eventual_consistency_vs_acid",
        description="Accept eventual consistency (distributed replicas) instead of ACID transactions.",
        gains=[
            "Higher availability during network partitions (CAP theorem)",
            "Horizontal scalability without distributed lock contention",
            "Lower write latency in globally distributed deployments",
        ],
        costs=[
            "Reads may return stale data for a window of time",
            "Complex application-level conflict resolution required",
            "Harder to reason about correctness in financial or inventory systems",
        ],
    ),
    TradeOffCard(
        decision="microservices_vs_monolith",
        description="Split functionality into independent microservices rather than a single monolith.",
        gains=[
            "Independent deployment and scaling per service",
            "Technology heterogeneity – each service picks its own stack",
            "Smaller codebases are easier for small teams to own",
        ],
        costs=[
            "Network latency and distributed failure modes",
            "Operational overhead: service discovery, tracing, load balancing",
            "Data consistency across service boundaries requires careful design",
        ],
    ),
    TradeOffCard(
        decision="message_queue_async",
        description="Decouple producer and consumer via an async message queue (Kafka, RabbitMQ).",
        gains=[
            "Producers never block waiting for slow consumers",
            "Natural buffer against traffic spikes",
            "Enables fan-out to multiple independent consumers",
        ],
        costs=[
            "At-least-once delivery requires idempotent consumers",
            "End-to-end latency is higher than synchronous calls",
            "Queue depth monitoring and back-pressure handling add complexity",
        ],
    ),
    TradeOffCard(
        decision="jwt_stateless_vs_session_store",
        description="Use stateless JWT tokens instead of server-side session storage.",
        gains=[
            "No shared session state – scales horizontally without sticky sessions",
            "Works natively across microservices without a central session store",
        ],
        costs=[
            "Tokens cannot be instantly revoked without a token blacklist",
            "Payload is base64-encoded – avoid storing sensitive claims",
            "Expiry management (refresh tokens) adds implementation complexity",
        ],
    ),
]

_TRADEOFF_MAP: dict[str, TradeOffCard] = {c.decision: c for c in _TRADEOFF_CARDS}


# ---------------------------------------------------------------------------
# AnalogyTranslator
# ---------------------------------------------------------------------------


class AnalogyTranslator:
    """Translate formal software terms into plain-English analogies and
    generate trade-off cards for common architectural decisions.
    """

    # ------------------------------------------------------------------
    # Analogy translation
    # ------------------------------------------------------------------

    def translate(self, term: str) -> AnalogyEntry | None:
        """Return the analogy entry for *term*, or ``None`` if not found.

        Args:
            term: Formal software term to look up (case-insensitive).  May be
                an exact canonical key (e.g. ``'invariant'``) or a partial
                alias (e.g. ``'register'``).

        Returns:
            Matching :class:`AnalogyEntry`, or ``None``.
        """
        normalised = term.lower().strip().replace(" ", "_")
        key = _PARTIAL_MAP.get(normalised, normalised)
        return _ANALOGY_MAP.get(key)

    def translate_all(self, terms: Sequence[str]) -> list[AnalogyEntry]:
        """Translate multiple terms, silently skipping unknown entries.

        Args:
            terms: Sequence of term strings to look up.

        Returns:
            List of successfully resolved :class:`AnalogyEntry` objects.
        """
        results: list[AnalogyEntry] = []
        for term in terms:
            entry = self.translate(term)
            if entry is not None:
                results.append(entry)
        return results

    def list_terms(self) -> list[str]:
        """Return all canonical term identifiers in the analogy dictionary."""
        return list(_ANALOGY_MAP.keys())

    # ------------------------------------------------------------------
    # Trade-off cards
    # ------------------------------------------------------------------

    def trade_off_cards_for(self, decision: str) -> list[TradeOffCard]:
        """Return trade-off card(s) matching *decision*.

        Args:
            decision: Decision key (e.g. ``'async_sql_pool'``) or a partial
                substring to search across decision labels.

        Returns:
            List of matching :class:`TradeOffCard` objects (empty if none found).
        """
        normalised = decision.lower().strip().replace(" ", "_")
        if normalised in _TRADEOFF_MAP:
            return [_TRADEOFF_MAP[normalised]]
        # Partial substring fallback
        return [c for c in _TRADEOFF_CARDS if normalised in c.decision]

    def all_trade_off_cards(self) -> list[TradeOffCard]:
        """Return the complete list of built-in trade-off cards."""
        return list(_TRADEOFF_CARDS)
