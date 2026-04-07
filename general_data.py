from __future__ import annotations

import json
from pathlib import Path
from typing import Any

OFFICIAL_GENERALS_FILE = Path(__file__).resolve().parent / "data" / "official_generals_catalog.json"


def normalize_general_entry(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    normalized.setdefault("name", normalized.get("raw_name") or "Генерал")
    normalized.setdefault("portrait_url", "")
    normalized.setdefault("skills", [])
    normalized.setdefault("abilities", [])
    normalized.setdefault("source", "local")
    normalized.setdefault("status", "verified")
    return normalized


def load_official_generals_catalog() -> list[dict[str, Any]]:
    if not OFFICIAL_GENERALS_FILE.exists():
        return []
    try:
        raw = json.loads(OFFICIAL_GENERALS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    return [normalize_general_entry(item) for item in raw if isinstance(item, dict)]


def get_generals_catalog() -> list[dict[str, Any]]:
    return sorted(
        load_official_generals_catalog(),
        key=lambda item: (
            -int(item.get("rarity_id") or 0),
            str(item.get("name") or ""),
        ),
    )
