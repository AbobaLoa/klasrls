from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.request import urlopen

ITEM_VERSION_URL = "https://empire-html5.goodgamestudios.com/default/items/ItemsVersion.properties"
ITEMS_BASE_URL = "https://empire-html5.goodgamestudios.com/default/items"
LANGUAGE_VERSION_URL = "https://langserv.public.ggs-ep.com/12/fr/@metadata"
LANGUAGE_BASE_URL = "https://langserv.public.ggs-ep.com"
GAME_INDEX_URL = "https://empire-html5.goodgamestudios.com/default/index.html"
ASSET_BASE_URL = "https://empire-html5.goodgamestudios.com/default/assets/itemassets/"
OUTPUT_FILE = Path(__file__).resolve().parent / "data" / "official_tools_catalog.json"


EFFECT_FIELD_MAP = {
    "additionalwaves": "extra_waves",
    "attackbonus": "global_attack_bonus",
    "attackboostyard": "courtyard_power_bonus",
    "killdefendingmeleetroopsyard": "courtyard_melee_kills",
    "killdefendingrangedtroopsyard": "courtyard_ranged_kills",
    "killdefendinganytroopsyard": "courtyard_defender_kills",
    "bonuswallcapacity": "raw_bonus_wall_capacity",
    "bonusdefencepower": "raw_bonus_defence_power",
    "bonusyarddefensepower": "raw_bonus_yard_defense_power",
    "killattackingmeleetroopsyard": "raw_kill_attacking_melee_yard",
    "killattackingrangedtroopsyard": "raw_kill_attacking_ranged_yard",
    "killattackinganytroopsyard": "raw_kill_attacking_any_yard",
    "infectionratebasemalus": "raw_infection_rate_base_malus",
    "reserveunitkill": "raw_reserve_unit_kill",
    "raidbosswallregenerationdelayall": "raw_raidboss_wall_regen_delay_all",
    "raidbosswallregenerationdelayfront": "raw_raidboss_wall_regen_delay_front",
    "raidbosswallregenerationdelayleft": "raw_raidboss_wall_regen_delay_left",
    "raidbosswallregenerationdelayright": "raw_raidboss_wall_regen_delay_right",
}

DIRECT_FIELD_MAP = {
    "wallbonus": "wall_reduction",
    "gatebonus": "gate_reduction",
    "moatbonus": "moat_reduction",
    "defrangebonus": "ranged_defense_reduction",
    "offrangebonus": "ranged_attack_bonus",
    "offmeleebonus": "melee_attack_bonus",
    "famebonus": "glory_bonus",
    "amountperwave": "tool_limit",
    "defmeleebonus": "raw_def_melee_bonus",
}

DEFAULT_NUMERIC_FIELDS = (
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
    "tool_limit",
    "raw_def_melee_bonus",
    "raw_bonus_wall_capacity",
    "raw_bonus_defence_power",
    "raw_bonus_yard_defense_power",
    "raw_kill_attacking_melee_yard",
    "raw_kill_attacking_ranged_yard",
    "raw_kill_attacking_any_yard",
    "raw_infection_rate_base_malus",
    "raw_reserve_unit_kill",
    "raw_raidboss_wall_regen_delay_all",
    "raw_raidboss_wall_regen_delay_front",
    "raw_raidboss_wall_regen_delay_left",
    "raw_raidboss_wall_regen_delay_right",
)


def fetch_text(url: str) -> str:
    with urlopen(url, timeout=60) as response:
        return response.read().decode("utf-8")


def fetch_json(url: str) -> Any:
    return json.loads(fetch_text(url))


def lowercase_keys_recursive(value: Any) -> Any:
    if isinstance(value, list):
        return [lowercase_keys_recursive(item) for item in value]
    if isinstance(value, dict):
        return {str(key).lower(): lowercase_keys_recursive(item) for key, item in value.items()}
    return value


def normalize_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def get_item_version() -> str:
    text = fetch_text(ITEM_VERSION_URL)
    match = re.search(r"CastleItemXMLVersion=(\d+\.\d+)", text)
    if not match:
        raise RuntimeError("Не удалось определить версию items JSON")
    return match.group(1)


def get_language_version() -> str:
    payload = fetch_json(LANGUAGE_VERSION_URL)
    return str(payload["@metadata"]["versionNo"])


def load_items() -> dict[str, Any]:
    version = get_item_version()
    payload = fetch_json(f"{ITEMS_BASE_URL}/items_v{version}.json")
    return lowercase_keys_recursive(payload)


def load_language(lang_code: str = "ru") -> dict[str, Any]:
    version = get_language_version()
    payload = fetch_json(f"{LANGUAGE_BASE_URL}/12@{version}/{lang_code}/*")
    return lowercase_keys_recursive(payload)


def get_dll_url() -> str:
    html = fetch_text(GAME_INDEX_URL)
    match = re.search(r"<link\s+id=[\"']dll[\"']\s+rel=[\"']preload[\"']\s+href=[\"']([^\"']+)[\"']", html, re.IGNORECASE)
    if not match:
        raise RuntimeError("Не удалось найти DLL с ассетами")
    return f"https://empire-html5.goodgamestudios.com/default/{match.group(1)}"


def build_tool_image_map() -> dict[str, str]:
    dll_text = fetch_text(get_dll_url())
    matches = re.finditer(r"Units\/[^\/]+\/[^\/]+\/[^\/]+?--\d+", dll_text)
    image_map: dict[str, str] = {}
    for match in matches:
        raw_path = match.group(0)
        filename = raw_path.split("/")[-1]
        key = normalize_name(filename.split("--")[0])
        image_map[key] = f"{ASSET_BASE_URL}{raw_path}.webp"
    return image_map


def get_number(value: Any) -> int | float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        number = float(text.replace(",", "."))
    except ValueError:
        return None
    if number.is_integer():
        return int(number)
    return number


def get_tool_display_name(tool: dict[str, Any], lang: dict[str, Any]) -> str:
    raw_name = str(tool.get("name") or "").strip()
    raw_type = str(tool.get("type") or "").strip()
    type_key = f"{raw_type.lower()}_name" if raw_type else ""
    name_key = f"{raw_name.lower()}_name" if raw_name else ""
    return str(lang.get(type_key) or raw_type or lang.get(name_key) or raw_name or "Орудие")


def get_tool_image_url(tool: dict[str, Any], image_map: dict[str, str]) -> str:
    raw_name = str(tool.get("name") or "")
    raw_type = str(tool.get("type") or "")
    if not raw_name or not raw_type:
        return ""

    name_norm = normalize_name(raw_name)
    type_norm = normalize_name(raw_type)
    exact_keys = [
        normalize_name(f"{raw_name}_unit_{raw_type}"),
        normalize_name(f"{raw_type}_unit_{raw_name}"),
        type_norm,
        name_norm,
    ]
    for key in exact_keys:
        if key in image_map:
            return image_map[key]

    for key, url in image_map.items():
        if type_norm in key and name_norm in key and "unit" in key:
            return url
    for key, url in image_map.items():
        if type_norm in key and "unit" in key:
            return url
    for key, url in image_map.items():
        if name_norm in key and "unit" in key:
            return url
    return ""


def is_tool(unit: dict[str, Any]) -> bool:
    joined = " ".join(str(unit.get(field) or "").lower() for field in ("name", "type", "group", "typ"))
    return "tool" in joined or "workshop" in joined


def build_side(tool: dict[str, Any]) -> str:
    typ = str(tool.get("typ") or "").strip().lower()
    if typ == "attack":
        return "attack"
    if typ == "defence":
        return "defence"
    return typ or "unknown"


def build_category(tool: dict[str, Any], normalized_fields: dict[str, Any]) -> str:
    side = build_side(tool)
    categories: list[str] = [side]
    if normalized_fields.get("wall_reduction"):
        categories.append("wall")
    if normalized_fields.get("gate_reduction"):
        categories.append("gate")
    if normalized_fields.get("moat_reduction"):
        categories.append("moat")
    if normalized_fields.get("ranged_defense_reduction"):
        categories.append("ranged_defense")
    if normalized_fields.get("melee_attack_bonus"):
        categories.append("melee_attack")
    if normalized_fields.get("ranged_attack_bonus"):
        categories.append("ranged_attack")
    if normalized_fields.get("extra_waves"):
        categories.append("waves")
    if normalized_fields.get("courtyard_melee_kills") or normalized_fields.get("courtyard_ranged_kills") or normalized_fields.get("courtyard_defender_kills"):
        categories.append("courtyard_kills")
    if normalized_fields.get("courtyard_power_bonus"):
        categories.append("courtyard_power")
    if normalized_fields.get("glory_bonus"):
        categories.append("glory")
    if len(categories) == 1:
        categories.append(str(tool.get("type") or tool.get("name") or "tool").lower())
    return " / ".join(categories)


def init_numeric_fields() -> dict[str, int | float]:
    return {field: 0 for field in DEFAULT_NUMERIC_FIELDS}


def parse_effects(tool: dict[str, Any], effect_defs: dict[str, dict[str, Any]]) -> tuple[dict[str, int | float], list[dict[str, Any]]]:
    mapped = init_numeric_fields()
    raw_effects: list[dict[str, Any]] = []
    text = str(tool.get("effects") or "").strip()
    if not text:
        return mapped, raw_effects

    for chunk in [piece.strip() for piece in text.split(",") if piece.strip()]:
        effect_id, _, payload = chunk.partition("&")
        definition = effect_defs.get(str(effect_id).strip(), {})
        effect_name = str(definition.get("name") or f"effect_{effect_id}")
        numeric_value = get_number(payload) or 0
        raw_effects.append(
            {
                "effect_id": str(effect_id).strip(),
                "effect_name": effect_name,
                "value": numeric_value,
            }
        )
        target_field = EFFECT_FIELD_MAP.get(effect_name.lower())
        if target_field:
            mapped[target_field] += numeric_value
    return mapped, raw_effects


def build_catalog() -> list[dict[str, Any]]:
    items = load_items()
    lang = load_language("ru")
    image_map = build_tool_image_map()
    effect_defs = {str(effect.get("effectid")): effect for effect in (items.get("effects") or []) if isinstance(effect, dict)}
    raw_units = items.get("units") or []
    entries: list[dict[str, Any]] = []

    for tool in raw_units:
        if not isinstance(tool, dict) or not is_tool(tool):
            continue

        mapped = init_numeric_fields()
        for source_key, target_key in DIRECT_FIELD_MAP.items():
            mapped[target_key] += get_number(tool.get(source_key)) or 0

        effect_mapped, raw_effects = parse_effects(tool, effect_defs)
        for key, value in effect_mapped.items():
            mapped[key] += value

        side = build_side(tool)
        display_name = get_tool_display_name(tool, lang)
        level = get_number(tool.get("level"))

        entry: dict[str, Any] = {
            "wod_id": str(tool.get("wodid") or tool.get("id") or ""),
            "name": str(tool.get("type") or tool.get("name") or display_name),
            "display_name": display_name,
            "raw_name": str(tool.get("name") or ""),
            "raw_type": str(tool.get("type") or ""),
            "group": str(tool.get("group") or ""),
            "side": side,
            "typ": str(tool.get("typ") or ""),
            "category": build_category(tool, mapped),
            "level": level,
            "image_url": get_tool_image_url(tool, image_map),
            "raw_effects": raw_effects,
            "source": "official",
            "status": "official",
        }
        entry.update(mapped)
        entries.append(entry)

    counts = Counter(entry["display_name"] for entry in entries)
    for entry in entries:
        if counts[entry["display_name"]] > 1:
            if entry.get("level"):
                entry["display_name"] = f"{entry['display_name']} ур.{entry['level']}"
            else:
                entry["display_name"] = f"{entry['display_name']} [ID {entry['wod_id']}]"

    entries.sort(
        key=lambda item: (
            str(item.get("side") or ""),
            str(item.get("category") or ""),
            str(item.get("display_name") or item.get("name") or ""),
            item.get("level") or 0,
            str(item.get("wod_id") or ""),
        )
    )
    return entries


def main() -> None:
    catalog = build_catalog()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(catalog)} tools to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
