from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def make_tool(
    name: str,
    category: str,
    level: int | None = None,
    wall_reduction: int | None = None,
    gate_reduction: int | None = None,
    moat_reduction: int | None = None,
    ranged_defense_reduction: int | None = None,
    melee_attack_bonus: int | None = None,
    ranged_attack_bonus: int | None = None,
    courtyard_melee_kills: int | None = None,
    courtyard_ranged_kills: int | None = None,
    courtyard_defender_kills: int | None = None,
    courtyard_power_bonus: int | None = None,
    global_attack_bonus: int | None = None,
    extra_waves: int | None = None,
    glory_bonus: int | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "display_name": f"{name} Lv.{level}" if level is not None else name,
        "side": "attack",
        "category": category,
        "level": level,
        "wall_reduction": wall_reduction,
        "gate_reduction": gate_reduction,
        "moat_reduction": moat_reduction,
        "ranged_defense_reduction": ranged_defense_reduction,
        "melee_attack_bonus": melee_attack_bonus,
        "ranged_attack_bonus": ranged_attack_bonus,
        "courtyard_melee_kills": courtyard_melee_kills,
        "courtyard_ranged_kills": courtyard_ranged_kills,
        "courtyard_defender_kills": courtyard_defender_kills,
        "courtyard_power_bonus": courtyard_power_bonus,
        "global_attack_bonus": global_attack_bonus,
        "extra_waves": extra_waves,
        "glory_bonus": glory_bonus,
        "status": "verified",
    }


ATTACK_TOOLS: list[dict[str, Any]] = [
    make_tool("Осадная башня", "wall", wall_reduction=20),
    make_tool("Тяжелый таран", "gate", gate_reduction=20),
    make_tool("Защитная стена", "ranged", ranged_defense_reduction=15),
    make_tool("Маска захватчика", "ranged", ranged_defense_reduction=20),
    make_tool("Лестница захватчика", "wall", wall_reduction=25),
    make_tool("Таран захватчика", "gate", gate_reduction=25),
    make_tool("Штурмовая лестница", "wall", wall_reduction=10),
    make_tool("Улучшенная осадная башня", "wall", wall_reduction=15),
    make_tool("Деревянный щит", "ranged", ranged_defense_reduction=5),
    make_tool("Обитый железом щит", "ranged", ranged_defense_reduction=10),
    make_tool("Таран", "gate", gate_reduction=10),
    make_tool("Железный таран", "gate", gate_reduction=15),
    make_tool("Фашины", "moat", moat_reduction=5),
    make_tool("Осадный мост", "moat", moat_reduction=10),
    make_tool("Таран черепаха", "gate", gate_reduction=15),
    make_tool("Камни", "moat", moat_reduction=15),
    make_tool("Боевой рог", "melee_attack", melee_attack_bonus=1),
    make_tool("Факелы", "melee_attack", melee_attack_bonus=30),
    make_tool("Отравленные стрелы", "ranged_attack", ranged_attack_bonus=30),
    make_tool("Элитный подъемник лучников", "wall_glory", wall_reduction=20, glory_bonus=5),
    make_tool("Флотский щит", "ranged", ranged_defense_reduction=10),
    make_tool("Королевская лестница", "wall_glory", wall_reduction=20, glory_bonus=6),
    make_tool("Имперская лестница", "wall_glory", wall_reduction=20, glory_bonus=8),
    make_tool("Элитный шипастый щит", "ranged_glory", ranged_defense_reduction=15, glory_bonus=5),
    make_tool("Штандарт", "glory", glory_bonus=5),
    make_tool("Таран рассомаха", "gate_glory", gate_reduction=20, glory_bonus=5),
    make_tool("Королевский таран", "gate_glory", gate_reduction=20, glory_bonus=6),
    make_tool("Имперский таран", "gate_glory", gate_reduction=20, glory_bonus=8),
    make_tool("Королевский щит", "ranged_glory", ranged_defense_reduction=15, glory_bonus=6),
    make_tool("Имперский щит", "ranged_glory", ranged_defense_reduction=15, glory_bonus=8),
    make_tool("Стяг", "glory", glory_bonus=1),
    make_tool("Боевое знамя", "glory", glory_bonus=2),
    make_tool("Знамя героя", "glory", glory_bonus=3),
    make_tool("Знамя триумфа", "glory", glory_bonus=4),
    make_tool("Королевское знамя", "glory", glory_bonus=6),
    make_tool("Имперское знамя", "glory", glory_bonus=8),
    make_tool("Знамя императора", "glory", glory_bonus=10),
    make_tool("Знамя королевы", "glory", glory_bonus=11),
    make_tool("Тележка с камнями", "moat_glory", moat_reduction=15, glory_bonus=5),
    make_tool("Королевский мост", "moat_glory", moat_reduction=15, glory_bonus=6),
    make_tool("Имперский мост", "moat_glory", moat_reduction=15, glory_bonus=8),
]

for level in range(1, 12):
    ATTACK_TOOLS.append(
        make_tool(
            "Усиленный таран",
            "gate_ranged",
            level=level,
            gate_reduction=30 + min(level - 1, 10),
            ranged_defense_reduction=20 if level == 11 else 15,
        )
    )

for level in range(1, 12):
    if level <= 5:
        ranged_value = 19 + level
        glory_value = 1
    elif level <= 10:
        ranged_value = 19 + level
        glory_value = 2
    else:
        ranged_value = 30
        glory_value = 3
    ATTACK_TOOLS.append(
        make_tool(
            "Башня славы",
            "ranged_glory",
            level=level,
            ranged_defense_reduction=ranged_value,
            glory_bonus=glory_value,
        )
    )

for level, wall_value in {1: 25, 2: 25, 3: 26, 4: 26, 5: 27, 6: 27, 7: 28, 8: 28, 9: 30, 10: 30}.items():
    ATTACK_TOOLS.append(
        make_tool(
            "Пушка крюкомет",
            "wall_melee",
            level=level,
            wall_reduction=wall_value,
            melee_attack_bonus=level,
        )
    )

for level, moat_value in {1: 20, 2: 22, 3: 22, 4: 24, 5: 24, 6: 26, 7: 26, 8: 28, 9: 28, 10: 30}.items():
    ATTACK_TOOLS.append(
        make_tool(
            "Хвачка",
            "moat_ranged",
            level=level,
            moat_reduction=moat_value,
            ranged_attack_bonus=level * 2,
        )
    )

for level, wall_value in {1: 25, 2: 25, 3: 26, 4: 26, 5: 27, 6: 27, 7: 28, 8: 28, 9: 30, 10: 30}.items():
    ATTACK_TOOLS.append(
        make_tool(
            "Осадная мортира",
            "wall_ranged",
            level=level,
            wall_reduction=wall_value,
            ranged_attack_bonus=level,
        )
    )

for level in range(1, 11):
    ATTACK_TOOLS.append(
        make_tool(
            "Осколочная бомба",
            "courtyard_melee",
            level=level,
            courtyard_melee_kills=250 + level * 25,
            courtyard_power_bonus=level,
        )
    )

for level in range(1, 11):
    ATTACK_TOOLS.append(
        make_tool(
            "Ручная бомбарда",
            "courtyard_all",
            level=level,
            courtyard_defender_kills=250 + level * 50,
            courtyard_power_bonus=level,
        )
    )

for level in range(1, 11):
    ATTACK_TOOLS.append(
        make_tool(
            "Штурмовой огнемет",
            "courtyard_power",
            level=level,
            courtyard_power_bonus=19 + level,
        )
    )

for level in range(1, 4):
    ATTACK_TOOLS.append(
        make_tool(
            "Боевая повозка",
            "waves",
            level=level,
            extra_waves=level,
            global_attack_bonus=(level * 2) - 1,
        )
    )

for level in range(1, 11):
    ATTACK_TOOLS.append(
        make_tool(
            "Пушка орган",
            "courtyard_ranged",
            level=level,
            courtyard_ranged_kills=250 + level * 25,
            courtyard_power_bonus=level,
        )
    )


OFFICIAL_TOOLS_FILE = Path(__file__).resolve().parent / "data" / "official_tools_catalog.json"


def normalize_tool_entry(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    normalized.setdefault("display_name", normalized.get("name"))
    normalized.setdefault("image_url", "")
    normalized.setdefault("source", "local")
    normalized.setdefault("status", "verified")
    normalized.setdefault("side", "attack")
    normalized.setdefault("def_melee_bonus", normalized.get("raw_def_melee_bonus", 0))
    normalized.setdefault("wall_capacity_bonus", normalized.get("raw_bonus_wall_capacity", 0))
    normalized.setdefault("defense_power_bonus", normalized.get("raw_bonus_defence_power", 0))
    normalized.setdefault("yard_defense_power_bonus", normalized.get("raw_bonus_yard_defense_power", 0))
    normalized.setdefault("kill_attacking_melee_yard", normalized.get("raw_kill_attacking_melee_yard", 0))
    normalized.setdefault("kill_attacking_ranged_yard", normalized.get("raw_kill_attacking_ranged_yard", 0))
    normalized.setdefault("kill_attacking_any_yard", normalized.get("raw_kill_attacking_any_yard", 0))
    normalized.setdefault("reserve_unit_kill", normalized.get("raw_reserve_unit_kill", 0))
    return normalized


def load_official_attack_tools_catalog() -> list[dict[str, Any]]:
    if not OFFICIAL_TOOLS_FILE.exists():
        return []
    try:
        raw = json.loads(OFFICIAL_TOOLS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    return [normalize_tool_entry(item) for item in raw if isinstance(item, dict)]


def get_all_tools_catalog() -> list[dict[str, Any]]:
    official_catalog = load_official_attack_tools_catalog()
    if official_catalog:
        return sorted(
            official_catalog,
            key=lambda item: (
                str(item.get("side") or ""),
                str(item.get("category") or ""),
                str(item.get("display_name") or item.get("name") or ""),
                item.get("level") or 0,
            ),
        )
    return sorted(
        (normalize_tool_entry(item) for item in ATTACK_TOOLS),
        key=lambda item: (item["category"], item["display_name"] or item["name"], item["level"] or 0),
    )


def get_attack_tools_catalog() -> list[dict[str, Any]]:
    return [item for item in get_all_tools_catalog() if str(item.get("side") or "attack").lower() == "attack"]


def get_defense_tools_catalog() -> list[dict[str, Any]]:
    return [item for item in get_all_tools_catalog() if str(item.get("side") or "").lower() in {"defense", "defence"}]
