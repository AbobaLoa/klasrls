from __future__ import annotations

from math import ceil
from typing import Any

from tools_data import get_attack_tools_catalog, get_defense_tools_catalog

FLANKS = ("left", "center", "right")
FLANK_LABELS = {
    "left": "левая стена",
    "center": "центр",
    "right": "правая стена",
}
TOOL_EFFECT_FIELDS = (
    "wall_reduction",
    "gate_reduction",
    "moat_reduction",
    "ranged_defense_reduction",
    "melee_attack_bonus",
    "ranged_attack_bonus",
    "courtyard_melee_kills",
    "courtyard_ranged_kills",
    "courtyard_defender_kills",
    "courtyard_power_bonus",
    "global_attack_bonus",
    "extra_waves",
    "glory_bonus",
)
DEFENSE_TOOL_EFFECT_FIELDS = (
    "def_melee_bonus",
    "wall_capacity_bonus",
    "defense_power_bonus",
    "yard_defense_power_bonus",
    "kill_attacking_melee_yard",
    "kill_attacking_ranged_yard",
    "kill_attacking_any_yard",
    "reserve_unit_kill",
)


def to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(" ", "").replace(",", ".")
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def to_int(value: Any, default: int = 0) -> int:
    return int(round(to_float(value, default)))


def non_negative_float(value: Any, default: float = 0.0) -> float:
    return max(0.0, to_float(value, default))


def non_negative_int(value: Any, default: int = 0) -> int:
    return max(0, to_int(value, default))


def calculate_upgrade_plan(payload: dict[str, Any]) -> dict[str, Any]:
    building_name = str(payload.get("building_name") or "Здание").strip() or "Здание"
    current_level = non_negative_int(payload.get("current_level"), 0)
    target_level = non_negative_int(payload.get("target_level"), current_level)
    if target_level < current_level:
        target_level = current_level

    levels_payload = payload.get("levels") or []
    level_costs: dict[int, dict[str, Any]] = {}
    warnings: list[str] = []

    for raw_row in levels_payload:
        level = non_negative_int(raw_row.get("level"), 0)
        if level <= 0:
            continue
        level_costs[level] = {
            "level": level,
            "hammers": non_negative_int(raw_row.get("hammers"), 0),
            "tokens": non_negative_int(raw_row.get("tokens"), 0),
            "note": str(raw_row.get("note") or "").strip(),
        }

    if target_level == current_level:
        warnings.append("Целевой уровень равен текущему. Дополнительных затрат нет.")

    used_levels: list[dict[str, Any]] = []
    missing_levels: list[int] = []
    total_hammers = 0
    total_tokens = 0

    for level in range(current_level + 1, target_level + 1):
        row = level_costs.get(level)
        if not row:
            missing_levels.append(level)
            continue
        total_hammers += row["hammers"]
        total_tokens += row["tokens"]
        used_levels.append(row)

    if not used_levels and target_level > current_level:
        warnings.append("Для выбранного диапазона уровней не заполнены строки стоимости.")
    if missing_levels:
        warnings.append("Не заполнены данные по уровням: " + ", ".join(str(level) for level in missing_levels))

    return {
        "building_name": building_name,
        "current_level": current_level,
        "target_level": target_level,
        "summary": {
            "total_hammers": total_hammers,
            "total_tokens": total_tokens,
            "levels_counted": len(used_levels),
            "ready": not missing_levels and target_level > current_level,
        },
        "used_levels": used_levels,
        "missing_levels": missing_levels,
        "warnings": warnings,
    }


def calculate_building_upgrade_plan(payload: dict[str, Any]) -> dict[str, Any]:
    building_name = str(payload.get("building_name") or "Здание").strip() or "Здание"
    levels_payload = payload.get("levels") or []
    current_level_label = str(payload.get("current_level") or "").strip()
    target_level_label = str(payload.get("target_level") or current_level_label).strip()
    resource_fields = [str(field).strip() for field in (payload.get("resource_fields") or []) if str(field).strip()]
    warnings: list[str] = []

    ordered_levels = [dict(item) for item in levels_payload if isinstance(item, dict) and str(item.get("level") or "").strip()]
    level_labels = [str(item.get("level") or "").strip() for item in ordered_levels]

    if not ordered_levels:
        warnings.append("Для здания не загружены уровни улучшения.")
        return {
            "building_name": building_name,
            "current_level": current_level_label,
            "target_level": target_level_label,
            "resource_totals": {},
            "used_levels": [],
            "warnings": warnings,
            "ready": False,
        }

    if current_level_label not in level_labels:
        current_level_label = level_labels[0]
        warnings.append("Текущий уровень не найден в каталоге. Выбран первый доступный уровень.")
    if target_level_label not in level_labels:
        target_level_label = level_labels[-1]
        warnings.append("Целевой уровень не найден в каталоге. Выбран максимальный доступный уровень.")

    current_index = level_labels.index(current_level_label)
    target_index = level_labels.index(target_level_label)
    if target_index < current_index:
        target_index = current_index
        target_level_label = current_level_label
        warnings.append("Целевой уровень был ниже текущего. Диапазон выровнен автоматически.")
    if target_index == current_index:
        warnings.append("Целевой уровень равен текущему. Дополнительных затрат нет.")

    used_levels = ordered_levels[current_index + 1 : target_index + 1]
    resource_totals = {field: 0 for field in resource_fields}

    for row in used_levels:
        for field in resource_fields:
            value = row.get(field)
            if value in {None, ""}:
                continue
            resource_totals[field] = resource_totals.get(field, 0) + non_negative_int(value, 0)

    if not used_levels and target_index > current_index:
        warnings.append("Для выбранного диапазона уровней не нашлось промежуточных шагов улучшения.")

    return {
        "building_name": building_name,
        "current_level": current_level_label,
        "target_level": target_level_label,
        "resource_totals": resource_totals,
        "used_levels": used_levels,
        "warnings": warnings,
        "ready": target_index > current_index,
    }


def parse_units(units_payload: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    units: list[dict[str, Any]] = []
    warnings: list[str] = []

    for index, raw_unit in enumerate(units_payload, start=1):
        name = str(raw_unit.get("name") or f"Юнит {index}").strip() or f"Юнит {index}"
        available = non_negative_int(raw_unit.get("available"), 0)
        melee_def = non_negative_float(raw_unit.get("melee_def"), 0.0)
        ranged_def = non_negative_float(raw_unit.get("ranged_def"), 0.0)
        placed = {
            flank: non_negative_int((raw_unit.get("placed") or {}).get(flank, raw_unit.get(flank)), 0)
            for flank in FLANKS
        }
        total_placed = sum(placed.values())
        reserve = max(0, available - total_placed)
        if total_placed > available:
            warnings.append(
                f"У юнита '{name}' выставлено {total_placed}, но в наличии указано только {available}. Резерв принят как 0."
            )
        units.append(
            {
                "name": name,
                "available": available,
                "melee_def": melee_def,
                "ranged_def": ranged_def,
                "placed": placed,
                "reserve": reserve,
                "role": "ranged" if ranged_def >= melee_def else "melee",
            }
        )

    return units, warnings


def parse_flanks(flanks_payload: dict[str, Any]) -> dict[str, dict[str, float]]:
    parsed: dict[str, dict[str, float]] = {}
    for flank in FLANKS:
        raw = flanks_payload.get(flank) or {}
        parsed[flank] = {
            "enemy_melee": non_negative_float(raw.get("enemy_melee"), 0.0),
            "enemy_ranged": non_negative_float(raw.get("enemy_ranged"), 0.0),
            "tool_melee_bonus": non_negative_float(raw.get("tool_melee_bonus"), 0.0),
            "tool_ranged_bonus": non_negative_float(raw.get("tool_ranged_bonus"), 0.0),
            "extra_bonus_percent": non_negative_float(raw.get("extra_bonus_percent"), 0.0),
        }
    return parsed


def allocate_units(
    reserve_pool: list[dict[str, Any]],
    stat_key: str,
    deficit: float,
    multiplier: float,
) -> tuple[list[dict[str, Any]], float]:
    candidates = [unit for unit in reserve_pool if unit["reserve"] > 0 and unit[stat_key] > 0]
    candidates.sort(key=lambda item: (item[stat_key], item["reserve"]), reverse=True)
    remaining = deficit
    picks: list[dict[str, Any]] = []

    for unit in candidates:
        effective_value = unit[stat_key] * multiplier
        if effective_value <= 0:
            continue
        need_count = ceil(remaining / effective_value)
        use_count = min(unit["reserve"], need_count)
        if use_count <= 0:
            continue
        covered = use_count * effective_value
        picks.append(
            {
                "name": unit["name"],
                "count": use_count,
                "covered": round(covered, 2),
            }
        )
        unit["reserve"] -= use_count
        remaining -= covered
        if remaining <= 0:
            remaining = 0
            break

    return picks, remaining


def format_pick_list(picks: list[dict[str, Any]]) -> str:
    return ", ".join(f"{item['count']} x {item['name']}" for item in picks)


def calculate_defense_plan(payload: dict[str, Any]) -> dict[str, Any]:
    units, warnings = parse_units(payload.get("units") or [])
    flanks = parse_flanks(payload.get("flanks") or {})

    flank_results: dict[str, dict[str, Any]] = {}
    reserve_pool = [
        {
            "name": unit["name"],
            "reserve": unit["reserve"],
            "melee_def": unit["melee_def"],
            "ranged_def": unit["ranged_def"],
            "role": unit["role"],
        }
        for unit in units
    ]

    overall_defense = 0.0
    overall_enemy_attack = 0.0

    for flank in FLANKS:
        melee_base = 0.0
        ranged_base = 0.0
        units_on_flank = 0
        for unit in units:
            count = unit["placed"][flank]
            units_on_flank += count
            melee_base += count * unit["melee_def"]
            ranged_base += count * unit["ranged_def"]

        melee_multiplier = 1 + (flanks[flank]["tool_melee_bonus"] + flanks[flank]["extra_bonus_percent"]) / 100
        ranged_multiplier = 1 + (flanks[flank]["tool_ranged_bonus"] + flanks[flank]["extra_bonus_percent"]) / 100

        melee_final = melee_base * melee_multiplier
        ranged_final = ranged_base * ranged_multiplier
        enemy_melee = flanks[flank]["enemy_melee"]
        enemy_ranged = flanks[flank]["enemy_ranged"]

        flank_results[flank] = {
            "label": FLANK_LABELS[flank],
            "units_on_flank": units_on_flank,
            "base_melee_defense": round(melee_base, 2),
            "base_ranged_defense": round(ranged_base, 2),
            "final_melee_defense": round(melee_final, 2),
            "final_ranged_defense": round(ranged_final, 2),
            "enemy_melee": round(enemy_melee, 2),
            "enemy_ranged": round(enemy_ranged, 2),
            "melee_margin": round(melee_final - enemy_melee, 2),
            "ranged_margin": round(ranged_final - enemy_ranged, 2),
            "total_margin": round((melee_final + ranged_final) - (enemy_melee + enemy_ranged), 2),
            "tool_melee_bonus": flanks[flank]["tool_melee_bonus"],
            "tool_ranged_bonus": flanks[flank]["tool_ranged_bonus"],
            "extra_bonus_percent": flanks[flank]["extra_bonus_percent"],
            "melee_multiplier": melee_multiplier,
            "ranged_multiplier": ranged_multiplier,
        }
        overall_defense += melee_final + ranged_final
        overall_enemy_attack += enemy_melee + enemy_ranged

    flank_order = sorted(
        FLANKS,
        key=lambda flank: min(0, flank_results[flank]["melee_margin"]) + min(0, flank_results[flank]["ranged_margin"]),
    )

    advice: list[str] = []

    for flank in flank_order:
        result = flank_results[flank]
        flank_advice: list[str] = []

        melee_deficit = max(0.0, -result["melee_margin"])
        ranged_deficit = max(0.0, -result["ranged_margin"])

        if ranged_deficit > 0:
            picks, shortfall = allocate_units(reserve_pool, "ranged_def", ranged_deficit, result["ranged_multiplier"])
            if picks:
                flank_advice.append(
                    f"На {result['label']} докинь стрелков: {format_pick_list(picks)}."
                )
            if shortfall > 0:
                donor = max(
                    (other for other in FLANKS if other != flank),
                    key=lambda other: flank_results[other]["ranged_margin"],
                    default=None,
                )
                if donor and flank_results[donor]["ranged_margin"] > 0:
                    flank_advice.append(
                        f"После резерва всё ещё не хватает {round(shortfall, 2)} дальней защиты. Если допустимо, перекинь часть стрелков с {flank_results[donor]['label']}."
                    )
                else:
                    flank_advice.append(
                        f"Даже после резерва не хватает {round(shortfall, 2)} дальней защиты. Нужны дополнительные дальние юниты или больший буст орудий."
                    )

        if melee_deficit > 0:
            picks, shortfall = allocate_units(reserve_pool, "melee_def", melee_deficit, result["melee_multiplier"])
            if picks:
                flank_advice.append(
                    f"На {result['label']} усили ближнюю защиту: {format_pick_list(picks)}."
                )
            if shortfall > 0:
                donor = max(
                    (other for other in FLANKS if other != flank),
                    key=lambda other: flank_results[other]["melee_margin"],
                    default=None,
                )
                if donor and flank_results[donor]["melee_margin"] > 0:
                    flank_advice.append(
                        f"После резерва всё ещё не хватает {round(shortfall, 2)} ближней защиты. Если допустимо, перекинь часть мили-защиты с {flank_results[donor]['label']}."
                    )
                else:
                    flank_advice.append(
                        f"Даже после резерва не хватает {round(shortfall, 2)} ближней защиты. Нужны более плотные юниты или больший буст орудий."
                    )

        if not flank_advice:
            if result["total_margin"] >= 0:
                flank_advice.append(f"{result['label'].capitalize()} выглядит устойчиво. Резерв можно держать под самый слабый фланг.")
            else:
                flank_advice.append(f"{result['label'].capitalize()} проседает по сумме защиты. Проверь расклад войск и бусты отдельно по типам атаки.")

        result["advice"] = flank_advice
        advice.extend(flank_advice)

    weakest_flank = min(FLANKS, key=lambda flank: flank_results[flank]["total_margin"])
    unused_reserve = [
        {"name": unit["name"], "reserve": unit["reserve"]}
        for unit in reserve_pool
        if unit["reserve"] > 0
    ]

    return {
        "summary": {
            "overall_defense": round(overall_defense, 2),
            "overall_enemy_attack": round(overall_enemy_attack, 2),
            "overall_margin": round(overall_defense - overall_enemy_attack, 2),
            "weakest_flank": FLANK_LABELS[weakest_flank],
        },
        "flanks": flank_results,
        "reserve_left": unused_reserve,
        "advice": advice,
        "warnings": warnings,
    }


def empty_tool_effects() -> dict[str, float]:
    return {field: 0.0 for field in TOOL_EFFECT_FIELDS}


def empty_defense_tool_effects() -> dict[str, float]:
    return {field: 0.0 for field in DEFENSE_TOOL_EFFECT_FIELDS}


def build_attack_tool_index() -> dict[str, dict[str, Any]]:
    name_index: dict[str, dict[str, Any]] = {}
    display_index: dict[str, dict[str, Any]] = {}
    for tool in get_attack_tools_catalog():
        display_index[str(tool["display_name"]).strip().lower()] = tool
        key = str(tool["name"]).strip().lower()
        existing = name_index.get(key)
        if not existing or (tool.get("level") or 0) >= (existing.get("level") or 0):
            name_index[key] = tool
    return {**name_index, **display_index}


def build_defense_tool_index() -> dict[str, dict[str, Any]]:
    name_index: dict[str, dict[str, Any]] = {}
    display_index: dict[str, dict[str, Any]] = {}
    for tool in get_defense_tools_catalog():
        display_index[str(tool["display_name"]).strip().lower()] = tool
        key = str(tool["name"]).strip().lower()
        existing = name_index.get(key)
        if not existing or (tool.get("level") or 0) >= (existing.get("level") or 0):
            name_index[key] = tool
    return {**name_index, **display_index}


def parse_governor(payload: dict[str, Any]) -> dict[str, float]:
    return {
        "melee_bonus": non_negative_float(payload.get("melee_bonus"), 0.0),
        "ranged_bonus": non_negative_float(payload.get("ranged_bonus"), 0.0),
        "courtyard_bonus": non_negative_float(payload.get("courtyard_bonus"), 0.0),
        "center_bonus": non_negative_float(payload.get("center_bonus"), 0.0),
        "overall_bonus": non_negative_float(payload.get("overall_bonus"), 0.0),
        "wall_defense": non_negative_float(payload.get("wall_defense"), 0.0),
        "gate_defense": non_negative_float(payload.get("gate_defense"), 0.0),
        "moat_defense": non_negative_float(payload.get("moat_defense"), 0.0),
        "wall_limit_bonus": non_negative_int(payload.get("wall_limit_bonus"), 0),
    }


def parse_commander(payload: dict[str, Any]) -> dict[str, float]:
    return {
        "melee_bonus": non_negative_float(payload.get("melee_bonus"), 0.0),
        "ranged_bonus": non_negative_float(payload.get("ranged_bonus"), 0.0),
        "overall_bonus": non_negative_float(payload.get("overall_bonus"), 0.0),
        "flank_bonus": non_negative_float(payload.get("flank_bonus"), 0.0),
        "center_bonus": non_negative_float(payload.get("center_bonus"), 0.0),
        "courtyard_bonus": non_negative_float(payload.get("courtyard_bonus"), 0.0),
        "wall_bonus": non_negative_float(payload.get("wall_bonus"), 0.0),
        "gate_bonus": non_negative_float(payload.get("gate_bonus"), 0.0),
        "moat_bonus": non_negative_float(payload.get("moat_bonus"), 0.0),
    }


def parse_castle(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(payload.get("name") or "Замок").strip() or "Замок",
        "wall_units_base": non_negative_int(payload.get("wall_units_base"), 0),
        "defensive_resources_note": str(payload.get("defensive_resources_note") or "").strip(),
    }


def normalize_wave(value: Any, default: str = "all") -> str:
    text = str(value or "").strip().lower()
    return text or default


def is_wave_allowed(wave: str, max_waves: int) -> bool:
    text = str(wave or "").strip().lower()
    if not text or text == "all":
        return True
    if not text.isdigit():
        return True
    return int(text) <= max_waves


def aggregate_attack_units(
    attack_units_payload: list[dict[str, Any]],
    max_waves: int = 1,
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, dict[str, Any]]], list[dict[str, Any]], list[str]]:
    flank_totals = {
        flank: {"melee_attack": 0.0, "ranged_attack": 0.0}
        for flank in FLANKS
    }
    wave_totals: dict[str, dict[str, dict[str, Any]]] = {flank: {} for flank in FLANKS}
    selected: list[dict[str, Any]] = []
    warnings: list[str] = []

    for raw_unit in attack_units_payload:
        flank = str(raw_unit.get("flank") or "").strip().lower()
        if flank not in FLANKS:
            warnings.append(f"Неизвестный фланг для атакующего юнита: '{flank}'.")
            continue

        wave = normalize_wave(raw_unit.get("wave"), "1")
        if not is_wave_allowed(wave, max_waves):
            warnings.append(f"Волна {wave} для атакующего юнита '{raw_unit.get('name') or ''}' выходит за предел {max_waves} и пропущена.")
            continue
        name = str(raw_unit.get("name") or "").strip()
        count = non_negative_int(raw_unit.get("count"), 0)
        attack_value = non_negative_float(raw_unit.get("attack"), 0.0)
        role = str(raw_unit.get("role") or "melee").strip().lower()
        if role not in {"melee", "ranged"}:
            role = "ranged" if "range" in role else "melee"
        if not name or count <= 0 or attack_value <= 0:
            continue

        total_attack = attack_value * count
        bucket = wave_totals[flank].setdefault(
            wave,
            {
                "wave": wave,
                "melee_attack": 0.0,
                "ranged_attack": 0.0,
                "units": [],
            },
        )
        if role == "ranged":
            flank_totals[flank]["ranged_attack"] += total_attack
            bucket["ranged_attack"] += total_attack
        else:
            flank_totals[flank]["melee_attack"] += total_attack
            bucket["melee_attack"] += total_attack

        unit_data = {
            "flank": flank,
            "wave": wave,
            "name": name,
            "count": count,
            "attack": round(total_attack, 2),
            "role": role,
        }
        bucket["units"].append(unit_data)
        selected.append(unit_data)

    return flank_totals, wave_totals, selected, warnings


def aggregate_attack_tools(
    tools_payload: list[dict[str, Any]],
    max_waves: int = 1,
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, dict[str, float]]], list[dict[str, Any]], list[str]]:
    tool_index = build_attack_tool_index()
    totals = {"all": empty_tool_effects(), **{flank: empty_tool_effects() for flank in FLANKS}}
    wave_totals: dict[str, dict[str, dict[str, float]]] = {"all": {}, **{flank: {} for flank in FLANKS}}
    selected: list[dict[str, Any]] = []
    warnings: list[str] = []

    for raw_tool in tools_payload:
        flank = str(raw_tool.get("flank") or "all").strip().lower() or "all"
        if flank not in totals:
            warnings.append(f"Неизвестный фланг для орудия: '{flank}'. Используй left, center, right или all.")
            continue

        wave = normalize_wave(raw_tool.get("wave"), "all")
        if not is_wave_allowed(wave, max_waves):
            warnings.append(f"Волна {wave} для орудия '{raw_tool.get('name') or ''}' выходит за предел {max_waves} и пропущена.")
            continue
        tool_name = str(raw_tool.get("name") or "").strip()
        count = non_negative_int(raw_tool.get("count"), 0)
        if not tool_name or count <= 0:
            continue

        tool = tool_index.get(tool_name.lower())
        if not tool:
            warnings.append(f"Орудие '{tool_name}' не найдено в каталоге.")
            continue

        selected.append(
            {
                "flank": flank,
                "wave": wave,
                "name": tool["display_name"],
                "count": count,
            }
        )
        wave_bucket = wave_totals[flank].setdefault(wave, empty_tool_effects())
        for field in TOOL_EFFECT_FIELDS:
            totals[flank][field] += non_negative_float(tool.get(field), 0.0) * count
            wave_bucket[field] += non_negative_float(tool.get(field), 0.0) * count

    return totals, wave_totals, selected, warnings


def aggregate_defense_tools(
    tools_payload: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, float]], list[dict[str, Any]], list[str]]:
    tool_index = build_defense_tool_index()
    totals = {zone: empty_defense_tool_effects() for zone in ("all", *FLANKS, "courtyard")}
    selected: list[dict[str, Any]] = []
    warnings: list[str] = []

    for raw_tool in tools_payload:
        zone = str(raw_tool.get("flank") or raw_tool.get("zone") or "all").strip().lower() or "all"
        if zone not in totals:
            warnings.append(f"Неизвестная зона для оборонительного орудия: '{zone}'. Используй left, center, right, courtyard или all.")
            continue

        tool_name = str(raw_tool.get("name") or "").strip()
        count = non_negative_int(raw_tool.get("count"), 0)
        if not tool_name or count <= 0:
            continue

        tool = tool_index.get(tool_name.lower())
        if not tool:
            warnings.append(f"Оборонительное орудие '{tool_name}' не найдено в каталоге.")
            continue

        selected.append(
            {
                "flank": zone,
                "name": tool["display_name"],
                "count": count,
            }
        )
        for field in DEFENSE_TOOL_EFFECT_FIELDS:
            totals[zone][field] += non_negative_float(tool.get(field), 0.0) * count

    return totals, selected, warnings


def merge_tool_effects(tool_totals: dict[str, dict[str, float]], flank: str) -> dict[str, float]:
    merged = empty_tool_effects()
    for field in TOOL_EFFECT_FIELDS:
        merged[field] = tool_totals["all"][field] + tool_totals[flank][field]
    return merged


def merge_defense_tool_effects(tool_totals: dict[str, dict[str, float]], zone: str) -> dict[str, float]:
    merged = empty_defense_tool_effects()
    for zone_key in ("all", zone):
        bucket = tool_totals.get(zone_key)
        if not bucket:
            continue
        for field in DEFENSE_TOOL_EFFECT_FIELDS:
            merged[field] += bucket[field]
    return merged


def merge_wave_tool_effects(
    wave_tool_totals: dict[str, dict[str, dict[str, float]]],
    flank: str,
    wave: str,
) -> dict[str, float]:
    merged = empty_tool_effects()
    for flank_key in ("all", flank):
        for wave_key in ("all", wave):
            bucket = wave_tool_totals.get(flank_key, {}).get(wave_key)
            if not bucket:
                continue
            for field in TOOL_EFFECT_FIELDS:
                merged[field] += bucket[field]
    return merged


def strongest_wave_tool_effects(
    tool_totals: dict[str, dict[str, float]],
    wave_tool_totals: dict[str, dict[str, dict[str, float]]],
    flank: str,
) -> dict[str, float]:
    strongest = merge_tool_effects(tool_totals, flank)
    wave_keys = set(wave_tool_totals.get("all", {}).keys()) | set(wave_tool_totals.get(flank, {}).keys())
    for wave in wave_keys:
        if wave == "all":
            continue
        effects = merge_wave_tool_effects(wave_tool_totals, flank, wave)
        for field in TOOL_EFFECT_FIELDS:
            strongest[field] = max(strongest[field], effects[field])
    return strongest


def combine_all_tool_effects(tool_totals: dict[str, dict[str, float]]) -> dict[str, float]:
    merged = empty_tool_effects()
    for bucket in tool_totals.values():
        for field in TOOL_EFFECT_FIELDS:
            merged[field] += bucket[field]
    return merged


def combine_all_defense_tool_effects(tool_totals: dict[str, dict[str, float]]) -> dict[str, float]:
    merged = empty_defense_tool_effects()
    for bucket in tool_totals.values():
        for field in DEFENSE_TOOL_EFFECT_FIELDS:
            merged[field] += bucket[field]
    return merged


def calculate_castle_overview(payload: dict[str, Any]) -> dict[str, Any]:
    units, warnings = parse_units(payload.get("units") or [])
    governor = parse_governor(payload.get("governor") or {})
    castle = parse_castle(payload.get("castle") or {})
    defense_tools = combine_all_defense_tool_effects(payload.get("defense_tools") or {zone: empty_defense_tool_effects() for zone in ("all", *FLANKS, "courtyard")})

    total_units = sum(unit["available"] for unit in units)
    units_on_wall = sum(sum(unit["placed"].values()) for unit in units)
    total_melee = sum(unit["available"] * unit["melee_def"] for unit in units)
    total_ranged = sum(unit["available"] * unit["ranged_def"] for unit in units)
    wall_capacity = castle["wall_units_base"] + governor["wall_limit_bonus"] + non_negative_int(defense_tools["wall_capacity_bonus"], 0)
    if wall_capacity and units_on_wall > wall_capacity:
        warnings.append(
            f"На стене выставлено {units_on_wall} юнитов, а доступный лимит {wall_capacity}."
        )

    total_power_multiplier = 1 + governor["overall_bonus"] / 100
    courtyard_multiplier = 1 + (governor["overall_bonus"] + governor["courtyard_bonus"]) / 100

    return {
        "castle_name": castle["name"],
        "total_units": total_units,
        "units_on_wall": units_on_wall,
        "wall_units_base": castle["wall_units_base"],
        "wall_unit_limit_bonus": governor["wall_limit_bonus"],
        "wall_unit_limit_total": wall_capacity,
        "base_melee_power": round(total_melee, 2),
        "base_ranged_power": round(total_ranged, 2),
        "base_total_power": round(total_melee + total_ranged, 2),
        "boosted_total_power": round((total_melee + total_ranged) * total_power_multiplier, 2),
        "courtyard_power": round((total_melee + total_ranged) * courtyard_multiplier, 2),
        "warnings": warnings,
        "defensive_resources_note": castle["defensive_resources_note"],
    }


def calculate_profile_defense_plan(payload: dict[str, Any]) -> dict[str, Any]:
    units, warnings = parse_units(payload.get("units") or [])
    flanks = parse_flanks(payload.get("flanks") or {})
    governor = parse_governor(payload.get("governor") or {})
    commander = parse_commander(payload.get("commander") or {})
    castle = parse_castle(payload.get("castle") or {})
    max_waves = max(1, min(12, non_negative_int(payload.get("max_waves"), 1)))
    attack_totals, attack_wave_totals, selected_attack_units, attack_unit_warnings = aggregate_attack_units(payload.get("attack_units") or [], max_waves=max_waves)
    warnings.extend(attack_unit_warnings)
    tool_totals, wave_tool_totals, selected_tools, tool_warnings = aggregate_attack_tools(payload.get("attack_tools") or [], max_waves=max_waves)
    warnings.extend(tool_warnings)
    defense_tool_totals, selected_defense_tools, defense_tool_warnings = aggregate_defense_tools(payload.get("defense_tools") or [])
    warnings.extend(defense_tool_warnings)

    overview = calculate_castle_overview({
        "units": units,
        "governor": governor,
        "castle": castle,
        "defense_tools": defense_tool_totals,
    })
    warnings.extend(overview["warnings"])

    flank_results: dict[str, dict[str, Any]] = {}
    reserve_pool = [
        {
            "name": unit["name"],
            "reserve": unit["reserve"],
            "melee_def": unit["melee_def"],
            "ranged_def": unit["ranged_def"],
            "role": unit["role"],
        }
        for unit in units
    ]

    overall_defense = 0.0
    overall_enemy_attack = 0.0
    total_attacker_wall_losses = 0
    total_defender_wall_losses = 0

    for flank in FLANKS:
        melee_base = 0.0
        ranged_base = 0.0
        units_on_flank = 0
        melee_units_on_flank = 0
        ranged_units_on_flank = 0
        tool_effects = strongest_wave_tool_effects(tool_totals, wave_tool_totals, flank)
        defense_tool_effects = merge_defense_tool_effects(defense_tool_totals, flank)

        for unit in units:
            count = unit["placed"][flank]
            units_on_flank += count
            melee_base += count * unit["melee_def"]
            ranged_base += count * unit["ranged_def"]
            if unit["role"] == "ranged":
                ranged_units_on_flank += count
            else:
                melee_units_on_flank += count

        if flank == "center":
            structure_bonus = max(0.0, governor["gate_defense"] - (tool_effects["gate_reduction"] + commander["gate_bonus"])) + max(0.0, governor["moat_defense"] - (tool_effects["moat_reduction"] + commander["moat_bonus"]))
        else:
            structure_bonus = max(0.0, governor["wall_defense"] - (tool_effects["wall_reduction"] + commander["wall_bonus"])) + max(0.0, governor["moat_defense"] - (tool_effects["moat_reduction"] + commander["moat_bonus"]))

        base_bonus = governor["overall_bonus"] + flanks[flank]["extra_bonus_percent"] + defense_tool_effects["defense_power_bonus"]
        if flank == "center":
            base_bonus += governor["center_bonus"]

        melee_bonus_percent = base_bonus + governor["melee_bonus"] + flanks[flank]["tool_melee_bonus"] + structure_bonus + defense_tool_effects["def_melee_bonus"]
        ranged_bonus_percent = base_bonus + governor["ranged_bonus"] + flanks[flank]["tool_ranged_bonus"] + structure_bonus - tool_effects["ranged_defense_reduction"]

        melee_multiplier = max(0.0, 1 + melee_bonus_percent / 100)
        ranged_multiplier = max(0.0, 1 + ranged_bonus_percent / 100)

        melee_final = melee_base * melee_multiplier
        ranged_final = ranged_base * ranged_multiplier

        wave_results: list[dict[str, Any]] = []
        wave_enemy_melee = 0.0
        wave_enemy_ranged = 0.0
        flank_wave_map = attack_wave_totals.get(flank, {})
        sorted_waves = sorted(flank_wave_map.keys(), key=lambda value: int(value) if str(value).isdigit() else 999)
        for wave in sorted_waves:
            wave_data = flank_wave_map[wave]
            wave_effects = merge_wave_tool_effects(wave_tool_totals, flank, wave)
            attack_side_bonus = commander["overall_bonus"] + (commander["center_bonus"] if flank == "center" else commander["flank_bonus"])
            wave_melee = wave_data["melee_attack"] * (1 + (wave_effects["melee_attack_bonus"] + wave_effects["global_attack_bonus"] + commander["melee_bonus"] + attack_side_bonus) / 100)
            wave_ranged = wave_data["ranged_attack"] * (1 + (wave_effects["ranged_attack_bonus"] + wave_effects["global_attack_bonus"] + commander["ranged_bonus"] + attack_side_bonus) / 100)
            wave_enemy_melee += wave_melee
            wave_enemy_ranged += wave_ranged
            wave_results.append(
                {
                    "wave": wave,
                    "melee_attack": round(wave_melee, 2),
                    "ranged_attack": round(wave_ranged, 2),
                    "units": wave_data["units"],
                    "tool_effects": {field: round(wave_effects[field], 2) for field in TOOL_EFFECT_FIELDS if wave_effects[field]},
                }
            )

        enemy_melee = flanks[flank]["enemy_melee"] + attack_totals[flank]["melee_attack"]
        enemy_ranged = flanks[flank]["enemy_ranged"] + attack_totals[flank]["ranged_attack"]
        enemy_melee += wave_enemy_melee - attack_totals[flank]["melee_attack"]
        enemy_ranged += wave_enemy_ranged - attack_totals[flank]["ranged_attack"]
        attack_total = enemy_melee + enemy_ranged
        defense_total = melee_final + ranged_final
        attack_melee_count = sum(item["count"] for item in selected_attack_units if item["flank"] == flank and item["role"] == "melee")
        attack_ranged_count = sum(item["count"] for item in selected_attack_units if item["flank"] == flank and item["role"] == "ranged")
        attack_units_count = attack_melee_count + attack_ranged_count
        if attack_total <= 0:
            attacker_loss_ratio = 0.0
            defender_loss_ratio = 0.0
        elif defense_total <= 0:
            attacker_loss_ratio = 0.0
            defender_loss_ratio = 1.0
        else:
            dominance = attack_total / defense_total
            defender_loss_ratio = min(1.0, 0.45 * dominance)
            attacker_loss_ratio = min(1.0, 0.45 / max(dominance, 0.01))

        attacker_losses = min(attack_units_count, round(attack_units_count * attacker_loss_ratio))
        defender_losses = min(units_on_flank, round(units_on_flank * defender_loss_ratio))
        attacker_survivors = max(0, attack_units_count - attacker_losses)
        defender_survivors = max(0, units_on_flank - defender_losses)
        attack_survivor_ratio = attacker_survivors / attack_units_count if attack_units_count else 0.0
        defense_survivor_ratio = defender_survivors / units_on_flank if units_on_flank else 0.0
        wall_breached = attack_total > defense_total and attacker_survivors > 0
        attack_power_after_wall = attack_total * attack_survivor_ratio if wall_breached else 0.0
        defense_power_after_wall = defense_total * defense_survivor_ratio
        attacker_melee_survivors = round(attack_melee_count * attack_survivor_ratio)
        attacker_ranged_survivors = round(attack_ranged_count * attack_survivor_ratio)
        total_attacker_wall_losses += attacker_losses
        total_defender_wall_losses += defender_losses

        flank_results[flank] = {
            "label": FLANK_LABELS[flank],
            "units_on_flank": units_on_flank,
            "melee_units_on_flank": melee_units_on_flank,
            "ranged_units_on_flank": ranged_units_on_flank,
            "base_melee_defense": round(melee_base, 2),
            "base_ranged_defense": round(ranged_base, 2),
            "final_melee_defense": round(melee_final, 2),
            "final_ranged_defense": round(ranged_final, 2),
            "enemy_melee": round(enemy_melee, 2),
            "enemy_ranged": round(enemy_ranged, 2),
            "melee_margin": round(melee_final - enemy_melee, 2),
            "ranged_margin": round(ranged_final - enemy_ranged, 2),
            "total_margin": round((melee_final + ranged_final) - (enemy_melee + enemy_ranged), 2),
            "manual_melee_bonus": flanks[flank]["tool_melee_bonus"],
            "manual_ranged_bonus": flanks[flank]["tool_ranged_bonus"],
            "extra_bonus_percent": flanks[flank]["extra_bonus_percent"],
            "governor_structure_bonus": round(structure_bonus, 2),
            "applied_tool_effects": {field: round(tool_effects[field], 2) for field in TOOL_EFFECT_FIELDS if tool_effects[field]},
            "applied_defense_tools": {field: round(defense_tool_effects[field], 2) for field in DEFENSE_TOOL_EFFECT_FIELDS if defense_tool_effects[field]},
            "waves": wave_results,
            "melee_multiplier": melee_multiplier,
            "ranged_multiplier": ranged_multiplier,
            "wall_breached": wall_breached,
            "wall_held": not wall_breached,
            "attacker_losses": attacker_losses,
            "defender_losses": defender_losses,
            "attacker_survivors": attacker_survivors,
            "defender_survivors": defender_survivors,
            "attack_power_after_wall": round(attack_power_after_wall, 2),
            "defense_power_after_wall": round(defense_power_after_wall, 2),
            "attacker_melee_survivors": attacker_melee_survivors,
            "attacker_ranged_survivors": attacker_ranged_survivors,
        }
        overall_defense += melee_final + ranged_final
        overall_enemy_attack += enemy_melee + enemy_ranged

    flank_order = sorted(
        FLANKS,
        key=lambda flank: min(0, flank_results[flank]["melee_margin"]) + min(0, flank_results[flank]["ranged_margin"]),
    )

    advice: list[str] = []

    for flank in flank_order:
        result = flank_results[flank]
        flank_advice: list[str] = []

        melee_deficit = max(0.0, -result["melee_margin"])
        ranged_deficit = max(0.0, -result["ranged_margin"])

        if ranged_deficit > 0:
            picks, shortfall = allocate_units(reserve_pool, "ranged_def", ranged_deficit, result["ranged_multiplier"])
            if picks:
                flank_advice.append(f"На {result['label']} докинь стрелков: {format_pick_list(picks)}.")
            if shortfall > 0:
                flank_advice.append(
                    f"После резерва на {result['label']} не хватает {round(shortfall, 2)} дальней защиты. Проверь орудия атакующего и бонусы наместника."
                )

        if melee_deficit > 0:
            picks, shortfall = allocate_units(reserve_pool, "melee_def", melee_deficit, result["melee_multiplier"])
            if picks:
                flank_advice.append(f"На {result['label']} усили ближнюю защиту: {format_pick_list(picks)}.")
            if shortfall > 0:
                flank_advice.append(
                    f"После резерва на {result['label']} не хватает {round(shortfall, 2)} ближней защиты. Нужен сильнее гарнизон или структура."
                )

        if not flank_advice:
            flank_advice.append(f"{result['label'].capitalize()} держится стабильно по текущему сценарию атаки.")

        result["advice"] = flank_advice
        advice.extend(flank_advice)

    weakest_flank = min(FLANKS, key=lambda flank: flank_results[flank]["total_margin"])
    held_flanks = [flank for flank in FLANKS if flank_results[flank]["wall_held"]]
    breached_flanks = [flank for flank in FLANKS if flank_results[flank]["wall_breached"]]
    unused_reserve = [
        {"name": unit["name"], "reserve": unit["reserve"]}
        for unit in reserve_pool
        if unit["reserve"] > 0
    ]

    total_tool_effects = combine_all_tool_effects(tool_totals)
    total_defense_tool_effects = combine_all_defense_tool_effects(defense_tool_totals)
    average_defender_unit_power = overview["base_total_power"] / overview["total_units"] if overview["total_units"] else 0.0
    base_total_attack = sum(item["attack"] for item in selected_attack_units)
    boosted_total_attack = 0.0
    used_waves = sorted(
        {
            str(item["wave"])
            for item in selected_attack_units
            if str(item.get("wave") or "").strip()
        },
        key=lambda value: int(value) if str(value).isdigit() else 999,
    )
    for flank in FLANKS:
        for wave in attack_wave_totals.get(flank, {}).keys():
            wave_data = attack_wave_totals[flank][wave]
            wave_effects = merge_wave_tool_effects(wave_tool_totals, flank, wave)
            attack_side_bonus = commander["overall_bonus"] + (commander["center_bonus"] if flank == "center" else commander["flank_bonus"])
            boosted_total_attack += wave_data["melee_attack"] * (1 + (wave_effects["melee_attack_bonus"] + wave_effects["global_attack_bonus"] + commander["melee_bonus"] + attack_side_bonus) / 100)
            boosted_total_attack += wave_data["ranged_attack"] * (1 + (wave_effects["ranged_attack_bonus"] + wave_effects["global_attack_bonus"] + commander["ranged_bonus"] + attack_side_bonus) / 100)

    breach_attack_power = sum(flank_results[flank]["attack_power_after_wall"] for flank in breached_flanks)
    breach_attackers = sum(flank_results[flank]["attacker_survivors"] for flank in breached_flanks)
    breached_melee_attackers = sum(flank_results[flank]["attacker_melee_survivors"] for flank in breached_flanks)
    breached_ranged_attackers = sum(flank_results[flank]["attacker_ranged_survivors"] for flank in breached_flanks)
    reserve_units = sum(unit["reserve"] for unit in units)
    reserve_power = sum(unit["reserve"] * (unit["melee_def"] + unit["ranged_def"]) for unit in units)
    wall_support_power = sum(flank_results[flank]["defense_power_after_wall"] for flank in FLANKS) * 0.35
    courtyard_defender_units = reserve_units + round(sum(flank_results[flank]["defender_survivors"] for flank in FLANKS) * 0.35)
    courtyard_tool_effects = merge_defense_tool_effects(defense_tool_totals, "courtyard")
    attackers_killed_by_def_tools = round(courtyard_tool_effects["kill_attacking_melee_yard"] + courtyard_tool_effects["kill_attacking_ranged_yard"] + courtyard_tool_effects["kill_attacking_any_yard"])
    defenders_killed_by_attack_tools = round(total_tool_effects["courtyard_melee_kills"] + total_tool_effects["courtyard_ranged_kills"] + total_tool_effects["courtyard_defender_kills"])
    breach_attackers_after_tools = max(0, breach_attackers - attackers_killed_by_def_tools)
    courtyard_defenders_after_tools = max(0, courtyard_defender_units - defenders_killed_by_attack_tools)
    attacker_avg_power_per_unit = breach_attack_power / breach_attackers if breach_attackers else 0.0
    courtyard_attack_bonus_percent = commander["overall_bonus"] + commander["courtyard_bonus"] + total_tool_effects["courtyard_power_bonus"]
    courtyard_attack_power = max(0.0, (breach_attackers_after_tools * attacker_avg_power_per_unit) * (1 + courtyard_attack_bonus_percent / 100))
    courtyard_defense_base = reserve_power + wall_support_power
    courtyard_defense_bonus_percent = governor["overall_bonus"] + governor["courtyard_bonus"] + total_defense_tool_effects["defense_power_bonus"] + courtyard_tool_effects["yard_defense_power_bonus"]
    courtyard_defense_power = max(0.0, (courtyard_defense_base * (1 + courtyard_defense_bonus_percent / 100)) - (defenders_killed_by_attack_tools * average_defender_unit_power))
    if courtyard_attack_power <= 0:
        courtyard_attacker_loss_ratio = 0.0
        courtyard_defender_loss_ratio = 0.0
    elif courtyard_defense_power <= 0:
        courtyard_attacker_loss_ratio = 0.0
        courtyard_defender_loss_ratio = 1.0
    else:
        courtyard_dominance = courtyard_attack_power / courtyard_defense_power
        courtyard_defender_loss_ratio = min(1.0, 0.55 * courtyard_dominance)
        courtyard_attacker_loss_ratio = min(1.0, 0.55 / max(courtyard_dominance, 0.01))
    courtyard_attacker_losses = min(breach_attackers_after_tools, round(breach_attackers_after_tools * courtyard_attacker_loss_ratio))
    courtyard_defender_losses = min(courtyard_defenders_after_tools, round(courtyard_defenders_after_tools * courtyard_defender_loss_ratio))
    castle_falls = courtyard_attack_power > courtyard_defense_power and breach_attack_power > 0
    attack_recommendations: list[str] = []
    weakest_attack_target = min(FLANKS, key=lambda flank: flank_results[flank]["final_melee_defense"] + flank_results[flank]["final_ranged_defense"])
    attack_recommendations.append(f"Главная точка давления для атаки: {FLANK_LABELS[weakest_attack_target]}. Там суммарная защита ниже остальных.")
    if flank_results[weakest_attack_target]["final_ranged_defense"] >= flank_results[weakest_attack_target]["final_melee_defense"]:
        attack_recommendations.append("На слабом участке защита опирается на дальний деф. Лучше заходят щиты, маски захватчика и дальнобойный офф.")
    else:
        attack_recommendations.append("На слабом участке больше ближней защиты. Усиливай мили-офф, факелы и общий буст урона по стене.")
    if governor["wall_defense"] > 0:
        attack_recommendations.append("Если атакуешь фланги, используй лестницы или башни: у защитника есть бонус стены.")
    if governor["gate_defense"] > 0 or governor["moat_defense"] > 0:
        attack_recommendations.append("Если давишь центр, усили таран и мост: ворота и ров ещё дают защитнику ценность.")
    if not selected_defense_tools:
        attack_recommendations.append("У защитника не указаны оборонительные орудия. Агрессивная атака в стену и двор обычно окупается лучше.")
    elif courtyard_tool_effects["kill_attacking_any_yard"] or courtyard_tool_effects["kill_attacking_melee_yard"] or courtyard_tool_effects["kill_attacking_ranged_yard"]:
        attack_recommendations.append("Во дворе у защитника есть убийства по атаке. Для добивания замка нужно больше живого оффа после стены или сильнее бонус двора.")

    return {
        "summary": {
            "overall_defense": round(overall_defense, 2),
            "overall_enemy_attack": round(overall_enemy_attack, 2),
            "overall_margin": round(overall_defense - overall_enemy_attack, 2),
            "weakest_flank": FLANK_LABELS[weakest_flank],
            "held_flanks": [FLANK_LABELS[flank] for flank in held_flanks],
            "breached_flanks": [FLANK_LABELS[flank] for flank in breached_flanks],
            "castle_falls": castle_falls,
        },
        "castle_overview": overview,
        "courtyard": {
            "estimated_power": round(courtyard_defense_power, 2),
            "estimated_losses": defenders_killed_by_attack_tools + courtyard_defender_losses,
            "bonus_percent": round(courtyard_defense_bonus_percent, 2),
            "breach_attack_power": round(courtyard_attack_power, 2),
            "breach_attackers": breach_attackers_after_tools,
            "defenders_in_courtyard": courtyard_defenders_after_tools,
            "attackers_killed_by_def_tools": attackers_killed_by_def_tools,
            "defenders_killed_by_attack_tools": defenders_killed_by_attack_tools,
            "attacker_losses_in_courtyard": courtyard_attacker_losses,
            "defender_losses_in_courtyard": courtyard_defender_losses,
            "castle_falls": castle_falls,
        },
        "attack_tools": {
            "selected": selected_tools,
            "totals": {field: round(total_tool_effects[field], 2) for field in TOOL_EFFECT_FIELDS if total_tool_effects[field]},
        },
        "defense_tools": {
            "selected": selected_defense_tools,
            "totals": {field: round(total_defense_tool_effects[field], 2) for field in DEFENSE_TOOL_EFFECT_FIELDS if total_defense_tool_effects[field]},
        },
        "attack_units": {
            "selected": selected_attack_units,
        },
        "attack_summary": {
            "configured_max_waves": max_waves,
            "used_waves": used_waves,
            "used_waves_count": len(used_waves),
            "base_total_attack": round(base_total_attack, 2),
            "boosted_total_attack": round(boosted_total_attack, 2),
            "breached_attackers": breach_attackers_after_tools,
            "surviving_melee": max(0, breached_melee_attackers - min(breached_melee_attackers, attackers_killed_by_def_tools)),
            "surviving_ranged": max(0, breached_ranged_attackers - min(max(0, attackers_killed_by_def_tools - breached_melee_attackers), breached_ranged_attackers)),
        },
        "losses": {
            "attacker_wall_losses": total_attacker_wall_losses,
            "defender_wall_losses": total_defender_wall_losses,
            "attacker_total_losses": total_attacker_wall_losses + courtyard_attacker_losses + attackers_killed_by_def_tools,
            "defender_total_losses": total_defender_wall_losses + defenders_killed_by_attack_tools + courtyard_defender_losses,
        },
        "flanks": flank_results,
        "reserve_left": unused_reserve,
        "advice": advice,
        "attack_recommendations": attack_recommendations,
        "warnings": warnings,
    }
