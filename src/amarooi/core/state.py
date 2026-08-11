"""Interactive state machine for the Amarooi planning session.

This module provides :class:`PlannerSession`, which manages the lifecycle of a
logic-manifest generation session through well-defined states.

Example:
    >>> from amarooi.core.state import PlannerSession
    >>> session = PlannerSession()
    >>> manifest = session.generate_manifest_from_prompt("Build an even/odd checker")
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum, auto

from amarooi.core.exceptions import AmarooiException
from amarooi.planner.schemas import LogicManifest
from amarooi.utils.llm import GroqClientWrapper

logger = logging.getLogger(__name__)

# System prompt that instructs the LLM to emit a JSON logic manifest.
_SYSTEM_PROMPT = """\
You are an expert software architect and logic planner for the Amarooi framework.

Your task is to analyse the user's system requirements and produce a structured
logic manifest in strict JSON format that conforms exactly to the following schema:

{
  "meta": {
    "project_name": "<string>",
    "version": "1.0.0",
    "generated_at": "<ISO-8601 timestamp>",
    "engine_version": "1.0.0"
  },
  "context": {
    "problem_statement": "<string>",
    "target_language": "python",
    "runtime_constraints": ["<string>", ...]
  },
  "state_matrix": {
    "variables": [
      {
        "name": "<string>",
        "type": "<string>",
        "description": "<string>",
        "allowed_values": null | ["<string>", ...]
      }
    ],
    "invariants": ["<string>", ...]
  },
  "logic_gates": [
    {
      "gate_id": "<string>",
      "condition": "<string>",
      "on_true": "<string>",
      "on_false": "<string>"
    }
  ],
  "edge_cases": [
    {
      "scenario": "<string>",
      "fallback_action": "<string>"
    }
  ]
}

Return ONLY the JSON object — no explanations, no Markdown fences.
"""


class SessionState(Enum):
    """Enumeration of possible states for a :class:`PlannerSession`.

    Attributes:
        IDLE: The session has been created but no planning has started.
        PLANNING: A manifest generation request is currently in progress.
        MANIFEST_GENERATED: A manifest has been successfully generated.
        FAILED: The last generation attempt ended in an unrecoverable error.
    """

    IDLE = auto()
    PLANNING = auto()
    MANIFEST_GENERATED = auto()
    FAILED = auto()


class PlannerSession:
    """Manages state during interactive logic-prompt extraction.

    The session begins in :attr:`SessionState.IDLE` and transitions through
    :attr:`SessionState.PLANNING` before arriving at either
    :attr:`SessionState.MANIFEST_GENERATED` (success) or
    :attr:`SessionState.FAILED` (error).

    Attributes:
        state: Current :class:`SessionState` of the session.
        manifest: The last successfully generated :class:`LogicManifest`, or
            ``None`` if no manifest has been produced yet.
    """

    def __init__(self, client: GroqClientWrapper | None = None) -> None:
        """Initialise a new planner session.

        Args:
            client: Optional pre-configured :class:`~amarooi.utils.llm.GroqClientWrapper`
                instance.  If *None*, a new client is created using the default
                application settings.
        """
        self.state: SessionState = SessionState.IDLE
        self.manifest: LogicManifest | None = None
        self._client: GroqClientWrapper = client or GroqClientWrapper()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_manifest_from_prompt(self, prompt: str) -> LogicManifest:
        """Convert raw system requirements into a validated :class:`LogicManifest`.

        Transitions the session through :attr:`~SessionState.PLANNING` and
        then to either :attr:`~SessionState.MANIFEST_GENERATED` on success or
        :attr:`~SessionState.FAILED` on error.

        Args:
            prompt: Free-form natural-language description of the system or
                logic to be planned.

        Returns:
            A fully validated :class:`~amarooi.planner.schemas.LogicManifest`
            instance constructed from the LLM's JSON response.

        Raises:
            AmarooiException: If the LLM call fails or the response cannot be
                validated against the manifest schema.  The session state is
                set to :attr:`~SessionState.FAILED` before re-raising.
        """
        self.state = SessionState.PLANNING
        logger.info("PlannerSession: starting manifest generation.")

        messages: list[dict[str, str]] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Requirements:\n{prompt}\n\n"
                    f"Current UTC time: {datetime.now(tz=timezone.utc).isoformat()}"
                ),
            },
        ]

        try:
            manifest = self._client.generate_structured_json(
                messages=messages,
                response_schema=LogicManifest,
            )
        except AmarooiException:
            self.state = SessionState.FAILED
            logger.error("PlannerSession: manifest generation failed.")
            raise

        self.manifest = manifest
        self.state = SessionState.MANIFEST_GENERATED
        logger.info("PlannerSession: manifest generated successfully.")
        return manifest
