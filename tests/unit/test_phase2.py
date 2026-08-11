"""Unit tests for Phase 2 planner schemas and manifest engine."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from amarooi.core.exceptions import ManifestValidationError
from amarooi.planner.manifest import ManifestEngine
from amarooi.planner.schemas import LogicManifest


def _build_valid_manifest_payload() -> dict[str, object]:
    """Return a valid manifest payload for use in planner tests."""
    return {
        "meta": {
            "project_name": "Amarooi Demo",
            "version": "1.0.0",
            "generated_at": "2026-08-11T20:00:00Z",
            "engine_version": "2.0.0",
        },
        "context": {
            "problem_statement": "Process user requests deterministically.",
            "runtime_constraints": ["offline-only", "no-network-side-effects"],
        },
        "state_matrix": {
            "variables": [
                {
                    "name": "request_status",
                    "type": "string",
                    "description": "Tracks the current request status.",
                    "allowed_values": ["pending", "complete"],
                }
            ],
            "invariants": ["request_status must always be present"],
        },
        "logic_gates": [
            {
                "gate_id": "gate-1",
                "condition": "request_status == 'pending'",
                "on_true": "continue_processing",
                "on_false": "return_result",
            }
        ],
        "edge_cases": [
            {
                "scenario": "Missing request status",
                "fallback_action": "reject_request",
            }
        ],
    }


class TestLogicManifestSchemas:
    """Tests for manifest schema validation."""

    def test_valid_manifest_payload_parses(self) -> None:
        payload = _build_valid_manifest_payload()

        manifest = LogicManifest.model_validate(payload)

        assert manifest.meta.project_name == "Amarooi Demo"
        assert manifest.context.target_language == "python"
        assert manifest.state_matrix.variables[0].allowed_values == [
            "pending",
            "complete",
        ]
        assert manifest.logic_gates[0].gate_id == "gate-1"
        assert manifest.edge_cases[0].fallback_action == "reject_request"


class TestManifestEngine:
    """Tests for manifest loading, saving, and raw JSON validation."""

    def test_validate_raw_json_rejects_invalid_json(self) -> None:
        with pytest.raises(ManifestValidationError):
            ManifestEngine.validate_raw_json("not valid json {{{")

    def test_validate_raw_json_rejects_missing_required_fields(self) -> None:
        invalid_payload = _build_valid_manifest_payload()
        invalid_payload.pop("meta")

        with pytest.raises(ManifestValidationError):
            ManifestEngine.validate_raw_json(json.dumps(invalid_payload))

    def test_save_and_load_manifest_round_trip(self, tmp_path: Path) -> None:
        payload = _build_valid_manifest_payload()
        manifest = LogicManifest.model_validate(payload)
        output_path = tmp_path / "logic.amarooi.json"

        ManifestEngine.save_manifest(manifest, output_path)
        loaded_manifest = ManifestEngine.load_manifest(output_path)

        assert output_path.read_text(encoding="utf-8").startswith('{\n  "meta"')
        assert loaded_manifest == manifest
