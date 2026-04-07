from __future__ import annotations

import json
from pathlib import Path
from typing import Any

OFFICIAL_EQUIPMENT_SETS_FILE = Path(__file__).resolve().parent / "data" / "official_equipment_sets_catalog.json"


def normalize_equipment_set_entry(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    normalized.setdefault("name", f"Set #{normalized.get('set_id') or '?'}")
    normalized.setdefault("pieces", [])
    normalized.setdefault("bonuses", [])
    normalized.setdefault("effect_summary", [])
    normalized.setdefault("wearer_labels", [])
    normalized.setdefault("source", "local")
    normalized.setdefault("status", "verified")
    return normalized


def load_official_equipment_sets_catalog() -> list[dict[str, Any]]:
    if not OFFICIAL_EQUIPMENT_SETS_FILE.exists():
        return []
    try:
        raw = json.loads(OFFICIAL_EQUIPMENT_SETS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    return [normalize_equipment_set_entry(item) for item in raw if isinstance(item, dict)]


def get_equipment_sets_catalog() -> list[dict[str, Any]]:
    return sorted(
        load_official_equipment_sets_catalog(),
        key=lambda item: (
            -(int(str(item.get("set_id") or 0)) if str(item.get("set_id") or "0").isdigit() else 0),
            str(item.get("name") or ""),
        ),
    )
