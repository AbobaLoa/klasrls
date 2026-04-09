from __future__ import annotations

import json
from pathlib import Path
from typing import Any

OFFICIAL_BUILDINGS_FILE = Path(__file__).resolve().parent / "data" / "official_buildings_catalog.json"
EXCLUDED_BUILDING_NAMES = {"Toolsmith-Kingdoms"}
BUILDING_MAX_LEVELS = {"Military academy": 10}


def sanitize_building_levels(name: str, levels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    max_level = BUILDING_MAX_LEVELS.get(str(name or "").strip())
    if max_level is None:
        return [dict(level) for level in levels if isinstance(level, dict)]
    result: list[dict[str, Any]] = []
    for level in levels:
        if not isinstance(level, dict):
            continue
        level_label = str(level.get("level") or "").strip()
        if not level_label.isdigit():
            continue
        if int(level_label) > max_level:
            continue
        result.append(dict(level))
    return result


def normalize_building_entry(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    normalized.setdefault("name", normalized.get("display_name") or "Здание")
    normalized.setdefault("display_name", normalized.get("name") or "Здание")
    normalized.setdefault("category", "Инфраструктура")
    normalized.setdefault("description", "Описание здания пока не заполнено.")
    normalized.setdefault("image_url", "")
    normalized.setdefault("resource_fields", [])
    normalized.setdefault("levels", [])
    normalized["levels"] = sanitize_building_levels(str(normalized.get("name") or ""), normalized.get("levels") or [])
    normalized["level_labels"] = [str(level.get("level") or "") for level in normalized.get("levels") or [] if level.get("level")]
    normalized.setdefault("source", "local")
    normalized.setdefault("status", "verified")
    return normalized


def load_official_buildings_catalog() -> list[dict[str, Any]]:
    if not OFFICIAL_BUILDINGS_FILE.exists():
        return []
    try:
        raw = json.loads(OFFICIAL_BUILDINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    return [
        normalize_building_entry(item)
        for item in raw
        if isinstance(item, dict) and str(item.get("name") or "").strip() not in EXCLUDED_BUILDING_NAMES
    ]


def get_buildings_catalog() -> list[dict[str, Any]]:
    return sorted(
        load_official_buildings_catalog(),
        key=lambda item: (str(item.get("category") or ""), str(item.get("display_name") or item.get("name") or "")),
    )
