from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

BUILDINGS_HTML_FILE = Path(__file__).resolve().parent / "data" / "buildings_sheet_data.html"
OUTPUT_FILE = Path(__file__).resolve().parent / "data" / "official_buildings_catalog.json"

NAME_FIXES = {
    "Trade distrct": "Trade district",
    "Entcantment": "Encampment",
    "Toolsmith-Kindoms": "Toolsmith-Kingdoms",
    "Refinery-Kindoms": "Refinery-Kingdoms",
    "moat": "Moat",
}

DISPLAY_NAME_MAP = {
    "Apiary": "Пасека",
    "Armory": "Оружейная",
    "Barracks": "Казармы",
    "Barrel workshop": "Бондарная мастерская",
    "Brewery": "Пивоварня",
    "Butcher shop": "Мясная лавка",
    "Castle expansion": "Расширение замка",
    "Cattle farm": "Скотная ферма",
    "Defence workshop": "Оборонная мастерская",
    "Dragon Breath Forge": "Кузница дыхания дракона",
    "Dragon Hoard": "Сокровищница дракона",
    "Encampment": "Военный лагерь",
    "Flour mill": "Мельница",
    "Food district": "Пищевой квартал",
    "Gate": "Ворота",
    "Honey gardens": "Медовые сады",
    "Imperial Council hall": "Имперский совет",
    "Inner district": "Внутренний квартал",
    "Keep": "Главная башня",
    "Marketplace": "Рынок",
    "Mead district": "Медовый квартал",
    "Mead distillery": "Медоварня",
    "Military academy": "Военная академия",
    "Military district": "Военный квартал",
    "Moat": "Ров",
    "Refinery": "Рафинерия",
    "Refinery-Kingdoms": "Рафинерия королевств",
    "Reinforced Vault": "Укреплённое хранилище",
    "Relic bakery": "Реликтовая пекарня",
    "Relic conservatory": "Реликтовая консерватория",
    "Relic greenhouse": "Реликтовая теплица",
    "Relic quarry": "Реликтовый карьер",
    "Relic storehouse": "Реликтовый склад",
    "Relic woodcutter": "Реликтовый дровосек",
    "Relictus": "Реликтус",
    "Research Tower": "Башня исследований",
    "Siege workshop": "Осадная мастерская",
    "Storehouse": "Склад",
    "Tavern": "Таверна",
    "Toolsmith": "Инструментальная кузница",
    "Toolsmith-Kingdoms": "Инструментальная кузница королевств",
    "Tower": "Башня",
    "Trade district": "Торговый квартал",
    "Wall": "Стена",
}

CATEGORY_MAP = {
    "Apiary": "Экономика",
    "Armory": "Военное",
    "Barracks": "Военное",
    "Barrel workshop": "Экономика",
    "Brewery": "Экономика",
    "Butcher shop": "Провиант",
    "Castle expansion": "Замок",
    "Cattle farm": "Провиант",
    "Defence workshop": "Оборона",
    "Dragon Breath Forge": "Дракон",
    "Dragon Hoard": "Дракон",
    "Encampment": "Военное",
    "Flour mill": "Провиант",
    "Food district": "Квартал",
    "Gate": "Оборона",
    "Honey gardens": "Провиант",
    "Imperial Council hall": "Администрация",
    "Inner district": "Квартал",
    "Keep": "Замок",
    "Marketplace": "Экономика",
    "Mead district": "Квартал",
    "Mead distillery": "Экономика",
    "Military academy": "Военное",
    "Military district": "Квартал",
    "Moat": "Оборона",
    "Refinery": "Ресурсы",
    "Refinery-Kingdoms": "Ресурсы",
    "Reinforced Vault": "Дракон",
    "Relic bakery": "Реликвии",
    "Relic conservatory": "Реликвии",
    "Relic greenhouse": "Реликвии",
    "Relic quarry": "Реликвии",
    "Relic storehouse": "Реликвии",
    "Relic woodcutter": "Реликвии",
    "Relictus": "Реликвии",
    "Research Tower": "Исследования",
    "Siege workshop": "Военное",
    "Storehouse": "Экономика",
    "Tavern": "Инфраструктура",
    "Toolsmith": "Военное",
    "Toolsmith-Kingdoms": "Военное",
    "Tower": "Оборона",
    "Trade district": "Квартал",
    "Wall": "Оборона",
}

DESCRIPTION_MAP = {
    "Apiary": "Хозяйственная постройка медовой цепочки. Используется в экономическом развитии и поддерживает профильные производственные здания.",
    "Armory": "Оружейная замка. Связана с военной инфраструктурой и развитием боевой части крепости.",
    "Barracks": "Казармы для найма и подготовки солдат. Базовое военное здание для развития армии.",
    "Barrel workshop": "Вспомогательное производственное здание. Используется в цепочке хозяйственных построек и переработки.",
    "Brewery": "Производственное здание, связанное с пивоваренной и медовой цепочкой экономики.",
    "Butcher shop": "Пищевое здание. Поддерживает провиантную цепочку и переработку продукции животноводства.",
    "Castle expansion": "Расширение замка. Открывает дополнительное место для развития и строительства внутри крепости.",
    "Cattle farm": "Ферма животноводства. Работает в провиантной цепочке вместе с пищевыми зданиями.",
    "Defence workshop": "Мастерская обороны. Связана с изготовлением и развитием защитной инфраструктуры замка.",
    "Dragon Breath Forge": "Поздняя игровая кузница драконьей ветки. Используется для развития специальной инфраструктуры.",
    "Dragon Hoard": "Хранилище драконьих ресурсов. Нужен для накопления и развития драконьей ветки построек.",
    "Encampment": "Военный лагерь. Вспомогательная постройка для развития армейской инфраструктуры.",
    "Flour mill": "Мельница для переработки продовольствия. Часть пищевой цепочки развития замка.",
    "Food district": "Пищевой квартал. Концентрирует развитие зданий, связанных с продовольствием.",
    "Gate": "Ворота замка. Ключевой элемент обороны, связанный с защитой прохода в крепость.",
    "Honey gardens": "Производственное здание медовой линии. Поддерживает хозяйственную цепочку ресурсов.",
    "Imperial Council hall": "Административное здание позднего этапа развития замка.",
    "Inner district": "Внутренний квартал замка. Отвечает за развитие центральной городской части.",
    "Keep": "Главное здание замка и центр всей крепости. Через него проходит развитие ключевой инфраструктуры.",
    "Marketplace": "Рынок для торговли и хозяйственных операций. Экономическое здание базовой инфраструктуры.",
    "Mead district": "Квартал медовой продукции. Объединяет профильные производственные улучшения.",
    "Mead distillery": "Производит медовую продукцию и участвует в профильной экономической цепочке.",
    "Military academy": "Обеспечивает доступ к программам подготовки.",
    "Military district": "Военный квартал. Сконцентрирован на развитии армии и профильных построек.",
    "Moat": "Ров перед стенами крепости. Важная часть обороны подступов к замку.",
    "Refinery": "Перерабатывающее здание для редких материалов и специальной ресурсной ветки.",
    "Refinery-Kingdoms": "Версия переработки ресурсов для миров и королевств.",
    "Reinforced Vault": "Усиленное хранилище для ценных ресурсов и позднего развития.",
    "Relic bakery": "Реликтовая производственная постройка. Относится к ветке реликтовых ресурсов.",
    "Relic conservatory": "Реликтовое здание для развития и поддержки особой ресурсной ветки.",
    "Relic greenhouse": "Реликтовая теплица. Используется в специальной цепочке реликтовых построек.",
    "Relic quarry": "Реликтовый карьер для добывающей части специальной ресурсной ветки.",
    "Relic storehouse": "Реликтовый склад для хранения особых ресурсов.",
    "Relic woodcutter": "Реликтовый дровосек. Производственная постройка ресурсной реликтовой ветки.",
    "Relictus": "Специальная реликтовая постройка позднего развития.",
    "Research Tower": "Башня исследований. Нужна для технологического и системного развития замка.",
    "Siege workshop": "Осадная мастерская. Связана с осадными инструментами и военной инфраструктурой.",
    "Storehouse": "Складская постройка. Поддерживает хранение и хозяйственную инфраструктуру.",
    "Tavern": "Служебное здание внутренней инфраструктуры замка.",
    "Toolsmith": "Кузница инструментов. Используется для военной и вспомогательной инфраструктуры.",
    "Toolsmith-Kingdoms": "Кузница инструментов для миров и королевств.",
    "Tower": "Оборонительная башня. Усиливает защитную систему стен и внешнего периметра.",
    "Trade district": "Торговый квартал. Развивает экономику, торговлю и хозяйственную часть замка.",
    "Wall": "Стена замка. Главная линия укрепления и базовая часть обороны крепости.",
}

HEADER_ALIASES = {
    "уровень": "level",
    "lvl": "level",
    "молотки": "build_tokens",
    "build tokens": "build_tokens",
    "стрелки": "upgrade_tokens",
    "upgrade tokens": "upgrade_tokens",
    "талеры": "talers",
    "dukaten": "ducats",
    "rubis": "rubies",
    "гипс": "plaster",
    "plaster": "plaster",
    "чешуя": "dragon_scale_tiles",
    "dragon scale tile": "dragon_scale_tiles",
}


def normalize_text(value: str) -> str:
    cleaned = html.unescape(str(value or "")).replace("\xa0", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def parse_rows(html_text: str) -> tuple[list[list[dict[str, Any]]], list[list[str]]]:
    rows_html = re.findall(r"<tr[^>]*>(.*?)</tr>", html_text, re.S)
    parsed_rows: list[list[dict[str, Any]]] = []
    expanded_rows: list[list[str]] = []
    for row_html in rows_html:
        col = 0
        parsed: list[dict[str, Any]] = []
        for attrs, cell in re.findall(r"<t[dh]([^>]*)>(.*?)</t[dh]>", row_html, re.S):
            raw = re.sub(r"<div[^>]*>|</div>|<img[^>]*>|<br\s*/?>", " ", cell)
            raw = re.sub(r"<[^>]+>", "", raw)
            value = normalize_text(raw)
            colspan_match = re.search(r'colspan="(\d+)"', attrs)
            colspan = int(colspan_match.group(1)) if colspan_match else 1
            parsed.append({"start": col, "end": col + colspan, "value": value})
            col += colspan
        if parsed and str(parsed[0].get("value") or "").isdigit():
            parsed = parsed[1:]
            for cell in parsed:
                cell["start"] -= 1
                cell["end"] -= 1
        width = max((cell["end"] for cell in parsed), default=0)
        expanded = [""] * width
        for cell in parsed:
            expanded[cell["start"]] = str(cell["value"] or "")
        parsed_rows.append(parsed)
        expanded_rows.append(expanded)
    return parsed_rows, expanded_rows


def normalize_header(label: str) -> str:
    return HEADER_ALIASES.get(normalize_text(label).lower(), "")


def normalize_name(name: str) -> str:
    return NAME_FIXES.get(normalize_text(name), normalize_text(name))


def infer_display_name(name: str) -> str:
    return DISPLAY_NAME_MAP.get(name, name)


def is_building_name(value: str) -> bool:
    text = normalize_text(value)
    if not text or text in {"Initial", "Cummulative"}:
        return False
    if normalize_header(text):
        return False
    if any(ch.isdigit() for ch in text):
        return False
    return True


def is_level_label(value: str) -> bool:
    text = normalize_text(value)
    return bool(text) and text[0].isdigit()


def dedupe_levels(levels: list[dict[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in levels:
        level = str(entry.get("level") or "").strip()
        if not level or level in seen:
            continue
        seen.add(level)
        result.append(entry)
    return result


def split_building_variants(name: str) -> list[str]:
    if " / " not in name:
        return [name]
    return [part.strip() for part in name.split("/") if part.strip()]


def infer_category(name: str) -> str:
    return CATEGORY_MAP.get(name, "Инфраструктура")


def infer_description(name: str) -> str:
    return DESCRIPTION_MAP.get(name, f"{name} — постройка из таблицы улучшений. Для неё доступны уровни и расчёт затрат по выбранному диапазону.")


def extract_building_images(html_text: str) -> dict[str, str]:
    rows_html = re.findall(r"<tr[^>]*>(.*?)</tr>", html_text, re.S)
    image_map: dict[str, str] = {}
    for index, row_html in enumerate(rows_html[:-1]):
        images = re.findall(r'<img src="([^"]+)"', row_html)
        if not images:
            continue
        next_row_html = rows_html[index + 1]
        title_cells: list[str] = []
        for _attrs, cell in re.findall(r"<t[dh]([^>]*)>(.*?)</t[dh]>", next_row_html, re.S):
            raw = re.sub(r"<div[^>]*>|</div>|<img[^>]*>|<br\s*/?>", " ", cell)
            raw = re.sub(r"<[^>]+>", "", raw)
            value = normalize_name(normalize_text(raw))
            if is_building_name(value):
                title_cells.append(value)
        if not title_cells:
            continue
        for position, building_name in enumerate(title_cells):
            if building_name not in image_map:
                image_map[building_name] = images[min(position, len(images) - 1)]
    return image_map


def parse_buildings_catalog(html_text: str) -> list[dict[str, Any]]:
    parsed_rows, rows = parse_rows(html_text)
    image_map = extract_building_images(html_text)
    start = next(index for index, row in enumerate(rows) if "Initial" in row)
    end = next(index for index, row in enumerate(rows) if "Cummulative" in row)

    active_groups: dict[tuple[int, int], dict[str, Any]] = {}
    buildings: dict[str, dict[str, Any]] = {}

    for index in range(start + 1, end):
        row_cells = parsed_rows[index]
        row = rows[index]
        next_row = rows[index + 1] if index + 1 < len(rows) else []

        for cell in row_cells:
            raw_name = normalize_name(str(cell.get("value") or ""))
            if not is_building_name(raw_name):
                continue
            field_positions: dict[int, str] = {}
            for col in range(cell["start"], min(cell["end"], len(next_row))):
                field_name = normalize_header(next_row[col])
                if field_name:
                    field_positions[col] = field_name
            if not field_positions or "level" not in field_positions.values():
                continue
            active_groups[(cell["start"], cell["end"])] = {"name": raw_name, "field_positions": field_positions}
            buildings.setdefault(raw_name, {"name": raw_name, "levels": [], "resource_fields": []})

        for group in active_groups.values():
            values: dict[str, str] = {}
            for col, field_name in group["field_positions"].items():
                if col >= len(row):
                    continue
                raw_value = normalize_text(row[col])
                if raw_value:
                    values[field_name] = raw_value
            level = values.get("level") or ""
            if not is_level_label(level):
                continue
            buildings[group["name"]]["levels"].append(values)

    result: list[dict[str, Any]] = []
    for raw_name, data in buildings.items():
        levels = dedupe_levels(data["levels"])
        if not levels:
            continue
        resource_fields: list[str] = []
        for row in levels:
            for key in row.keys():
                if key != "level" and key not in resource_fields:
                    resource_fields.append(key)
        for variant_name in split_building_variants(raw_name):
            result.append(
                {
                    "name": variant_name,
                    "display_name": infer_display_name(variant_name),
                    "category": infer_category(variant_name),
                    "description": infer_description(variant_name),
                    "image_url": image_map.get(raw_name) or image_map.get(variant_name) or "",
                    "resource_fields": resource_fields,
                    "levels": levels,
                    "level_labels": [str(item.get("level") or "") for item in levels if item.get("level")],
                    "source": "google_sheet",
                    "status": "verified",
                }
            )
    return sorted(result, key=lambda item: (str(item.get("category") or ""), str(item.get("display_name") or "")))


def main() -> None:
    if not BUILDINGS_HTML_FILE.exists():
        raise FileNotFoundError(f"Не найден HTML-лист зданий: {BUILDINGS_HTML_FILE}")
    html_text = BUILDINGS_HTML_FILE.read_text(encoding="utf-8")
    catalog = parse_buildings_catalog(html_text)
    OUTPUT_FILE.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(catalog)} buildings to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
