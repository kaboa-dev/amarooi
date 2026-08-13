"""Verified Knowledge Retrieval Engine.

Provides background retrieval of verified technical patterns and documentation
to anchor architectural advice in accurate, up-to-date facts.

In production this module integrates with configured external sources (official
framework docs, RFC repositories, curated design-pattern catalogs).  In the
default *offline* mode it falls back to a built-in curated knowledge base so
that the rest of the system always has a stable, dependency-free baseline.

Example::

    from amarooi.core.search import KnowledgeEngine
    engine = KnowledgeEngine()
    results = engine.query("JWT authentication best practices")
    for r in results:
        print(r.title, r.source)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class KnowledgeEntry:
    """A single retrieved knowledge artefact.

    Attributes:
        title: Short human-readable title for the entry.
        summary: One-to-three sentence description of the concept or pattern.
        source: Canonical source label (e.g. ``'RFC 7519'``, ``'OWASP'``).
        tags: Keywords that connect this entry to domain/compound searches.
        verified: ``True`` when the entry originates from an official or
            peer-reviewed source rather than community content.
    """

    title: str
    summary: str
    source: str
    tags: list[str] = field(default_factory=list)
    verified: bool = True


# ---------------------------------------------------------------------------
# Built-in curated knowledge base
# ---------------------------------------------------------------------------

_BUILTIN_KB: list[KnowledgeEntry] = [
    # --- Auth / Session ---------------------------------------------------------
    KnowledgeEntry(
        title="JSON Web Tokens (JWT)",
        summary=(
            "Compact, URL-safe tokens for representing claims between two parties. "
            "Sign with HS256 or RS256; validate signature before trusting payload. "
            "Store only non-sensitive claims; never embed passwords."
        ),
        source="RFC 7519",
        tags=["jwt", "auth", "token", "session", "web_api"],
    ),
    KnowledgeEntry(
        title="OAuth 2.0 Authorization Framework",
        summary=(
            "Delegated authorisation protocol enabling third-party access without "
            "exposing credentials. Use PKCE for public clients (SPAs, mobile apps)."
        ),
        source="RFC 6749",
        tags=["oauth", "auth", "token", "session", "web_api"],
    ),
    KnowledgeEntry(
        title="OWASP Authentication Cheat Sheet",
        summary=(
            "Multi-factor authentication, secure password storage (bcrypt/Argon2), "
            "account-lockout policies, and session-fixation prevention."
        ),
        source="OWASP",
        tags=["auth", "password", "session", "security", "web_api"],
    ),
    # --- SQL / ORM --------------------------------------------------------------
    KnowledgeEntry(
        title="SQLAlchemy ORM Patterns",
        summary=(
            "Use declarative base classes for model definitions; leverage async "
            "session factories (``AsyncSession``) for high-concurrency APIs. "
            "Prefer explicit transactions over implicit auto-commit."
        ),
        source="SQLAlchemy Docs",
        tags=["sql", "orm", "database", "schema", "web_api"],
    ),
    KnowledgeEntry(
        title="Database Index Design",
        summary=(
            "B-tree indexes for range queries; partial indexes for filtered lookups. "
            "Avoid over-indexing write-heavy tables. Use ``EXPLAIN ANALYZE`` to "
            "validate query plans."
        ),
        source="PostgreSQL Documentation",
        tags=["sql", "database", "index", "performance"],
    ),
    # --- REST / GraphQL ---------------------------------------------------------
    KnowledgeEntry(
        title="RESTful API Design Principles",
        summary=(
            "Use nouns for resources, HTTP verbs for actions. Return appropriate "
            "status codes. Version via URL prefix (``/v1/``) or ``Accept`` headers. "
            "Paginate large collections."
        ),
        source="IETF RFC 7231",
        tags=["rest", "api", "endpoint", "http", "web_api"],
    ),
    KnowledgeEntry(
        title="GraphQL Schema Design",
        summary=(
            "Define strong types for all queries and mutations. Use connections "
            "for pagination (Relay spec). DataLoader pattern prevents N+1 queries."
        ),
        source="GraphQL Specification",
        tags=["graphql", "api", "schema", "web_api"],
    ),
    # --- Trading / Event Engines ------------------------------------------------
    KnowledgeEntry(
        title="Circuit Breaker Pattern",
        summary=(
            "Prevents cascade failures by opening after N consecutive errors and "
            "entering a half-open probe state after a cool-down period. "
            "Implement with exponential back-off for re-entry."
        ),
        source="Release It! (Nygard, 2018)",
        tags=["circuit_breaker", "trading", "networking", "resilience"],
    ),
    KnowledgeEntry(
        title="WebSocket Real-Time Ingestion",
        summary=(
            "Use ``asyncio`` + ``websockets`` library for Python; heartbeat pings "
            "every 30 s detect silent disconnects. Reconnect with exponential "
            "back-off; buffer in-flight messages during reconnection."
        ),
        source="RFC 6455",
        tags=["websocket", "realtime", "trading", "networking"],
    ),
    KnowledgeEntry(
        title="Order Execution Risk Controls",
        summary=(
            "Enforce pre-trade risk checks (position limits, notional caps) as "
            "invariant gates before submitting orders. Log every state transition "
            "for audit and replay."
        ),
        source="FIX Protocol / Industry Best Practice",
        tags=["order", "execution", "risk", "trading"],
    ),
    # --- Compiler / AST ---------------------------------------------------------
    KnowledgeEntry(
        title="Recursive Descent Parsing",
        summary=(
            "Top-down parser that maps each grammar rule to a dedicated function. "
            "Handles LL(k) grammars cleanly; straightforward to extend. "
            "Prefer explicit error recovery nodes over silent failure."
        ),
        source="Crafting Interpreters (Nystrom, 2021)",
        tags=["parser", "ast", "compiler", "grammar"],
    ),
    KnowledgeEntry(
        title="Visitor Pattern for AST Transformations",
        summary=(
            "Decouple tree traversal from node-type logic using double-dispatch "
            "visitors. Each transformation pass should be a separate visitor to "
            "keep concerns isolated."
        ),
        source="Design Patterns (GoF)",
        tags=["ast", "visitor", "compiler", "transform"],
    ),
    # --- Game Engines -----------------------------------------------------------
    KnowledgeEntry(
        title="Fixed-Timestep Game Loop",
        summary=(
            "Separate update rate from render rate. Accumulate elapsed time and "
            "call ``update(dt)`` in fixed increments. Interpolate render state "
            "to avoid visual jitter at non-aligned frames."
        ),
        source="Game Programming Patterns (Nystrom, 2014)",
        tags=["game", "loop", "delta", "frame", "physics"],
    ),
    KnowledgeEntry(
        title="Entity-Component-System (ECS)",
        summary=(
            "Data-oriented architecture that separates entities (IDs), components "
            "(data bags), and systems (logic). Enables cache-friendly iteration and "
            "easy composition without deep inheritance hierarchies."
        ),
        source="Game Programming Patterns (Nystrom, 2014)",
        tags=["game", "entity", "component", "state_machine"],
    ),
    # --- Networking / Microservices ---------------------------------------------
    KnowledgeEntry(
        title="Exponential Backoff with Jitter",
        summary=(
            "Retry failed requests with wait = min(cap, base * 2^n) + random_jitter. "
            "Full jitter distributes load across retrying clients. "
            "Cap retries to avoid unbounded waiting."
        ),
        source="AWS Architecture Blog",
        tags=["retry", "backoff", "networking", "resilience"],
    ),
    KnowledgeEntry(
        title="gRPC & Protocol Buffers",
        summary=(
            "Binary serialisation (Protobuf) reduces payload size vs JSON. "
            "Supports streaming RPCs. Define service contracts in ``.proto`` files "
            "and generate client/server stubs."
        ),
        source="gRPC Documentation",
        tags=["grpc", "rpc", "protobuf", "networking", "serialisation"],
    ),
    KnowledgeEntry(
        title="Rate Limiting Algorithms",
        summary=(
            "Token bucket allows short bursts; leaky bucket enforces steady rate. "
            "Sliding window log gives precise counts. Use Redis atomic INCR + EXPIRE "
            "for distributed rate limiting."
        ),
        source="Cloudflare Engineering Blog",
        tags=["rate_limit", "throttle", "networking", "web_api"],
    ),
]

# Pre-build a lowercase tag index for fast lookup.
_TAG_INDEX: dict[str, list[KnowledgeEntry]] = {}
for _entry in _BUILTIN_KB:
    for _tag in _entry.tags:
        _TAG_INDEX.setdefault(_tag, []).append(_entry)


# ---------------------------------------------------------------------------
# KnowledgeEngine
# ---------------------------------------------------------------------------


class KnowledgeEngine:
    """Background knowledge retrieval engine.

    By default operates in *offline* mode using the built-in curated
    knowledge base.  Subclass and override :meth:`_fetch_remote` to wire in
    live documentation sources.
    """

    def __init__(self, *, verified_only: bool = True) -> None:
        """Initialise the engine.

        Args:
            verified_only: When ``True`` (default), results from the built-in
                knowledge base are filtered to entries whose ``verified``
                attribute is ``True``.
        """
        self._verified_only = verified_only

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def query(self, query_text: str, *, max_results: int = 5) -> list[KnowledgeEntry]:
        """Retrieve relevant knowledge entries for *query_text*.

        Performs a keyword-based search against the built-in curated knowledge
        base.  Results are ranked by the number of query tokens that match an
        entry's tags or title.

        Args:
            query_text: Natural-language question or keyword phrase.
            max_results: Maximum number of entries to return.

        Returns:
            Ranked list of :class:`KnowledgeEntry` objects (best match first).
        """
        tokens = _tokenize(query_text)
        scored: dict[int, int] = {}  # entry id → hit count
        entry_map: dict[int, KnowledgeEntry] = {}

        for token in tokens:
            for entry in _TAG_INDEX.get(token, []):
                eid = id(entry)
                entry_map[eid] = entry
                scored[eid] = scored.get(eid, 0) + 1

            # Also match against title words
            for entry in _BUILTIN_KB:
                if token in entry.title.lower():
                    eid = id(entry)
                    entry_map[eid] = entry
                    scored[eid] = scored.get(eid, 0) + 1

        candidates = list(entry_map.values())
        if self._verified_only:
            candidates = [e for e in candidates if e.verified]

        ranked = sorted(candidates, key=lambda e: scored.get(id(e), 0), reverse=True)
        return ranked[:max_results]

    def query_for_domain(self, domain: str, *, max_results: int = 5) -> list[KnowledgeEntry]:
        """Return knowledge entries relevant to a specific domain identifier.

        Args:
            domain: Domain identifier as returned by
                :class:`~amarooi.core.domain.DomainAdapter` (e.g. ``'trading'``).
            max_results: Maximum number of entries to return.

        Returns:
            Filtered list of :class:`KnowledgeEntry` objects.
        """
        results = [e for e in _BUILTIN_KB if domain in e.tags]
        if self._verified_only:
            results = [e for e in results if e.verified]
        return results[:max_results]

    def _fetch_remote(self, query_text: str) -> list[KnowledgeEntry]:  # pragma: no cover
        """Hook for subclasses to add live remote retrieval.

        Override this method to query external documentation APIs.  The base
        implementation always returns an empty list (offline mode).
        """
        return []


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    """Lower-case and split *text* into word tokens, stripping punctuation."""
    return re.findall(r"[a-z]+", text.lower())
