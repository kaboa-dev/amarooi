"""Dynamic Domain Adaptation & Software Component Inference Engine.

Automatically infers the system architecture domain and required software
components from an unstructured natural-language prompt, without forcing
the user to select from dropdowns.

Supported domains
-----------------
- ``web_api`` – Web / API / Mobile applications
- ``trading`` – Trading / Event Engines
- ``compiler`` – Compilers / Extractor Tools
- ``game`` – Game Engines / Interactive Systems
- ``networking`` – Networking / Microservices

Each domain maps to a set of *software components*: the canonical structural
building blocks that should be scaffolded for that kind of system.

Example::

    from amarooi.core.domain import DomainAdapter
    adapter = DomainAdapter()
    result = adapter.infer("Build a REST API with JWT auth and Postgres")
    print(result.domain)      # 'web_api'
    print(result.software_components)   # ['Security & Auth Component (JWT, OAuth, Encryption)', ...]
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence


# ---------------------------------------------------------------------------
# Domain keyword signals
# ---------------------------------------------------------------------------

#: Mapping of domain name → frozenset of signal keywords (lower-case).
_DOMAIN_SIGNALS: dict[str, frozenset[str]] = {
    "web_api": frozenset(
        {
            "api", "rest", "graphql", "http", "https", "endpoint", "route",
            "web", "mobile", "jwt", "oauth", "session", "token", "auth",
            "sql", "orm", "database", "postgres", "mysql", "sqlite",
            "request", "response", "json", "client", "server", "frontend",
            "backend", "middleware", "cors", "cookie",
        }
    ),
    "trading": frozenset(
        {
            "trade", "trading", "order", "execution", "broker", "market",
            "price", "bid", "ask", "portfolio", "risk", "circuit", "breaker",
            "websocket", "stream", "tick", "candle", "position", "balance",
            "exchange", "algo", "latency", "fill", "instrument",
        }
    ),
    "compiler": frozenset(
        {
            "compiler", "transpiler", "ast", "parse", "token", "tokenize",
            "lexer", "grammar", "syntax", "transform", "codegen",
            "intermediate", "ir", "bytecode", "emit", "visitor", "walker",
            "rewrite", "macro", "dsl", "language",
        }
    ),
    "game": frozenset(
        {
            "game", "entity", "sprite", "render", "frame", "delta",
            "collision", "physics", "scene", "player", "enemy", "level",
            "animation", "input", "controller", "canvas", "shader",
            "texture", "mesh", "event_loop", "tick", "update",
        }
    ),
    "networking": frozenset(
        {
            "microservice", "service", "rpc", "grpc", "protobuf", "kafka",
            "queue", "broker", "pubsub", "retry", "backoff", "rate", "limit",
            "throttle", "circuit", "serializ", "deserializ", "mesh", "proxy",
            "gateway", "load", "balancer", "timeout", "health", "check",
        }
    ),
}

#: Canonical software components for each domain.
_DOMAIN_SOFTWARE_COMPONENTS: dict[str, list[str]] = {
    "web_api": [
        "Security & Auth Component (JWT, OAuth, Encryption)",
        "Database Component (SQL, ORM, Migrations)",
        "Networking Component (REST, WebSockets, Rate Limiters)",
        "Presentation Component (Client UI State, Forms, Validation)",
    ],
    "trading": [
        "Networking Component (Broker APIs, WebSockets, Rate Limiters)",
        "Execution Loop Component (State Machines, Invariant Gates)",
        "Database Component (Orders, Positions, Ledger Storage)",
        "Risk Control Component (Circuit Breakers, Exposure Checks, Alerts)",
    ],
    "compiler": [
        "Parsing Component (Tokenizers, AST Builders, Grammar Rules)",
        "Execution Loop Component (State Machines, Invariant Gates)",
        "Transformation Component (Visitors, Rewriters, Optimizers)",
        "Code Generation Component (IR, Emitters, Target Backends)",
    ],
    "game": [
        "Execution Loop Component (Frame Delta, State Machines, Invariant Gates)",
        "Rendering Component (Sprites, Scenes, Shaders)",
        "Physics Component (Collisions, Constraints, Kinematics)",
        "Input Component (Controllers, Actions, Event Mapping)",
    ],
    "networking": [
        "Networking Component (REST, WebSockets, Rate Limiters)",
        "Execution Loop Component (State Machines, Invariant Gates)",
        "Security & Auth Component (mTLS, OAuth, Encryption)",
        "Serialization Component (RPC Contracts, Schemas, Backoff Policies)",
    ],
}

#: Fallback domain used when no domain can be inferred with sufficient confidence.
_FALLBACK_DOMAIN = "web_api"

#: Minimum number of matching keywords required to claim a domain.
_MIN_KEYWORD_HITS = 2


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class DomainInferenceResult:
    """Result of a domain inference pass.

    Attributes:
        domain: The inferred domain identifier (e.g. ``'web_api'``).
        software_components: Ordered list of canonical software components for the
            domain.
        confidence: Fraction of matched keywords relative to the winning domain's
            vocabulary size.  Value in ``[0.0, 1.0]``.
        prompt_tokens: Normalised tokens extracted from the original prompt.
    """

    domain: str
    software_components: list[str]
    confidence: float
    prompt_tokens: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# DomainAdapter
# ---------------------------------------------------------------------------


class DomainAdapter:
    """Infer the software domain and required software components from a prompt.

    The adapter uses a keyword-frequency heuristic; it requires no LLM call and
    is therefore always fast and deterministic.
    """

    def infer(self, prompt: str) -> DomainInferenceResult:
        """Infer domain and software components from an unstructured prompt.

        Args:
            prompt: Free-form description of the system being built.  May be
                a single sentence or several hundred words.

        Returns:
            A :class:`DomainInferenceResult` with the best-matching domain,
            its canonical software components, and a confidence score.
        """
        tokens = _tokenize(prompt)
        scores: dict[str, int] = {}
        for domain, signals in _DOMAIN_SIGNALS.items():
            hits = sum(1 for token in tokens if token in signals)
            if hits >= _MIN_KEYWORD_HITS:
                scores[domain] = hits

        if not scores:
            # No domain reached minimum threshold – pick the domain with the
            # most hits even if below threshold, and fall back to web_api on tie.
            raw_scores = {
                domain: sum(1 for t in tokens if t in sigs)
                for domain, sigs in _DOMAIN_SIGNALS.items()
            }
            best = max(raw_scores, key=raw_scores.get)  # type: ignore[arg-type]
            chosen = best if raw_scores[best] > 0 else _FALLBACK_DOMAIN
        else:
            chosen = max(scores, key=scores.get)  # type: ignore[arg-type]

        vocab_size = len(_DOMAIN_SIGNALS[chosen])
        confidence = min(scores.get(chosen, 0) / vocab_size, 1.0)

        return DomainInferenceResult(
            domain=chosen,
            software_components=list(_DOMAIN_SOFTWARE_COMPONENTS[chosen]),
            confidence=round(confidence, 4),
            prompt_tokens=tokens,
        )

    def list_domains(self) -> list[str]:
        """Return all supported domain identifiers."""
        return list(_DOMAIN_SIGNALS.keys())

    def software_components_for(self, domain: str) -> list[str]:
        """Return the canonical software components for a given domain.

        Args:
            domain: A domain identifier (e.g. ``'trading'``).

        Returns:
            Ordered list of software component names.

        Raises:
            KeyError: If *domain* is not recognised.
        """
        if domain not in _DOMAIN_SOFTWARE_COMPONENTS:
            raise KeyError(
                f"Unknown domain: '{domain}'.  Valid domains: {list(_DOMAIN_SOFTWARE_COMPONENTS)}"
            )
        return list(_DOMAIN_SOFTWARE_COMPONENTS[domain])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    """Lower-case and split *text* into word tokens, stripping punctuation."""
    return re.findall(r"[a-z]+", text.lower())
