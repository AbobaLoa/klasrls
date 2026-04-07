from __future__ import annotations

import json
from pathlib import Path
from typing import Any

GAME_MECHANICS_FILE = Path(__file__).resolve().parent / "data" / "game_mechanics_snapshot.json"


def load_game_mechanics_snapshot() -> dict[str, Any]:
    if not GAME_MECHANICS_FILE.exists():
        return {}
    try:
        raw = json.loads(GAME_MECHANICS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def get_current_model_gaps() -> list[str]:
    snapshot = load_game_mechanics_snapshot()
    current_model = snapshot.get("current_project_model") or {}
    gaps = current_model.get("not_implemented") or []
    return [str(item) for item in gaps if str(item).strip()]


def get_recommended_integration_order() -> list[str]:
    snapshot = load_game_mechanics_snapshot()
    items = snapshot.get("recommended_next_integration_order") or []
    return [str(item) for item in items if str(item).strip()]
