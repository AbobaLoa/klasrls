from __future__ import annotations

import json
from pathlib import Path
from typing import Any

UNIT_CATALOG: list[dict[str, Any]] = [
    {"name": "Maceman", "category": "Core Attack", "attack": 38, "melee_def": 38, "ranged_def": 6, "looting": 32, "movement": 73, "food": 2, "status": "verified"},
    {"name": "Crossbowman", "category": "Core Attack", "attack": 36, "melee_def": 6, "ranged_def": 36, "looting": 22, "movement": 73, "food": 2, "status": "verified"},
    {"name": "Swordsman", "category": "Core Attack", "attack": 61, "melee_def": 5, "ranged_def": 3, "looting": 12, "movement": 24, "food": 3, "status": "verified"},
    {"name": "Two-Handed Swordsman", "category": "Core Attack", "attack": 109, "melee_def": 19, "ranged_def": 5, "looting": 28, "movement": 18, "food": 4, "status": "verified"},
    {"name": "Heavy Crossbowman", "category": "Core Attack", "attack": 92, "melee_def": 15, "ranged_def": 24, "looting": 32, "movement": 20, "food": 4, "status": "verified"},
    {"name": "Veteran Maceman", "category": "Core Attack", "attack": 118, "melee_def": 20, "ranged_def": 6, "looting": 32, "movement": 22, "food": 4, "status": "verified"},
    {"name": "Veteran Crossbowman", "category": "Core Attack", "attack": 98, "melee_def": 16, "ranged_def": 26, "looting": 22, "movement": 23, "food": 4, "status": "verified"},
    {"name": "Veteran Swordsman", "category": "Core Attack", "attack": 111, "melee_def": 138, "ranged_def": 72, "looting": 29, "movement": 28, "food": 6, "status": "verified"},
    {"name": "Veteran Two-Handed Sword", "category": "Core Attack", "attack": 125, "melee_def": 20, "ranged_def": 6, "looting": 32, "movement": 28, "food": 4, "status": "verified"},
    {"name": "Veteran Heavy Crossbowman", "category": "Core Attack", "attack": 145, "melee_def": 16, "ranged_def": 26, "looting": 25, "movement": 28, "food": 4, "status": "verified"},
    {"name": "Armed Citizens", "category": "Core Defense", "attack": 3, "melee_def": 9, "ranged_def": 9, "looting": None, "movement": None, "food": 0, "status": "partial"},
    {"name": "Militia", "category": "Core Defense", "attack": 24, "melee_def": 27, "ranged_def": 27, "looting": None, "movement": None, "food": 0, "status": "partial"},
    {"name": "Spearman", "category": "Core Defense", "attack": 26, "melee_def": 26, "ranged_def": 8, "looting": 14, "movement": 75, "food": 2, "status": "verified"},
    {"name": "Bowman", "category": "Core Defense", "attack": 24, "melee_def": 8, "ranged_def": 24, "looting": 13, "movement": 75, "food": 2, "status": "verified"},
    {"name": "Archer", "category": "Core Defense", "attack": 10, "melee_def": 53, "ranged_def": 55, "looting": 9, "movement": 25, "food": 3, "status": "verified"},
    {"name": "Halberdier", "category": "Core Defense", "attack": 17, "melee_def": 135, "ranged_def": 45, "looting": 18, "movement": 19, "food": 4, "status": "verified"},
    {"name": "Longbowman", "category": "Core Defense", "attack": 20, "melee_def": 51, "ranged_def": 125, "looting": 21, "movement": 21, "food": 4, "status": "verified"},
    {"name": "Veteran Spearman", "category": "Core Defense", "attack": 15, "melee_def": 142, "ranged_def": 52, "looting": 14, "movement": 26, "food": 4, "status": "verified"},
    {"name": "Veteran Bowman", "category": "Core Defense", "attack": 18, "melee_def": 59, "ranged_def": 132, "looting": 13, "movement": 27, "food": 4, "status": "verified"},
    {"name": "Shadow Maceman", "category": "Shadow Mercenaries", "attack": 37, "melee_def": 4, "ranged_def": 23, "looting": 32, "movement": 22, "food": 0, "status": "verified"},
    {"name": "Shadow Crossbowman", "category": "Shadow Mercenaries", "attack": 39, "melee_def": 20, "ranged_def": 7, "looting": 22, "movement": 23, "food": 0, "status": "verified"},
    {"name": "Shadow Rogue", "category": "Shadow Mercenaries", "attack": 109, "melee_def": 19, "ranged_def": 5, "looting": 28, "movement": 18, "food": 0, "status": "verified"},
    {"name": "Shadow Felon", "category": "Shadow Mercenaries", "attack": 92, "melee_def": 15, "ranged_def": 24, "looting": 32, "movement": 20, "food": 0, "status": "verified"},
    {"name": "Travelling Crossbowman", "category": "Travelling Soldiers", "attack": 135, "melee_def": 22, "ranged_def": 30, "looting": 35, "movement": 25, "food": 4, "status": "verified"},
    {"name": "Travelling Knight", "category": "Travelling Soldiers", "attack": 146, "melee_def": 20, "ranged_def": 9, "looting": 34, "movement": 25, "food": 4, "status": "verified"},
    {"name": "Knight of the Kingsguard", "category": "Kingsguard", "attack": 138, "melee_def": 18, "ranged_def": 5, "looting": 45, "movement": 25, "food": 4, "status": "verified"},
    {"name": "Crossbowman of the Kingsguard", "category": "Kingsguard", "attack": 127, "melee_def": 14, "ranged_def": 23, "looting": 45, "movement": 25, "food": 4, "status": "verified"},
    {"name": "Sentinel of the Kingsguard", "category": "Kingsguard", "attack": 14, "melee_def": 150, "ranged_def": 59, "looting": 16, "movement": 27, "food": 4, "status": "verified"},
    {"name": "Scout of the Kingsguard", "category": "Kingsguard", "attack": 16, "melee_def": 64, "ranged_def": 139, "looting": 16, "movement": 27, "food": 4, "status": "verified"},
    {"name": "Norseman with Axe", "category": "Everwinter Glacier", "attack": 103, "melee_def": 129, "ranged_def": 41, "looting": 20, "movement": 25, "food": 4, "status": "verified"},
    {"name": "Norseman with Bow", "category": "Everwinter Glacier", "attack": 86, "melee_def": 48, "ranged_def": 119, "looting": 20, "movement": 25, "food": 4, "status": "verified"},
    {"name": "Saber Warrior", "category": "Burning Sands", "attack": 109, "melee_def": 135, "ranged_def": 45, "looting": 20, "movement": 25, "food": 4, "status": "verified"},
    {"name": "Desert Bowman", "category": "Burning Sands", "attack": 92, "melee_def": 51, "ranged_def": 125, "looting": 20, "movement": 25, "food": 4, "status": "verified"},
    {"name": "Cultist Fanatic", "category": "Fire Peaks", "attack": 124, "melee_def": 144, "ranged_def": 55, "looting": 20, "movement": 25, "food": 4, "status": "verified"},
    {"name": "Cultist Bowman", "category": "Fire Peaks", "attack": 124, "melee_def": 144, "ranged_def": 55, "looting": 20, "movement": 25, "food": 4, "status": "partial"},
    {"name": "Marauder", "category": "Marauder Event", "attack": 113, "melee_def": 18, "ranged_def": 4, "looting": 70, "movement": 30, "food": 4, "status": "verified"},
    {"name": "Pyromaniac", "category": "Marauder Event", "attack": 111, "melee_def": 19, "ranged_def": 4, "looting": 25, "movement": 30, "food": 4, "status": "verified"},
    {"name": "Veteran Marauder", "category": "Marauder Event", "attack": 165, "melee_def": 18, "ranged_def": 4, "looting": 105, "movement": 32, "food": 5, "status": "verified"},
    {"name": "Veteran Pyromaniac", "category": "Marauder Event", "attack": 160, "melee_def": 19, "ranged_def": 4, "looting": 31, "movement": 32, "food": 5, "status": "verified"},
    {"name": "Slingshot", "category": "Nomad Soldiers", "attack": 130, "melee_def": 5, "ranged_def": 9, "looting": 29, "movement": 28, "food": 4, "status": "partial"},
    {"name": "Saber Cleaver", "category": "Nomad Soldiers", "attack": 139, "melee_def": 6, "ranged_def": 3, "looting": 33, "movement": 28, "food": 4, "status": "partial"},
    {"name": "Khan Guards", "category": "Nomad Soldiers", "attack": None, "melee_def": None, "ranged_def": None, "looting": None, "movement": None, "food": 4, "status": "partial"},
    {"name": "Lion Warrior", "category": "Berimond", "attack": 117, "melee_def": 139, "ranged_def": 48, "looting": 26, "movement": 25, "food": 4, "status": "verified"},
    {"name": "Bear Warrior", "category": "Berimond", "attack": 117, "melee_def": 139, "ranged_def": 48, "looting": 26, "movement": 25, "food": 4, "status": "verified"},
    {"name": "Lion Bowman", "category": "Berimond", "attack": 98, "melee_def": 54, "ranged_def": 129, "looting": 26, "movement": 25, "food": 4, "status": "verified"},
    {"name": "Bear Bowman", "category": "Berimond", "attack": 98, "melee_def": 54, "ranged_def": 129, "looting": 26, "movement": 25, "food": 4, "status": "verified"},
    {"name": "Demon Horror", "category": "Horror Soldiers", "attack": 185, "melee_def": 19, "ranged_def": 5, "looting": 35, "movement": 28, "food": 5, "status": "verified"},
    {"name": "Deathly Horror", "category": "Horror Soldiers", "attack": 162, "melee_def": 15, "ranged_def": 24, "looting": 40, "movement": 28, "food": 5, "status": "verified"},
    {"name": "Veteran Demon Horror", "category": "Horror Soldiers", "attack": 200, "melee_def": 21, "ranged_def": 6, "looting": 45, "movement": 30, "food": 5, "status": "verified"},
    {"name": "Veteran Deathly Horror", "category": "Horror Soldiers", "attack": 175, "melee_def": 17, "ranged_def": 26, "looting": 50, "movement": 30, "food": 5, "status": "verified"},
    {"name": "Renegade Stone Smasher", "category": "Storm Islands", "attack": 135, "melee_def": 22, "ranged_def": 30, "looting": 20, "movement": 50, "food": 4, "status": "partial"},
    {"name": "Renegade Shark Tooth Warrior", "category": "Storm Islands", "attack": 146, "melee_def": None, "ranged_def": None, "looting": None, "movement": None, "food": None, "status": "partial"},
]


OFFICIAL_CATALOG_FILE = Path(__file__).resolve().parent / "data" / "official_units_catalog.json"


def normalize_unit_entry(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    normalized.setdefault("display_name", normalized.get("name"))
    normalized.setdefault("image_url", "")
    normalized.setdefault("source", "local")
    normalized.setdefault("status", "verified")
    normalized.setdefault("attack_strength", normalized.get("attack"))
    normalized.setdefault("melee_strength", normalized.get("melee_attack", normalized.get("attack")))
    normalized.setdefault("ranged_strength", normalized.get("ranged_attack", normalized.get("attack")))
    if normalized.get("melee_attack") is None and normalized.get("role") == "melee":
        normalized["melee_attack"] = normalized.get("attack")
    if normalized.get("ranged_attack") is None and normalized.get("role") == "ranged":
        normalized["ranged_attack"] = normalized.get("attack")
    return normalized


def load_official_unit_catalog() -> list[dict[str, Any]]:
    if not OFFICIAL_CATALOG_FILE.exists():
        return []
    try:
        raw = json.loads(OFFICIAL_CATALOG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    return [normalize_unit_entry(item) for item in raw if isinstance(item, dict)]


def get_unit_catalog() -> list[dict[str, Any]]:
    official_catalog = load_official_unit_catalog()
    if official_catalog:
        return sorted(official_catalog, key=lambda item: (str(item.get("category") or ""), str(item.get("display_name") or item.get("name") or "")))
    return sorted((normalize_unit_entry(item) for item in UNIT_CATALOG), key=lambda item: (item["category"], item["display_name"] or item["name"]))
