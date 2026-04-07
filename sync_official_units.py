from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.request import urlopen

ITEM_VERSION_URL = "https://empire-html5.goodgamestudios.com/default/items/ItemsVersion.properties"
ITEMS_BASE_URL = "https://empire-html5.goodgamestudios.com/default/items"
LANGUAGE_VERSION_URL = "https://langserv.public.ggs-ep.com/12/fr/@metadata"
LANGUAGE_BASE_URL = "https://langserv.public.ggs-ep.com"
GAME_INDEX_URL = "https://empire-html5.goodgamestudios.com/default/index.html"
ASSET_BASE_URL = "https://empire-html5.goodgamestudios.com/default/assets/itemassets/"
OUTPUT_FILE = Path(__file__).resolve().parent / "data" / "official_units_catalog.json"


def fetch_text(url: str) -> str:
    with urlopen(url, timeout=60) as response:
        return response.read().decode("utf-8")


def fetch_json(url: str) -> Any:
    return json.loads(fetch_text(url))


def normalize_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def lowercase_keys_recursive(value: Any) -> Any:
    if isinstance(value, list):
        return [lowercase_keys_recursive(item) for item in value]
    if isinstance(value, dict):
        return {str(key).lower(): lowercase_keys_recursive(item) for key, item in value.items()}
    return value


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
    item_version = get_item_version()
    payload = fetch_json(f"{ITEMS_BASE_URL}/items_v{item_version}.json")
    return lowercase_keys_recursive(payload)


def load_language(lang_code: str = "ru") -> dict[str, Any]:
    lang_version = get_language_version()
    payload = fetch_json(f"{LANGUAGE_BASE_URL}/12@{lang_version}/{lang_code}/*")
    return lowercase_keys_recursive(payload)


def get_dll_url() -> str:
    html = fetch_text(GAME_INDEX_URL)
    match = re.search(r"<link\s+id=[\"']dll[\"']\s+rel=[\"']preload[\"']\s+href=[\"']([^\"']+)[\"']", html, re.IGNORECASE)
    if not match:
        raise RuntimeError("Не удалось найти DLL с ассетами")
    return f"https://empire-html5.goodgamestudios.com/default/{match.group(1)}"


def build_unit_image_map() -> dict[str, str]:
    dll_text = fetch_text(get_dll_url())
    matches = re.finditer(r"Units\/[^\/]+\/[^\/]+\/[^\/]+?--\d+", dll_text)
    image_map: dict[str, str] = {}
    for match in matches:
        raw_path = match.group(0)
        filename = raw_path.split("/")[-1]
        key = normalize_name(filename.split("--")[0])
        image_map[key] = f"{ASSET_BASE_URL}{raw_path}.webp"
    return image_map


def get_number(unit: dict[str, Any], *keys: str) -> int | float | None:
    for key in keys:
        value = unit.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        try:
            number = float(text.replace(",", "."))
        except ValueError:
            continue
        if number.is_integer():
            return int(number)
        return number
    return None


def get_supply(unit: dict[str, Any]) -> int | float | None:
    return get_number(unit, "foodsupply", "meadsupply", "beefsupply")


def get_unit_display_name(unit: dict[str, Any], lang: dict[str, Any]) -> str:
    raw_name = str(unit.get("name") or "").strip()
    raw_type = str(unit.get("type") or "").strip()
    type_key = f"{raw_type.lower()}_name" if raw_type else ""
    name_key = f"{raw_name.lower()}_name" if raw_name else ""
    return str(lang.get(type_key) or raw_type or lang.get(name_key) or raw_name or "Unit")


def get_unit_image_url(unit: dict[str, Any], image_map: dict[str, str]) -> str:
    raw_name = str(unit.get("name") or "")
    raw_type = str(unit.get("type") or "")
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

    entries = list(image_map.items())
    for key, url in entries:
        if type_norm in key and name_norm in key and "unit" in key:
            return url
    for key, url in entries:
        if type_norm in key and "unit" in key:
            return url
    for key, url in entries:
        if name_norm in key and "unit" in key:
            return url
    return ""


def is_tool(unit: dict[str, Any]) -> bool:
    joined = " ".join(str(unit.get(field) or "").lower() for field in ("name", "type", "group"))
    return "tool" in joined or "workshop" in joined


def build_category(unit: dict[str, Any]) -> str:
    group = str(unit.get("group") or "").strip()
    typ = str(unit.get("typ") or unit.get("type") or "").strip()
    if group and typ:
        return f"{group} / {typ}"
    return group or typ or "Unknown"


def build_attack_value(melee_attack: int | float | None, ranged_attack: int | float | None) -> int | float | None:
    if ranged_attack and ranged_attack > 0:
        return ranged_attack
    return melee_attack


def build_role(melee_attack: int | float | None, ranged_attack: int | float | None) -> str:
    if (ranged_attack or 0) > (melee_attack or 0):
        return "ranged"
    return "melee"


def build_display_name(base_name: str, unit: dict[str, Any]) -> str:
    level = str(unit.get("level") or "").strip()
    if level and level not in {"0", "-"}:
        return f"{base_name} (ур. {level})"
    return base_name


def build_catalog() -> list[dict[str, Any]]:
    items = load_items()
    lang = load_language("ru")
    image_map = build_unit_image_map()
    raw_units = items.get("units") or []
    catalog: list[dict[str, Any]] = []

    for unit in raw_units:
        if not isinstance(unit, dict) or is_tool(unit):
            continue

        melee_attack = get_number(unit, "meleeattack")
        ranged_attack = get_number(unit, "rangeattack", "rangedattack", "attackrange", "rangedstrength")
        melee_def = get_number(unit, "meleedefence")
        ranged_def = get_number(unit, "rangedefence")
        if not any(value not in (None, 0) for value in (melee_attack, ranged_attack, melee_def, ranged_def)):
            continue

        display_name_base = get_unit_display_name(unit, lang)
        catalog.append(
            {
                "wod_id": str(unit.get("wodid") or unit.get("id") or ""),
                "name": str(unit.get("type") or unit.get("name") or display_name_base),
                "display_name": build_display_name(display_name_base, unit),
                "raw_name": str(unit.get("name") or ""),
                "raw_type": str(unit.get("type") or ""),
                "group": str(unit.get("group") or ""),
                "category": build_category(unit),
                "level": str(unit.get("level") or ""),
                "role": build_role(melee_attack, ranged_attack),
                "attack": build_attack_value(melee_attack, ranged_attack),
                "attack_strength": build_attack_value(melee_attack, ranged_attack),
                "melee_attack": melee_attack,
                "melee_strength": melee_attack,
                "ranged_attack": ranged_attack,
                "ranged_strength": ranged_attack,
                "melee_def": melee_def,
                "ranged_def": ranged_def,
                "looting": get_number(unit, "lootvalue"),
                "movement": get_number(unit, "speed"),
                "food": get_supply(unit),
                "might": get_number(unit, "mightvalue", "might"),
                "image_url": get_unit_image_url(unit, image_map),
                "source": "official",
                "status": "official",
            }
        )

    catalog.sort(key=lambda item: (str(item.get("category") or ""), str(item.get("display_name") or item.get("name") or ""), str(item.get("level") or "")))
    return catalog


def main() -> None:
    catalog = build_catalog()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(catalog)} units to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
