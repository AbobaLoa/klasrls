from __future__ import annotations

import json
import re
import ssl
from pathlib import Path
from typing import Any
from urllib.request import urlopen

ITEM_VERSION_URL = "https://empire-html5.goodgamestudios.com/default/items/ItemsVersion.properties"
ITEMS_BASE_URL = "https://empire-html5.goodgamestudios.com/default/items"
LANGUAGE_VERSION_URL = "https://langserv.public.ggs-ep.com/12/fr/@metadata"
LANGUAGE_BASE_URL = "https://langserv.public.ggs-ep.com"
GAME_INDEX_URL = "https://empire-html5.goodgamestudios.com/default/index.html"
ASSET_BASE_URL = "https://empire-html5.goodgamestudios.com/default/assets/itemassets/"
OUTPUT_FILE = Path(__file__).resolve().parent / "data" / "official_equipment_sets_catalog.json"
DEFAULT_MIN_SET_ID = 1084

SLOT_ORDER = {
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "6": 5,
    "gem": 6,
}


def fetch_text(url: str) -> str:
    context = ssl._create_unverified_context()
    with urlopen(url, timeout=120, context=context) as response:
        return response.read().decode("utf-8")


def fetch_json(url: str) -> Any:
    return json.loads(fetch_text(url))


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


def load_items() -> dict[str, Any]:
    version = get_item_version()
    payload = fetch_json(f"{ITEMS_BASE_URL}/items_v{version}.json")
    return lowercase_keys_recursive(payload)


def get_language_version() -> str:
    payload = fetch_json(LANGUAGE_VERSION_URL)
    return str(payload["@metadata"]["versionNo"])


def load_language(lang_code: str = "ru") -> dict[str, Any]:
    version = get_language_version()
    payload = fetch_json(f"{LANGUAGE_BASE_URL}/12@{version}/{lang_code}/*")
    return lowercase_keys_recursive(payload)


def get_dll_url() -> str:
    html = fetch_text(GAME_INDEX_URL)
    match = re.search(r"<link\s+id=[\"']dll[\"']\s+rel=[\"']preload[\"']\s+href=[\"']([^\"']+)[\"']", html, re.IGNORECASE)
    if not match:
        raise RuntimeError("DLL preload not found")
    return f"https://empire-html5.goodgamestudios.com/default/{match.group(1)}"


def parse_equipment_unique_images(dll_text: str) -> dict[str, str]:
    regex_equipment = re.finditer(r"Equipment/Uniques/Item_Unique_(\d+)/Item_Unique_\1--\d+", dll_text)
    regex_hero = re.finditer(r"Equipment/Heroes/Hero_Unique_(\d+)/Hero_Unique_\1--\d+", dll_text)
    result: dict[str, str] = {}
    for match in regex_equipment:
        result[str(match.group(1))] = f"{ASSET_BASE_URL}{match.group(0)}.webp"
    for match in regex_hero:
        result.setdefault(str(match.group(1)), f"{ASSET_BASE_URL}{match.group(0)}.webp")
    return result


def parse_unique_gem_images(dll_text: str) -> dict[str, str]:
    regex = re.finditer(r"Equipment/UniqueGems/Item_Gem_Unique_(\d+)/Item_Gem_Unique_\1--\d+", dll_text)
    return {str(match.group(1)): f"{ASSET_BASE_URL}{match.group(0)}.webp" for match in regex}


def build_image_maps() -> tuple[dict[str, str], dict[str, str]]:
    dll_text = fetch_text(get_dll_url())
    return parse_equipment_unique_images(dll_text), parse_unique_gem_images(dll_text)


def build_lookup(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        value = item.get(key)
        if value is not None:
            result[str(value)] = item
    return result


def clean_template_text(text: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\{\d+\}", "", str(text or ""))).strip()


def normalize_set_id(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text or text == "0":
        return None
    return text


def is_default_set_id(set_id: str) -> bool:
    try:
        return int(set_id) >= DEFAULT_MIN_SET_ID
    except ValueError:
        return False


def get_effect_context(data: dict[str, Any], lang: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], set[str]]:
    effect_definitions = build_lookup(data.get("effects", []), "effectid")
    percent_ids: set[str] = set()
    for effect_id, effect in effect_definitions.items():
        base = str(effect.get("name") or "").lower()
        possible_keys = [
            f"equip_effect_description_{base}",
            f"ci_effect_{base}",
            f"effect_name_{base}",
            f"effect_desc_{base}",
        ]
        is_percent = False
        for key in possible_keys:
            if "%" in str(lang.get(key) or "") or "%" in str(lang.get(f"{key}_tt") or ""):
                is_percent = True
                break
        if is_percent and "unboosted" not in base:
            percent_ids.add(effect_id)
    return effect_definitions, percent_ids


def split_effect_token(token: str) -> list[dict[str, Any]]:
    effect_id_raw, _, value_raw = str(token or "").partition("&")
    effect_id = effect_id_raw.strip()
    if not effect_id:
        return []
    value_part = value_raw.strip()
    if "#" in value_part:
        nested: list[dict[str, Any]] = []
        for part in [piece.strip() for piece in value_part.split("#") if piece.strip() and "+" in piece]:
            arg_id_raw, nested_value_raw = part.split("+", 1)
            arg_id = str(arg_id_raw or "").strip()
            try:
                nested_value = float(nested_value_raw)
            except ValueError:
                continue
            nested.append({"id": effect_id, "value": nested_value, "arg_id": arg_id})
        return nested
    numeric_part = value_part
    arg_id: str | None = None
    if "+" in numeric_part:
        arg_raw, actual = numeric_part.split("+", 1)
        arg_id = str(arg_raw or "").strip() or None
        numeric_part = actual
    try:
        parsed = float(numeric_part)
    except ValueError:
        parsed = 0.0
    return [{"id": effect_id, "value": parsed, "arg_id": arg_id}]


def resolve_effect_id(effect_id: str, equipment_effect_to_effect_id: dict[str, str], effect_definitions: dict[str, dict[str, Any]], source_type: str = "auto") -> str:
    raw = str(effect_id or "").strip()
    if not raw:
        return raw
    mapped = equipment_effect_to_effect_id.get(raw)
    has_direct = raw in effect_definitions
    if source_type in {"equipment", "set_bonus"}:
        return str(mapped or raw)
    if source_type == "gem":
        return raw if has_direct else str(mapped or raw)
    return raw if has_direct else str(mapped or raw)


def get_effect_label(effect_id: str, equipment_effect_to_effect_id: dict[str, str], effect_definitions: dict[str, dict[str, Any]], lang: dict[str, Any], source_type: str = "auto") -> str:
    resolved_effect_id = resolve_effect_id(effect_id, equipment_effect_to_effect_id, effect_definitions, source_type)
    effect_def = effect_definitions.get(str(resolved_effect_id), {})
    raw_name = str(effect_def.get("name") or "").strip()
    if not raw_name:
        return f"Effect {resolved_effect_id or effect_id}"
    key = raw_name.lower()
    normalized_key = "additionalwaves" if key == "charmboost" else key
    stripped_shape_key = normalized_key[:-12] if normalized_key.endswith("shapeshifter") else None
    candidates = [
        f"equip_effect_description_{stripped_shape_key}" if stripped_shape_key else None,
        f"ci_effect_{stripped_shape_key}" if stripped_shape_key else None,
        f"effect_name_{stripped_shape_key}" if stripped_shape_key else None,
        f"equip_effect_description_short_{stripped_shape_key}" if stripped_shape_key else None,
        stripped_shape_key,
        f"equip_effect_description_{normalized_key}",
        f"ci_effect_{normalized_key}",
        f"effect_name_{normalized_key}",
        f"effect_desc_{normalized_key}",
        f"equip_effect_description_short_{normalized_key}",
        normalized_key,
        f"equip_effect_description_{key}",
        f"ci_effect_{key}",
        f"effect_name_{key}",
        f"effect_desc_{key}",
        f"equip_effect_description_short_{key}",
        key,
    ]
    for candidate in [item for item in candidates if item]:
        value = str(lang.get(candidate) or "")
        if not value:
            continue
        if re.search(r"lost its powers|seems to have run out|örökség|elvesztette erejét", value, flags=re.IGNORECASE):
            continue
        return value
    return re.sub(r"_", " ", re.sub(r"([a-z])([A-Z])", r"\1 \2", raw_name)).strip()


def format_localized_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text


def format_effect_value(effect_id: str, value: float, equipment_effect_to_effect_id: dict[str, str], effect_definitions: dict[str, dict[str, Any]], percent_ids: set[str], source_type: str = "auto") -> str:
    resolved_effect_id = resolve_effect_id(effect_id, equipment_effect_to_effect_id, effect_definitions, source_type)
    is_percent = str(resolved_effect_id) in percent_ids
    sign = "+" if value > 0 else "-" if value < 0 else ""
    text = format_localized_number(abs(value) if sign else value)
    return f"{sign}{text}{'%' if is_percent else ''}"


def format_template_value(template: str, effect_id: str, value: float, equipment_effect_to_effect_id: dict[str, str], effect_definitions: dict[str, dict[str, Any]], percent_ids: set[str], source_type: str = "auto") -> str:
    resolved_effect_id = resolve_effect_id(effect_id, equipment_effect_to_effect_id, effect_definitions, source_type)
    is_percent = str(resolved_effect_id) in percent_ids
    abs_text = format_localized_number(abs(value))
    signed_text = f"+{abs_text}" if value > 0 else f"-{abs_text}" if value < 0 else "0"
    has_sign_placeholder = bool(re.search(r"[+\-]\s*\{0\}|\{0\}\s*[+\-]", template))
    has_percent_placeholder = bool(re.search(r"\{0\}\s*%|%\s*\{0\}", template))
    token = abs_text if has_sign_placeholder else signed_text
    if is_percent and not has_percent_placeholder:
        token += "%"
    return token


def normalize_effect_semantic_value(effect_id: str, value: float, equipment_effect_to_effect_id: dict[str, str], effect_definitions: dict[str, dict[str, Any]], lang: dict[str, Any], source_type: str = "auto") -> float:
    template = get_effect_label(effect_id, equipment_effect_to_effect_id, effect_definitions, lang, source_type)
    if re.search(r"-\s*\{0\}|\{0\}\s*-", template):
        return -abs(value)
    if re.search(r"\+\s*\{0\}|\{0\}\s*\+", template):
        return abs(value)
    return value


def get_unit_name_by_id(unit_id: str, units_by_id: dict[str, dict[str, Any]], lang: dict[str, Any]) -> str:
    unit = units_by_id.get(str(unit_id), {})
    if not unit:
        return str(unit_id)
    type_key = str(unit.get("type") or "").strip()
    if type_key:
        lang_key = f"{type_key}_name".lower()
        if lang.get(lang_key):
            return str(lang[lang_key])
    return str(unit.get("comment2") or unit.get("name") or unit.get("type") or unit_id)


def render_effect_line(effect_id: str, value: float, arg_id: str | None, equipment_effect_to_effect_id: dict[str, str], effect_definitions: dict[str, dict[str, Any]], percent_ids: set[str], lang: dict[str, Any], units_by_id: dict[str, dict[str, Any]], source_type: str = "auto") -> str:
    template = get_effect_label(effect_id, equipment_effect_to_effect_id, effect_definitions, lang, source_type)
    if "{0}" in template:
        token = format_template_value(template, effect_id, value, equipment_effect_to_effect_id, effect_definitions, percent_ids, source_type)
        text = template.replace("{0}", token)
        text = text.replace("{1}", get_unit_name_by_id(str(arg_id or ""), units_by_id, lang) if arg_id else "")
        text = text.replace("{2}", "")
        text = re.sub(r"\{\d+\}", "", text)
        text = re.sub(r"\s*\.$", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
    cleaned = clean_template_text(template)
    value_text = format_effect_value(effect_id, value, equipment_effect_to_effect_id, effect_definitions, percent_ids, source_type)
    return f"{cleaned}{'' if cleaned.endswith(':') else ':'} {value_text}"


def parse_effect_tokens(raw: Any, equipment_effect_to_effect_id: dict[str, str], effect_definitions: dict[str, dict[str, Any]], lang: dict[str, Any], units_by_id: dict[str, dict[str, Any]], source_type: str = "auto") -> list[dict[str, Any]]:
    tokens: list[dict[str, Any]] = []
    if not raw:
        return tokens
    for part in [piece.strip() for piece in str(raw).split(",") if piece.strip()]:
        for entry in split_effect_token(part):
            normalized_value = normalize_effect_semantic_value(entry["id"], float(entry["value"]), equipment_effect_to_effect_id, effect_definitions, lang, source_type)
            tokens.append({
                "effect_id": str(resolve_effect_id(entry["id"], equipment_effect_to_effect_id, effect_definitions, source_type)),
                "raw_effect_id": str(entry["id"]),
                "value": normalized_value,
                "arg_id": entry.get("arg_id"),
                "label": render_effect_line(entry["id"], normalized_value, entry.get("arg_id"), equipment_effect_to_effect_id, effect_definitions, set(), lang, units_by_id, source_type),
            })
    return tokens


def parse_effect_lines(raw: Any, equipment_effect_to_effect_id: dict[str, str], effect_definitions: dict[str, dict[str, Any]], percent_ids: set[str], lang: dict[str, Any], units_by_id: dict[str, dict[str, Any]], source_type: str = "auto") -> list[str]:
    lines: list[str] = []
    if not raw:
        return lines
    for part in [piece.strip() for piece in str(raw).split(",") if piece.strip()]:
        for entry in split_effect_token(part):
            normalized_value = normalize_effect_semantic_value(entry["id"], float(entry["value"]), equipment_effect_to_effect_id, effect_definitions, lang, source_type)
            lines.append(render_effect_line(entry["id"], normalized_value, entry.get("arg_id"), equipment_effect_to_effect_id, effect_definitions, percent_ids, lang, units_by_id, source_type))
    return lines


def get_localized_wearer_name(wearer_id: Any, wearer_by_id: dict[str, dict[str, Any]], lang: dict[str, Any]) -> str:
    wearer = wearer_by_id.get(str(wearer_id), {})
    raw = str(wearer.get("name") or "").lower()
    if "baron" in raw:
        return str(lang.get("equipment_itemtype_baron") or lang.get("dialog_alliancecrestgenerator_castellan_tab") or "Кастелян")
    if "general" in raw:
        return str(lang.get("equipment_itemtype_general") or lang.get("dialog_alliancecrestgenerator_commander_tab") or "Командующий")
    return str(wearer.get("name") or f"Wearer {wearer_id}")


def get_localized_slot_name(slot_id: Any, slot_by_id: dict[str, dict[str, Any]], lang: dict[str, Any]) -> str:
    slot = slot_by_id.get(str(slot_id), {})
    raw = str(slot.get("name") or "").lower()
    by_raw_to_filter_key = {
        "helmet": "filters_subfilter_1",
        "armor": "filters_subfilter_2",
        "weapon": "filters_subfilter_3",
        "artifact": "filters_subfilter_4",
        "look": "filters_subfilter_5",
        "skin": "filters_subfilter_5",
        "hero": "filters_subfilter_6",
        "heroes": "filters_subfilter_6",
    }
    mapped_key = by_raw_to_filter_key.get(raw)
    if mapped_key and lang.get(mapped_key):
        return str(lang[mapped_key])
    for key in (f"equipmentslot_name_{raw}", f"dialog_equipment_slot_{raw}", raw):
        if lang.get(key):
            return str(lang[key])
    return raw or f"Slot {slot_id}"


def get_equipment_name(item: dict[str, Any], lang: dict[str, Any]) -> str:
    equipment_id = str(item.get("equipmentid") or "")
    lang_key = f"equipment_unique_{equipment_id}".lower()
    return str(lang.get(lang_key) or item.get("comment2") or item.get("comment1") or f"Equipment {equipment_id}")


def get_gem_name(item: dict[str, Any], lang: dict[str, Any]) -> str:
    gem_id = str(item.get("gemid") or "")
    lang_key = f"gem_unique_{gem_id}".lower()
    return str(lang.get(lang_key) or item.get("comment2") or item.get("comment1") or f"Gem {gem_id}")


def get_set_title(set_entry: dict[str, Any], lang: dict[str, Any]) -> str:
    set_id = str(set_entry.get("id") or "").strip()
    if set_id:
        for key in (f"equipment_set_{set_id}".lower(), f"equipment_set_{set_id}"):
            if lang.get(key):
                return str(lang[key])
    for bonus in set_entry.get("bonuses", []):
        comment2 = str(bonus.get("comment2") or "").strip()
        if comment2:
            return comment2
    for equipment in set_entry.get("equipments", []):
        comment1 = str(equipment.get("comment1") or "").strip()
        if comment1:
            return re.sub(r"\b(armor|weapon|helmet|artifact|hero)\b", "", comment1, flags=re.IGNORECASE).strip()
    return f"Set #{set_id}"


def build_set_index(equipments: list[dict[str, Any]], gems: list[dict[str, Any]], set_bonuses: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    def ensure(set_id: str) -> dict[str, Any]:
        index.setdefault(set_id, {"id": set_id, "equipments": [], "gems": [], "bonuses": []})
        return index[set_id]
    for item in equipments:
        set_id = normalize_set_id(item.get("setid"))
        if set_id:
            ensure(set_id)["equipments"].append(item)
    for item in gems:
        set_id = normalize_set_id(item.get("setid"))
        if set_id:
            ensure(set_id)["gems"].append(item)
    for item in set_bonuses:
        set_id = normalize_set_id(item.get("setid"))
        if set_id:
            ensure(set_id)["bonuses"].append(item)
    for entry in index.values():
        entry["bonuses"].sort(key=lambda row: int(str(row.get("neededitems") or "0") or 0))
        entry["equipments"].sort(key=lambda row: int(str(row.get("slotid") or "0") or 0))
    return index


def build_piece_rows(set_entry: dict[str, Any], equipment_images: dict[str, str], gem_images: dict[str, str], slot_by_id: dict[str, dict[str, Any]], wearer_by_id: dict[str, dict[str, Any]], equipment_effect_to_effect_id: dict[str, str], effect_definitions: dict[str, dict[str, Any]], percent_ids: set[str], lang: dict[str, Any], units_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    gem_slot_label = str(lang.get("gem_name") or lang.get("gem_slottype_all") or "Связанные самоцветы")
    for item in set_entry.get("equipments", []):
        equipment_id = str(item.get("equipmentid") or "")
        reuse_id = str(item.get("reuseassetofequipmentid") or "")
        image_url = equipment_images.get(equipment_id) or (equipment_images.get(reuse_id) if reuse_id else "") or ""
        rows.append({
            "type": "equipment",
            "id": equipment_id,
            "slot_id": str(item.get("slotid") or ""),
            "slot_label": get_localized_slot_name(item.get("slotid"), slot_by_id, lang),
            "wearer_id": str(item.get("wearerid") or ""),
            "wearer_label": get_localized_wearer_name(item.get("wearerid"), wearer_by_id, lang),
            "name": get_equipment_name(item, lang),
            "effects": parse_effect_lines(item.get("effects"), equipment_effect_to_effect_id, effect_definitions, percent_ids, lang, units_by_id, "equipment"),
            "effect_tokens": parse_effect_tokens(item.get("effects"), equipment_effect_to_effect_id, effect_definitions, lang, units_by_id, "equipment"),
            "image_url": image_url,
            "might_value": int(str(item.get("mightvalue") or "0") or 0),
            "raw": item,
        })
    for item in set_entry.get("gems", []):
        gem_id = str(item.get("gemid") or "")
        reuse_id = str(item.get("reuseassetofgemid") or "")
        image_url = gem_images.get(gem_id) or (gem_images.get(reuse_id) if reuse_id else "") or ""
        rows.append({
            "type": "gem",
            "id": gem_id,
            "slot_id": "gem",
            "slot_label": gem_slot_label,
            "wearer_id": str(item.get("wearerid") or ""),
            "wearer_label": get_localized_wearer_name(item.get("wearerid"), wearer_by_id, lang),
            "name": get_gem_name(item, lang),
            "effects": parse_effect_lines(item.get("effects"), equipment_effect_to_effect_id, effect_definitions, percent_ids, lang, units_by_id, "gem"),
            "effect_tokens": parse_effect_tokens(item.get("effects"), equipment_effect_to_effect_id, effect_definitions, lang, units_by_id, "gem"),
            "image_url": image_url,
            "trigger_chance": int(str(item.get("triggerchance") or "0") or 0),
            "raw": item,
        })
    rows.sort(key=lambda row: (SLOT_ORDER.get(row["slot_id"], 99), int(row["id"] or 0)))
    return rows


def build_summary(set_entry: dict[str, Any], equipment_effect_to_effect_id: dict[str, str], effect_definitions: dict[str, dict[str, Any]], percent_ids: set[str], lang: dict[str, Any], units_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[str, dict[str, Any]] = {}
    def add_tokens(raw: Any, source_type: str) -> None:
        for token in parse_effect_tokens(raw, equipment_effect_to_effect_id, effect_definitions, lang, units_by_id, source_type):
            key = f"{token['effect_id']}::{token.get('arg_id') or ''}"
            bucket = totals.get(key)
            if not bucket:
                totals[key] = {"effect_id": token["effect_id"], "arg_id": token.get("arg_id"), "value": float(token["value"])}
                continue
            bucket["value"] += float(token["value"])
    for item in set_entry.get("equipments", []):
        add_tokens(item.get("effects"), "equipment")
    for item in set_entry.get("gems", []):
        add_tokens(item.get("effects"), "gem")
    for item in set_entry.get("bonuses", []):
        add_tokens(item.get("effects"), "set_bonus")
    rows = []
    for entry in totals.values():
        label = render_effect_line(entry["effect_id"], entry["value"], entry.get("arg_id"), equipment_effect_to_effect_id, effect_definitions, percent_ids, lang, units_by_id, "auto")
        rows.append({
            "effect_id": entry["effect_id"],
            "arg_id": entry.get("arg_id"),
            "value": entry["value"],
            "label": label,
        })
    rows.sort(key=lambda item: (-abs(float(item["value"])), int(str(item["effect_id"]).split('.')[0]) if str(item["effect_id"]).isdigit() else 0, item["label"]))
    return rows


def build_catalog() -> list[dict[str, Any]]:
    items = load_items()
    lang = load_language("ru")
    equipment_images, gem_images = build_image_maps()
    effect_definitions, percent_ids = get_effect_context(items, lang)

    equipments = items.get("equipments", [])
    gems = items.get("gems", [])
    set_bonuses = items.get("equipment_sets", [])
    equipment_effects = items.get("equipment_effects", [])
    slots = items.get("equipment_slots", [])
    wearers = items.get("equipment_wearers", [])
    units = items.get("units", [])

    equipment_effect_to_effect_id = {
        str(row.get("equipmenteffectid") or "").strip(): str(row.get("effectid") or "").strip()
        for row in equipment_effects
        if str(row.get("equipmenteffectid") or "").strip() and str(row.get("effectid") or "").strip()
    }
    slot_by_id = build_lookup(slots, "slotid")
    wearer_by_id = build_lookup(wearers, "wearerid")
    units_by_id = build_lookup(units, "wodid")
    set_index = build_set_index(equipments, gems, set_bonuses)

    catalog: list[dict[str, Any]] = []
    for set_id, set_entry in set_index.items():
        piece_rows = build_piece_rows(set_entry, equipment_images, gem_images, slot_by_id, wearer_by_id, equipment_effect_to_effect_id, effect_definitions, percent_ids, lang, units_by_id)
        bonus_rows = []
        for bonus in set_entry.get("bonuses", []):
            bonus_rows.append({
                "milestone_id": str(bonus.get("id") or ""),
                "needed_items": int(str(bonus.get("neededitems") or "0") or 0),
                "name": str(bonus.get("comment2") or ""),
                "effects": parse_effect_lines(bonus.get("effects"), equipment_effect_to_effect_id, effect_definitions, percent_ids, lang, units_by_id, "set_bonus"),
                "effect_tokens": parse_effect_tokens(bonus.get("effects"), equipment_effect_to_effect_id, effect_definitions, lang, units_by_id, "set_bonus"),
                "raw": bonus,
            })
        set_title = get_set_title(set_entry, lang)
        wearer_ids = sorted(
            {
                str(item.get("wearerid") or "")
                for item in [*set_entry.get("equipments", []), *set_entry.get("gems", [])]
                if str(item.get("wearerid") or "").strip()
            }
        )
        wearer_labels = [get_localized_wearer_name(wearer_id, wearer_by_id, lang) for wearer_id in wearer_ids]
        catalog.append({
            "set_id": set_id,
            "name": set_title,
            "is_default_set_id": is_default_set_id(set_id),
            "wearer_ids": wearer_ids,
            "wearer_labels": wearer_labels,
            "piece_count": len(piece_rows),
            "equipment_count": len(set_entry.get("equipments", [])),
            "gem_count": len(set_entry.get("gems", [])),
            "pieces": piece_rows,
            "bonuses": bonus_rows,
            "effect_summary": build_summary(set_entry, equipment_effect_to_effect_id, effect_definitions, percent_ids, lang, units_by_id),
            "source": "official",
            "status": "official",
        })
    catalog.sort(key=lambda item: (-(int(item["set_id"]) if item["set_id"].isdigit() else 0), item["name"]))
    return catalog


def main() -> None:
    catalog = build_catalog()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(catalog)} equipment sets to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
