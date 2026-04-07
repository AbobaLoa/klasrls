from __future__ import annotations

import io
import json
import re
import ssl
import zipfile
from pathlib import Path
from typing import Any
from urllib.request import urlopen
import xml.etree.ElementTree as ET

APP_LOOKUP_URL = "https://itunes.apple.com/lookup?id=585661281"
LANGUAGE_VERSION_URL = "https://langserv.public.ggs-ep.com/12/fr/@metadata"
LANGUAGE_BASE_URL = "https://langserv.public.ggs-ep.com"
GAME_INDEX_URL = "https://empire-html5.goodgamestudios.com/default/index.html"
ASSET_BASE_URL = "https://empire-html5.goodgamestudios.com/default/assets/"
OUTPUT_FILE = Path(__file__).resolve().parent / "data" / "official_generals_catalog.json"

SKILL_TYPE_MAP = {
    "CourtyardSize": "defense",
    "ReinforcementWave": "attack",
    "UnitAmountWall": "defense",
    "defenseBoostYard": "defense",
    "DefenseBoostFlank": "defense",
    "DefenseBoostFront": "defense",
    "AttackBoostFlank": "attack",
    "AttackBoostFront": "attack",
    "additionalWaves": "attack",
    "UnitAmountFlank": "attack",
    "UnitAmountFront": "attack",
    "BonusPowerYard": "attack",
    "additionalWavesSiege": "attack",
}

FALLBACK_ICON_MAP = {
    "attack": "https://generalscamp.github.io/forum/img_base/attack-icon.webp",
    "defense": "https://generalscamp.github.io/forum/img_base/defense-icon.webp",
}

SPECIAL_ABILITY_HANDLERS = {"1021", "1023", "1033", "1035", "1028"}


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


def normalize_name(value: Any) -> str:
    return str(value or "").lower()


def build_lookup(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        value = item.get(key)
        if value is not None:
            result[str(value)] = item
    return result


def get_e4k_app_version() -> str:
    payload = fetch_json(APP_LOOKUP_URL)
    version = str(payload.get("results", [{}])[0].get("version") or "")
    parts = version.split(".")
    if len(parts) < 2:
        raise RuntimeError(f"Unexpected E4K version format: {version}")
    major = parts[0]
    minor = parts[1]
    patch = (parts[2] if len(parts) > 2 else "0").zfill(3)
    return f"{major}{minor}{patch}"


def get_e4k_item_version(app_version: str) -> str:
    payload = fetch_json(f"https://media.goodgamestudios.com/loader/empirefourkingdoms/{app_version}/versions.json")
    version = str(payload.get("CastleItemXMLVersion") or "")
    if not version:
        raise RuntimeError("CastleItemXMLVersion missing from E4K versions.json")
    return version


def load_e4k_items() -> dict[str, list[dict[str, Any]]]:
    app_version = get_e4k_app_version()
    item_version = get_e4k_item_version(app_version)
    normalized_version = item_version.replace(".", "_")
    archive_url = f"https://media.goodgamestudios.com/loader/empirefourkingdoms/{app_version}/itemsXML/items_{normalized_version}.ggs"
    context = ssl._create_unverified_context()
    with urlopen(archive_url, timeout=180, context=context) as response:
        archive_data = response.read()

    with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
        first_name = archive.namelist()[0]
        xml_bytes = archive.read(first_name)

    root = ET.fromstring(xml_bytes)
    result: dict[str, list[dict[str, Any]]] = {}
    for child in list(root):
        result[child.tag.lower()] = [lowercase_keys_recursive(dict(node.attrib)) for node in list(child)]
    return result


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


def parse_general_assets() -> tuple[dict[str, str], dict[str, str]]:
    dll_text = fetch_text(get_dll_url())
    portraits: dict[str, str] = {}
    abilities: dict[str, str] = {}

    for match in re.finditer(r"itemassets/General/Portrait/GeneralPortrait_(\d+)/GeneralPortrait_\1--\d+", dll_text):
        general_id = match.group(1)
        portraits[general_id] = f"{ASSET_BASE_URL}{match.group(0)}.webp"

    for match in re.finditer(r"itemassets/Dialogs/Generals/GeneralIcons/GeneralIcon_(\d+)/GeneralIcon_\1--\d+", dll_text):
        general_id = match.group(1)
        portraits[general_id] = f"{ASSET_BASE_URL}{match.group(0)}.webp"

    for match in re.finditer(r"itemassets/General/Abilities/GeneralsAbilityGroup_(\d+)/GeneralsAbilityGroup_\1--\d+", dll_text):
        ability_group_id = match.group(1)
        abilities[ability_group_id] = f"{ASSET_BASE_URL}{match.group(0)}.webp"

    return portraits, abilities


def resolve_general_name(general: dict[str, Any], lang: dict[str, Any]) -> str:
    return str(
        lang.get(f"generals_characters_{general.get('generalid')}_name")
        or general.get("generalname")
        or "Генерал"
    )


def get_rarity_name(rarity_id: str, lang: dict[str, Any]) -> str:
    return str(lang.get(f"generals_rarity_{rarity_id}") or rarity_id or "Unknown")


def get_base_skill_name(skill_name: str) -> str:
    if not skill_name:
        return ""
    return re.sub(r"\d+$", "", re.sub(r"Legendary|Epic|Rare|Common", "", skill_name, flags=re.IGNORECASE)).strip()


def resolve_ability_group_id(skill: dict[str, Any]) -> str:
    raw = str(skill.get("skillgroupid") or "")
    return raw if len(raw) <= 4 else raw[-4:]


def resolve_skill_display_name(skill: dict[str, Any], lang: dict[str, Any]) -> str:
    raw_name = str(skill.get("name") or "")
    base = get_base_skill_name(raw_name)
    if not base:
        return "Unknown"

    plain_key = f"generals_skill_name_{base}".lower()
    if lang.get(plain_key):
        return str(lang[plain_key])

    rarity_match = re.search(r"Legendary|Epic|Rare|Common", raw_name, re.IGNORECASE)
    if rarity_match:
        rarity = rarity_match.group(0)
        key = f"generals_skill_name_{base}{rarity}".lower()
        if lang.get(key):
            return str(lang[key])

    return base


def resolve_skill_description(skill: dict[str, Any], lang: dict[str, Any], skills_by_general: dict[str, list[dict[str, Any]]]) -> str:
    effects = str(skill.get("effects") or "")
    if not effects:
        return ""
    parts = effects.split("&", 1)
    if len(parts) != 2:
        return ""
    value = parts[1]
    base_name = get_base_skill_name(str(skill.get("name") or ""))
    if not base_name:
        return ""

    text = lang.get(f"generals_skill_desc_{base_name}".lower())
    if not text:
        for rarity in ("Legendary", "Epic", "Rare", "Common"):
            alt_key = f"generals_skill_desc_{base_name}{rarity}".lower()
            if lang.get(alt_key):
                text = lang[alt_key]
                break
    if not text:
        return ""

    replaced = str(text).replace("{0}", value)
    try:
        value_num = float(value)
    except ValueError:
        return replaced

    skill_group_id = str(skill.get("skillgroupid") or "")
    max_level = len([item for item in skills_by_general.get(str(skill.get("generalid") or ""), []) if str(item.get("skillgroupid") or "") == skill_group_id])
    if max_level <= 1:
        return replaced

    max_bonus = int(value_num * max_level) if float(value_num).is_integer() else value_num * max_level
    return f"{replaced} (max.: {max_bonus}{'%' if '%' in replaced else ''})"


def get_skill_type(skill: dict[str, Any]) -> str:
    return SKILL_TYPE_MAP.get(get_base_skill_name(str(skill.get("name") or "")), "unknown")


def get_slot_index(general: dict[str, Any], slots_by_id: dict[str, dict[str, Any]], ability_group_id: str, slot_type: str) -> int | None:
    key = "defenseslots" if slot_type == "defense" else "attackslots"
    slot_ids = [part.strip() for part in str(general.get(key) or "").split(",") if part.strip()]
    for index, slot_id in enumerate(slot_ids, start=1):
        slot = slots_by_id.get(slot_id)
        if not slot:
            continue
        groups = [part.strip() for part in str(slot.get("abilitygroupids") or "").split(",") if part.strip()]
        if str(ability_group_id) in groups:
            return index
    return None


def resolve_ability_effect_values(ability: dict[str, Any] | None, ability_effects_by_id: dict[str, dict[str, Any]], effect_type: str) -> list[str]:
    if not ability:
        return []
    effect_id_key = "abilityattackeffectid" if effect_type == "attack" else "abilitydefenseeffectid"
    effect_id = str(ability.get(effect_id_key) or "")
    if not effect_id or effect_id == "0":
        return []
    effect = ability_effects_by_id.get(effect_id)
    if not effect:
        return []
    text = str(effect.get("effects") or "")
    values: list[str] = []
    for chunk in [part.strip() for part in text.split(",") if part.strip()]:
        parts = chunk.split("&", 1)
        if len(parts) == 2:
            values.append(parts[1])
    return values


def build_ability_level_payload(level_item: dict[str, Any], ability_effects_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "ability_id": str(level_item.get("abilityid") or ""),
        "level": int(str(level_item.get("level") or "0") or 0),
        "ability_attack_effect_id": str(level_item.get("abilityattackeffectid") or ""),
        "ability_defense_effect_id": str(level_item.get("abilitydefenseeffectid") or ""),
        "attack_effect_values": resolve_ability_effect_values(level_item, ability_effects_by_id, "attack"),
        "defense_effect_values": resolve_ability_effect_values(level_item, ability_effects_by_id, "defense"),
    }


def resolve_ability_description(group_id: str, ability: dict[str, Any] | None, effect_type: str, lang: dict[str, Any]) -> str:
    key = f"generals_abilities_desc_{effect_type}_{group_id}".lower()
    text = str(lang.get(key) or "")
    if not text:
        return ""

    values = resolve_ability_effect_values(ability, {}, effect_type)
    if ability is not None:
        effect_id_key = "abilityattackeffectid" if effect_type == "attack" else "abilitydefenseeffectid"
        _ = ability.get(effect_id_key)
    if group_id == "1021":
        placeholder_key = "generals_abilities_desc_upgrade_placeholder_1021"
        placeholder_text = str(lang.get(placeholder_key.lower()) or "")
        wave = str((ability or {}).get("triggerperwave") or "1")
        if placeholder_text:
            injected = placeholder_text.replace("{0}", wave)
            return text.replace("{0}", f" {injected}").strip()
        return text.replace("{0}", "").strip()

    values = resolve_ability_effect_values(ability, ability_effects_by_id_global, effect_type)
    if group_id == "1023":
        value0 = values[0] if values else "0"
        return text.replace("{0}", value0).replace("{1}", "10").replace("{2}", str((ability or {}).get("triggerperwave") or "1")).strip()

    for index, value in enumerate(values):
        text = text.replace(f"{{{index}}}", value)

    if group_id == "1033" and values:
        text = text.replace("{1}", values[0])

    if group_id == "1035" and values:
        try:
            base = float(values[0])
            replacement = str(int(base * 2) if float(base * 2).is_integer() else base * 2)
            text = text.replace("{1}", replacement)
        except ValueError:
            pass

    if group_id == "1028":
        value0 = values[0] if values else "0"
        if effect_type == "attack":
            text = text.replace("{0}", value0).replace("{1}", value0)
        else:
            text = text.replace("{0}", value0).replace("{1}", "")
        return text.replace("{2}", str((ability or {}).get("triggerperwave") or "1")).strip()

    text = text.replace("{0}", "")
    text = text.replace("{1}", str((ability or {}).get("triggerperwave") or "1"))
    text = text.replace("{2}", str((ability or {}).get("triggerperwave") or "1"))
    return text.strip()


def get_ability_type(ability: dict[str, Any] | None) -> str:
    if not ability:
        return "unknown"
    has_attack = str(ability.get("abilityattackeffectid") or "") not in {"", "0"}
    has_defense = str(ability.get("abilitydefenseeffectid") or "") not in {"", "0"}
    if has_attack and has_defense:
        return "both"
    if has_attack:
        return "attack"
    if has_defense:
        return "defense"
    return "unknown"


def build_costs(general: dict[str, Any], rarity: dict[str, Any]) -> dict[str, Any]:
    max_level = int(str(general.get("maxlevel") or "0") or 0)
    unlock_cost = int(str(rarity.get("unlockcosts") or "0") or 0)
    upgrade_costs = [int(value) for value in str(rarity.get("upgradecosts") or "").split(",") if value.strip()]
    xp_requirements = [int(value) for value in str(rarity.get("xprequirements") or "").split(",") if value.strip()]

    levels: list[dict[str, Any]] = []
    upgrade_index = 0
    total_shards = 0
    total_xp = 0

    for level in range(1, max_level + 1):
        shard_value: int | None = None
        if level == 1:
            shard_value = unlock_cost
        elif (level - 1) % 10 == 0 or level == max_level:
            shard_value = upgrade_costs[upgrade_index] if upgrade_index < len(upgrade_costs) else None
            upgrade_index += 1

        xp_value: int | None = None
        if level - 1 < len(xp_requirements):
            if level == 1:
                xp_value = xp_requirements[0]
            elif level - 2 < len(xp_requirements):
                xp_value = xp_requirements[level - 1] - xp_requirements[level - 2]

        if shard_value is not None:
            total_shards += shard_value
        if xp_value is not None:
            total_xp += xp_value

        levels.append({"level": level, "shards": shard_value, "xp": xp_value})

    return {"levels": levels, "total_shards": total_shards, "total_xp": total_xp}


ability_effects_by_id_global: dict[str, dict[str, Any]] = {}


def build_catalog() -> list[dict[str, Any]]:
    global ability_effects_by_id_global

    items = load_e4k_items()
    lang = load_language("ru")
    portrait_map, ability_icon_map = parse_general_assets()

    generals = [item for item in items.get("generals", []) if str(item.get("isnpcgeneral") or "0") != "1"]
    general_skills = items.get("generalskills", [])
    general_abilities = items.get("generalabilities", [])
    general_ability_effects = items.get("generalabilityeffects", [])
    general_rarities = items.get("generalrarities", [])
    general_slots = items.get("generalslots", [])

    skills_by_general: dict[str, list[dict[str, Any]]] = {}
    for skill in general_skills:
        skills_by_general.setdefault(str(skill.get("generalid") or ""), []).append(skill)

    ability_levels_by_group: dict[str, list[dict[str, Any]]] = {}
    for ability in general_abilities:
        ability_levels_by_group.setdefault(str(ability.get("abilitygroupid") or ""), []).append(ability)
    for levels in ability_levels_by_group.values():
        levels.sort(key=lambda item: int(str(item.get("level") or "0") or 0))

    abilities_by_group = {group_id: levels[-1] for group_id, levels in ability_levels_by_group.items() if levels}
    ability_effects_by_id_global = build_lookup(general_ability_effects, "abilityeffectid")
    rarities_by_id = build_lookup(general_rarities, "generalrarityid")
    slots_by_id = build_lookup(general_slots, "slotid")

    catalog: list[dict[str, Any]] = []

    for general in generals:
        general_id = str(general.get("generalid") or "")
        rarity_id = str(general.get("generalrarityid") or "")
        rarity = rarities_by_id.get(rarity_id, {})
        display_name = resolve_general_name(general, lang)
        general_skills_for_general = skills_by_general.get(general_id, [])

        grouped_skills: dict[str, dict[str, Any]] = {}
        for skill in general_skills_for_general:
            raw_group_id = str(skill.get("skillgroupid") or "")
            same_group_count = len([item for item in general_skills_for_general if str(item.get("skillgroupid") or "") == raw_group_id])
            is_ability_like = 1 < same_group_count <= 3
            resolved_group_id = resolve_ability_group_id(skill) if is_ability_like else raw_group_id
            tier = str(skill.get("tier") or "0")
            key = f"{tier}:{resolved_group_id}"
            group = grouped_skills.setdefault(
                key,
                {
                    "tier": int(tier or 0),
                    "group_id": resolved_group_id,
                    "raw_group_id": raw_group_id,
                    "is_ability_like": is_ability_like,
                    "current_level": 0,
                    "max_level": 0,
                    "sample_skill": skill,
                    "levels": [],
                },
            )
            level_number = int(str(skill.get("level") or "0") or 0)
            group["levels"].append(level_number)
            group["max_level"] += 1
            if level_number >= group["current_level"]:
                group["current_level"] = level_number
                group["sample_skill"] = skill

        skills_payload: list[dict[str, Any]] = []
        abilities_payload: list[dict[str, Any]] = []

        for group in sorted(grouped_skills.values(), key=lambda item: (item["tier"], item["group_id"])):
            sample_skill = group["sample_skill"]
            skill_type = get_skill_type(sample_skill)
            skill_entry = {
                "tier": group["tier"],
                "group_id": group["group_id"],
                "raw_group_id": group["raw_group_id"],
                "skill_id": str(sample_skill.get("skillid") or ""),
                "name": resolve_skill_display_name(sample_skill, lang),
                "raw_name": str(sample_skill.get("name") or ""),
                "skill_type": skill_type,
                "description": resolve_skill_description(sample_skill, lang, skills_by_general),
                "levels": sorted(group["levels"]),
                "current_level": group["current_level"],
                "max_level": group["max_level"],
                "cost_skill_points": int(str(sample_skill.get("costskillpoints") or "0") or 0),
                "total_cost_skill_points": int(str(sample_skill.get("totalcostskillpoints") or "0") or 0),
                "effects": str(sample_skill.get("effects") or ""),
                "is_ability_like": group["is_ability_like"],
                "icon_url": ability_icon_map.get(group["group_id"]) if group["is_ability_like"] else FALLBACK_ICON_MAP.get(skill_type, "https://generalscamp.github.io/forum/img_base/unknown-icon.webp"),
            }
            skills_payload.append(skill_entry)

            if group["is_ability_like"]:
                ability_group_id = str(group["group_id"])
                ability = abilities_by_group.get(ability_group_id)
                attack_slot = get_slot_index(general, slots_by_id, ability_group_id, "attack")
                defense_slot = get_slot_index(general, slots_by_id, ability_group_id, "defense")
                ability_levels = ability_levels_by_group.get(ability_group_id, [])
                abilities_payload.append(
                    {
                        "group_id": ability_group_id,
                        "name": str(lang.get(f"generals_abilities_name_{ability_group_id}") or resolve_skill_display_name(sample_skill, lang)),
                        "ability_type": get_ability_type(ability),
                        "tier": group["tier"],
                        "trigger_per_wave": int(str((ability or {}).get("triggerperwave") or "0") or 0),
                        "affects_enemy_army": str((ability or {}).get("affectsenemyarmy") or "0") == "1",
                        "attack_slot_index": attack_slot,
                        "defense_slot_index": defense_slot,
                        "icon_url": ability_icon_map.get(ability_group_id, "https://generalscamp.github.io/forum/img_base/unknown-icon.webp"),
                        "attack_description": resolve_ability_description(ability_group_id, ability, "attack", lang),
                        "defense_description": resolve_ability_description(ability_group_id, ability, "defense", lang),
                        "attack_effect_values": resolve_ability_effect_values(ability, ability_effects_by_id_global, "attack"),
                        "defense_effect_values": resolve_ability_effect_values(ability, ability_effects_by_id_global, "defense"),
                        "ability_attack_effect_id": str((ability or {}).get("abilityattackeffectid") or ""),
                        "ability_defense_effect_id": str((ability or {}).get("abilitydefenseeffectid") or ""),
                        "levels": [build_ability_level_payload(item, ability_effects_by_id_global) for item in ability_levels],
                    }
                )

        entry = {
            "general_id": general_id,
            "crossplay_id": str(general.get("crossplayid") or ""),
            "name": display_name,
            "raw_name": str(general.get("generalname") or ""),
            "rarity_id": rarity_id,
            "rarity_name": get_rarity_name(rarity_id, lang),
            "max_level": int(str(general.get("maxlevel") or "0") or 0),
            "max_star_level": int(str(general.get("maxstarlevel") or "0") or 0),
            "unlock_currency_id": str(general.get("unlockcurrencyid") or ""),
            "upgrade_currency_ids": [part.strip() for part in str(general.get("upgradecurrencyids") or "").split(",") if part.strip()],
            "attack_slots": [part.strip() for part in str(general.get("attackslots") or "").split(",") if part.strip()],
            "defense_slots": [part.strip() for part in str(general.get("defenseslots") or "").split(",") if part.strip()],
            "bg_color": str(general.get("bgcolor") or ""),
            "bg_color_preview": str(general.get("bgcolorpreview") or ""),
            "portrait_url": portrait_map.get(general_id, ""),
            "costs": build_costs(general, rarity),
            "skills": skills_payload,
            "abilities": sorted(abilities_payload, key=lambda item: (item["tier"], item["group_id"])),
            "source": "official_e4k",
            "status": "official",
        }
        catalog.append(entry)

    catalog.sort(key=lambda item: (-int(item.get("rarity_id") or 0), str(item.get("name") or "")))
    return catalog


def main() -> None:
    catalog = build_catalog()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(catalog)} generals to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
