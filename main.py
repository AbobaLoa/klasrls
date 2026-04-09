from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import threading
from typing import Any
from urllib.parse import quote, urlparse
from urllib.request import urlopen

from kivy.config import Config
from kivy.app import App
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.factory import Factory
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import AsyncImage
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.resources import resource_find
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider

from building_data import get_buildings_catalog
from calculators import calculate_building_upgrade_plan, calculate_profile_defense_plan, calculate_upgrade_plan
from general_data import get_generals_catalog
from tools_data import get_defense_tools_catalog
from units_data import get_unit_catalog

try:
    from kivy.utils import platform
except Exception:
    platform = "unknown"

def resolve_default_ui_font() -> str:
    candidates = [
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return str(resource_find("Roboto-Regular.ttf") or "")

Config.set("graphics", "resizable", "1")
Config.set("graphics", "minimum_width", "420")
Config.set("graphics", "minimum_height", "760")
Config.set("graphics", "width", "1360")
Config.set("graphics", "height", "920")

if platform not in {"android", "ios"}:
    Config.set("graphics", "width", "1360")
    Config.set("graphics", "height", "920")

Window.clearcolor = (0.04, 0.07, 0.12, 1)

if platform not in {"android", "ios"}:
    Window.size = (1360, 920)


KV_FILE = "empirecalc_modern.kv"
PROFILE_FILE_NAME = "profiles.json"
MAIN_CASTLE_IMAGE_FILE = Path(r"C:\Users\Dima\Desktop\castle.jpg")
DEFAULT_UI_FONT = resolve_default_ui_font()
LOCAL_BUILDING_IMAGE_DIR = Path(__file__).resolve().parent / "data" / "building_icons"
LOCAL_BUILDING_IMAGE_OVERRIDES = {}
ACCOUNT_CASTLE_NAMES = (
    "Основной замок",
    "Аванпост 1",
    "Аванпост 2",
    "Аванпост 3",
    "Вечнохолодный ледник",
    "Пылающие пески",
    "Огненные вершины",
    "Штормовые острова",
    "Берег Клинков",
    "Внешние миры",
    "За гранью горизонта",
)
WORLD_RESOURCE_FIELDS = {"plaster", "dragon_scale_tiles"}
OUTPOST_AVAILABLE_BUILDING_NAMES = {
    "Encampment",
    "Barracks",
    "Armory",
    "Siege workshop",
    "Keep",
    "Tower",
    "Gate",
    "Defence workshop",
    "Moat",
    "Wall",
    "Tavern",
    "Marketplace",
    "Storehouse",
}
GOVERNOR_GENERAL_NONE = "Без наместника"
ACCOUNT_AVATAR_LABELS = {
    "crown": "Корона",
    "knight": "Рыцарь",
    "falcon": "Сокол",
    "wolf": "Волк",
}
DEFENSE_TOOL_ZONE_VALUES = ["all", "left", "center", "right", "courtyard"]
DEFENSE_TOOL_ZONE_LABELS = {
    "all": "Все участки",
    "left": "Левый фланг",
    "center": "Центр",
    "right": "Правый фланг",
    "courtyard": "Двор",
}
GOVERNOR_SKILL_SPECS = {
    "flank_bonus": {
        "raw_prefixes": ("defenseboostflank",),
        "label": "Фланги в обороне",
    },
    "center_bonus": {
        "raw_prefixes": ("defenseboostfront",),
        "label": "Центр в обороне",
    },
    "courtyard_bonus": {
        "raw_prefixes": ("defenseboostyard",),
        "label": "Двор в обороне",
    },
    "wall_limit_percent_bonus": {
        "raw_prefixes": ("unitamountwall",),
        "label": "Лимит стены, %",
    },
    "courtyard_size_bonus": {
        "raw_prefixes": ("courtyardsize",),
        "label": "Размер двора",
    },
}


def placeholder_image_url(text: str, bg_color: str, fg_color: str = "F3F7FF", size: str = "128x96") -> str:
    return f"https://placehold.co/{size}/{bg_color}/{fg_color}.png?text={quote(text)}"


def default_governor() -> dict[str, str]:
    return {
        "general_id": "",
        "general_name": "",
        "melee_bonus": "",
        "ranged_bonus": "",
        "flank_bonus": "",
        "courtyard_bonus": "",
        "center_bonus": "",
        "overall_bonus": "",
        "wall_defense": "",
        "gate_defense": "",
        "moat_defense": "",
        "wall_limit_bonus": "",
        "wall_limit_percent_bonus": "",
        "courtyard_size_bonus": "",
        "skill_flank_bonus_level": "",
        "skill_center_bonus_level": "",
        "skill_courtyard_bonus_level": "",
        "skill_wall_limit_percent_bonus_level": "",
        "skill_courtyard_size_bonus_level": "",
    }


def default_commander() -> dict[str, str]:
    return {
        "melee_bonus": "",
        "ranged_bonus": "",
        "overall_bonus": "",
        "flank_bonus": "",
        "center_bonus": "",
        "courtyard_bonus": "",
        "wall_bonus": "",
        "gate_bonus": "",
        "moat_bonus": "",
    }


def default_castle_record(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "display_name": name,
        "wall_units_base": "",
        "defensive_resources_note": "",
        "governor": default_governor(),
        "commander": default_commander(),
        "building_levels": {},
        "units_text": "",
        "defensive_tools_text": "",
    }


def default_account(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "avatar_key": "crown",
        "castles": {castle_name: default_castle_record(castle_name) for castle_name in ACCOUNT_CASTLE_NAMES},
    }


class WallUnitRow(ButtonBehavior, BoxLayout):
    selected = BooleanProperty(False)
    title_text = StringProperty("")
    subtitle_text = StringProperty("")
    detail_text = StringProperty("")
    stats_text = StringProperty("")
    image_source = StringProperty("")
    fallback_text = StringProperty("")


class EmpireCalcApp(App):
    main_tab = StringProperty("profile")
    ui_font_name = StringProperty(DEFAULT_UI_FONT)
    castle_values = ListProperty([])
    building_values = ListProperty([])
    unit_values = ListProperty([])
    attack_unit_values = ListProperty([])
    defense_tool_values = ListProperty([])
    governor_general_values = ListProperty([GOVERNOR_GENERAL_NONE])
    wave_values = ListProperty(["1"])
    attack_wave_count = StringProperty("1")
    profile_output = StringProperty("Создай аккаунт и выбери замок.")
    unit_picker_output = StringProperty("Выбери солдата из списка, чтобы увидеть его защиту и добавить в гарнизон.")
    unit_picker_image_source = StringProperty("")
    governor_general_summary = StringProperty("Выбери наместника из официального каталога или оставь ручной ввод бонусов.")
    defense_tool_picker_title = StringProperty("Выбери оборонительное орудие")
    defense_tool_picker_output = StringProperty("Выбери оборонительное орудие из каталога, укажи участок и количество.")
    defense_tool_picker_image_source = StringProperty("")
    attack_unit_picker_output = StringProperty("Выбери атакующего солдата, фланг, волну и количество.")
    attack_unit_picker_image_source = StringProperty("")
    upgrade_output = StringProperty("Нет расчёта.")
    upgrade_level_values = ListProperty([])
    upgrade_view_mode = StringProperty("list")
    upgrade_selected_building_name = StringProperty("")
    upgrade_selected_building_badge = StringProperty("")
    upgrade_selected_building_category = StringProperty("Категория не выбрана")
    upgrade_selected_building_description = StringProperty("Выбери здание из списка ниже, чтобы увидеть, зачем оно нужно и сколько ресурсов требуется на апгрейд.")
    upgrade_selected_building_summary = StringProperty("Каталог зданий загружается.")
    upgrade_detail_title = StringProperty("Профиль: —")
    upgrade_selected_building_image_source = StringProperty("")
    upgrade_current_level_value = StringProperty("")
    upgrade_target_level_value = StringProperty("")
    defense_output = StringProperty("Нет расчёта.")
    active_account_name = StringProperty("")
    active_account_avatar_source = StringProperty("")
    active_account_avatar_label = StringProperty("Локальный аккаунт")
    active_castle_name = StringProperty("")
    active_castle_card_title = StringProperty("Профиль не выбран")
    active_castle_card_subtitle = StringProperty("Замок / аванпост / мир")
    active_castle_card_summary = StringProperty("Открой аккаунт, затем выбери карточку профиля ниже.")
    active_castle_card_image_source = StringProperty("")
    wall_scene_caption = StringProperty("Стена замка: фронт")
    wall_scene_totals = StringProperty("На стене 0 солдат")
    wall_left_summary = StringProperty("Пусто")
    wall_center_summary = StringProperty("Пусто")
    wall_right_summary = StringProperty("Пусто")
    wall_active_flank = StringProperty("center")
    wall_active_flank_label = StringProperty("Центр")
    wall_active_units_output = StringProperty("На этом фланге пока нет солдат.")
    wall_add_panel_open = BooleanProperty(False)
    account_panel_open = BooleanProperty(False)

    def build(self):
        self.title = "Empire 4K Calculator"
        if platform not in {"android", "ios"}:
            Window.size = (1360, 920)
            if hasattr(Window, "system_size"):
                Window.system_size = (1360, 920)
        self.profile_store: dict[str, Any] = {"active_account": "", "accounts": {}}
        self.unit_catalog: list[dict[str, Any]] = []
        self.unit_index: dict[str, dict[str, Any]] = {}
        self.unit_display_index: dict[str, dict[str, Any]] = {}
        self.defense_tool_catalog: list[dict[str, Any]] = []
        self.defense_tool_index: dict[str, dict[str, Any]] = {}
        self.defense_tool_display_index: dict[str, dict[str, Any]] = {}
        self.general_catalog: list[dict[str, Any]] = []
        self.general_index_by_name: dict[str, dict[str, Any]] = {}
        self.general_index_by_id: dict[str, dict[str, Any]] = {}
        self.all_building_catalog: list[dict[str, Any]] = []
        self.building_catalog: list[dict[str, Any]] = []
        self.building_index_by_name: dict[str, dict[str, Any]] = {}
        self.attack_unit_catalog: list[dict[str, Any]] = []
        self.attack_unit_index: dict[str, dict[str, Any]] = {}
        self.attack_unit_display_index: dict[str, dict[str, Any]] = {}
        self._suspend_castle_events = False
        return Builder.load_file(KV_FILE)

    def on_start(self):
        self.load_unit_catalog()
        self.load_defense_tool_catalog()
        self.load_general_catalog()
        self.load_building_catalog()
        self.update_wave_values(self.attack_wave_count)
        self.load_profile_store()
        active_account = str(self.profile_store.get("active_account") or "").strip()
        if active_account and active_account in self.profile_store.get("accounts", {}):
            self.activate_account(active_account)
        else:
            self.initialize_empty_state()
        self.set_main_tab(self.main_tab)
        self.hide_main_tab_strip()

    def hide_main_tab_strip(self):
        if not self.root or "main_tabs" not in self.root.ids:
            return
        tabs = self.root.ids.main_tabs
        strip = getattr(tabs, "_tab_strip", None)
        if strip is None:
            return
        strip.size_hint_y = None
        strip.height = 0
        strip.opacity = 0
        for child in list(getattr(strip, "children", [])):
            if hasattr(child, "height"):
                child.height = 0
            if hasattr(child, "width"):
                child.width = 0
            if hasattr(child, "opacity"):
                child.opacity = 0

    def toggle_account_panel(self):
        self.open_profile_menu()

    def initialize_empty_state(self):
        self.castle_values = list(ACCOUNT_CASTLE_NAMES)
        if self.root and "castle_spinner" in self.root.ids and self.castle_values:
            self.root.ids.castle_spinner.text = self.castle_values[0]
        if self.root and "account_name" in self.root.ids:
            self.root.ids.account_name.text = ""
        if self.root and "governor_general_picker" in self.root.ids:
            self.root.ids.governor_general_picker.text = GOVERNOR_GENERAL_NONE
        if self.defense_tool_values:
            self.update_defense_tool_preview(self.defense_tool_values[0])
        else:
            self.update_defense_tool_preview("")
        self.profile_output = "Открой аккаунт, затем выбери или добавь профиль замка."
        self.defense_output = "Заполни профиль, атаку и нажми 'Проверить оборону'."
        self.upgrade_output = "Выбери здание из списка, затем укажи текущий и желаемый уровень."
        self.refresh_active_account_state()
        self.refresh_governor_general_summary()
        self.refresh_wall_scene()
        self.refresh_upgrade_state()

    def profiles_path(self) -> Path:
        base_dir = Path(self.user_data_dir)
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir / PROFILE_FILE_NAME

    def image_cache_dir(self) -> Path:
        base_dir = Path(self.user_data_dir)
        target = base_dir / "cache" / "images"
        target.mkdir(parents=True, exist_ok=True)
        return target

    def image_cache_digest(self, url: str) -> str:
        return hashlib.sha1(str(url or "").strip().encode("utf-8")).hexdigest()

    def image_suffix_from_content_type(self, content_type: str) -> str:
        normalized = str(content_type or "").split(";", 1)[0].strip().lower()
        return {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/webp": ".webp",
            "image/gif": ".gif",
            "image/bmp": ".bmp",
        }.get(normalized, ".png")

    def sniff_image_suffix(self, data: bytes) -> str:
        header = bytes(data[:16])
        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            return ".png"
        if header.startswith(b"\xff\xd8\xff"):
            return ".jpg"
        if header.startswith(b"GIF87a") or header.startswith(b"GIF89a"):
            return ".gif"
        if header.startswith(b"RIFF") and b"WEBP" in bytes(data[:32]):
            return ".webp"
        if header.startswith(b"BM"):
            return ".bmp"
        return ".png"

    def migrate_legacy_cached_image(self, url: str) -> Path | None:
        url = str(url or "").strip()
        if not url:
            return None
        digest = self.image_cache_digest(url)
        cache_dir = self.image_cache_dir()
        legacy = cache_dir / f"{digest}.img"
        if not legacy.exists():
            return None
        try:
            data = legacy.read_bytes()
            new_path = cache_dir / f"{digest}{self.sniff_image_suffix(data)}"
            if not new_path.exists():
                legacy.replace(new_path)
            else:
                legacy.unlink(missing_ok=True)
            return new_path if new_path.exists() else None
        except Exception:
            return legacy

    def cached_image_path(self, url: str) -> Path | None:
        url = str(url or "").strip()
        if not url:
            return None
        parsed = urlparse(url)
        if parsed.scheme in {"", "file"}:
            try:
                local = Path(parsed.path) if parsed.scheme == "file" else Path(url)
            except Exception:
                return None
            return local if local.exists() else None
        migrated = self.migrate_legacy_cached_image(url)
        if migrated and migrated.exists():
            return migrated
        digest = self.image_cache_digest(url)
        suffix = Path(parsed.path).suffix
        if suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
            suffix = ".png"
        return self.image_cache_dir() / f"{digest}{suffix}"

    def resolve_image_source(self, url: str) -> str:
        """Return a local file path if available; otherwise start caching and return empty until ready."""
        target = self.cached_image_path(url)
        if not target:
            return ""
        if target.exists():
            return str(target)
        parsed = urlparse(str(url or "").strip())
        if parsed.scheme not in {"http", "https"}:
            return ""

        if not hasattr(self, "_image_downloads"):
            self._image_downloads: set[str] = set()
        key = str(target)
        if key in self._image_downloads:
            return ""
        self._image_downloads.add(key)

        def _refresh_previews(_dt: float):
            try:
                if not self.root:
                    return
                resolved_target = self.cached_image_path(url)
                if resolved_target and resolved_target.exists():
                    unit_name = str(getattr(self, "_wall_selected_unit_name", "") or "").strip()
                    unit = self.unit_display_index.get(unit_name) or self.unit_index.get(unit_name)
                    if unit and str(unit.get("image_url") or "").strip() == str(url or "").strip():
                        self.unit_picker_image_source = str(resolved_target)
                        if getattr(self, "_wall_add_preview_image", None) is not None:
                            self._wall_add_preview_image.source = str(resolved_target)

                    attack_unit_name = str(self.root.ids.attack_unit_picker.text or "").strip() if "attack_unit_picker" in self.root.ids else ""
                    attack_unit = self.attack_unit_display_index.get(attack_unit_name) or self.attack_unit_index.get(attack_unit_name)
                    if attack_unit and str(attack_unit.get("image_url") or "").strip() == str(url or "").strip():
                        self.attack_unit_picker_image_source = str(resolved_target)
                    if getattr(self, "_wall_add_popup", None) is not None and self.wall_add_panel_open:
                        visible_units = getattr(self, "_wall_popup_visible_units", [])
                        if any(str(item.get("image_url") or "").strip() == str(url or "").strip() for item in visible_units):
                            self.refresh_wall_popup_ui()
                    building = self.building_record()
                    if building and str(building.get("image_url") or "").strip() == str(url or "").strip():
                        self.upgrade_selected_building_image_source = str(resolved_target)
                    self.refresh_upgrade_building_list()
            finally:
                self._image_downloads.discard(key)

        def _download():
            try:
                with urlopen(url, timeout=15) as resp:
                    content_type = getattr(resp.headers, "get_content_type", lambda: "")()
                    content = resp.read()
                suffix = self.image_suffix_from_content_type(content_type) if content_type else self.sniff_image_suffix(content)
                final_target = target.with_suffix(suffix)
                tmp = target.with_suffix(target.suffix + ".tmp")
                tmp.write_bytes(content)
                tmp.replace(final_target)
            except Exception:
                Clock.schedule_once(_refresh_previews, 0)
                return

            Clock.schedule_once(_refresh_previews, 0)

        threading.Thread(target=_download, daemon=True).start()
        return ""

    def load_profile_store(self):
        path = self.profiles_path()
        if not path.exists():
            self.profile_store = {"active_account": "", "accounts": {}}
            return
        try:
            self.profile_store = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.profile_store = {"active_account": "", "accounts": {}}

    def save_profile_store(self):
        path = self.profiles_path()
        path.write_text(json.dumps(self.profile_store, ensure_ascii=False, indent=2), encoding="utf-8")

    def safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            cleaned = str(value).strip().replace("\xa0", " ").replace(" ", "").replace(",", ".")
            return float(cleaned)
        except (TypeError, ValueError):
            return default

    def defense_tool_sort_key(self, tool: dict[str, Any]) -> tuple[Any, ...]:
        category = str(tool.get("category") or "")
        power = max(
            self.safe_int(tool.get("def_melee_bonus"), 0),
            self.safe_int(tool.get("wall_capacity_bonus"), 0),
            self.safe_int(tool.get("defense_power_bonus"), 0),
            self.safe_int(tool.get("yard_defense_power_bonus"), 0),
            self.safe_int(tool.get("kill_attacking_any_yard"), 0),
            self.safe_int(tool.get("kill_attacking_melee_yard"), 0),
            self.safe_int(tool.get("kill_attacking_ranged_yard"), 0),
        )
        return (
            category,
            -power,
            -(self.safe_int(tool.get("level"), 0)),
            str(tool.get("display_name") or tool.get("name") or ""),
        )

    def load_defense_tool_catalog(self):
        raw_catalog = sorted(get_defense_tools_catalog(), key=self.defense_tool_sort_key)
        by_name: dict[str, dict[str, Any]] = {}
        by_display: dict[str, dict[str, Any]] = {}
        for tool in raw_catalog:
            name_key = str(tool.get("name") or "").strip()
            display_key = str(tool.get("display_name") or tool.get("name") or "").strip()
            if name_key and name_key not in by_name:
                by_name[name_key] = tool
            if display_key and display_key not in by_display:
                by_display[display_key] = tool
        self.defense_tool_catalog = list(by_display.values())
        self.defense_tool_index = by_name
        self.defense_tool_display_index = by_display
        self.defense_tool_values = [str(tool.get("display_name") or tool.get("name") or "") for tool in self.defense_tool_catalog]

    def load_general_catalog(self):
        self.general_catalog = list(get_generals_catalog())
        self.general_index_by_name = {str(item.get("name") or "").strip(): item for item in self.general_catalog if str(item.get("name") or "").strip()}
        self.general_index_by_id = {str(item.get("general_id") or "").strip(): item for item in self.general_catalog if str(item.get("general_id") or "").strip()}
        self.governor_general_values = [GOVERNOR_GENERAL_NONE] + [str(item.get("name") or "") for item in self.general_catalog if str(item.get("name") or "").strip()]

    def load_building_catalog(self):
        self.all_building_catalog = list(get_buildings_catalog())
        self.refresh_available_building_catalog()

    def castle_scope_key(self, castle_key: str | None = None) -> str:
        value = str(castle_key or self.active_castle_name or "Основной замок").strip().lower()
        if "аванпост" in value:
            return "outpost"
        if value == "основной замок":
            return "main"
        return "world"

    def building_available_for_scope(self, building: dict[str, Any], scope: str) -> bool:
        name = str(building.get("name") or "").strip()
        resource_fields = {str(field).strip() for field in (building.get("resource_fields") or []) if str(field).strip()}
        has_world_resources = bool(resource_fields & WORLD_RESOURCE_FIELDS)
        is_world_only = bool(resource_fields) and resource_fields.issubset(WORLD_RESOURCE_FIELDS)
        if scope == "outpost":
            return name in OUTPOST_AVAILABLE_BUILDING_NAMES
        if scope == "world":
            return has_world_resources
        return not is_world_only

    def refresh_available_building_catalog(self):
        scope = self.castle_scope_key()
        self.building_catalog = [item for item in self.all_building_catalog if self.building_available_for_scope(item, scope)]
        self.building_index_by_name = {}
        for item in self.building_catalog:
            name = str(item.get("name") or "").strip()
            display_name = str(item.get("display_name") or name).strip()
            if name:
                self.building_index_by_name[name] = item
            if display_name and display_name not in self.building_index_by_name:
                self.building_index_by_name[display_name] = item
        self.building_values = [str(item.get("display_name") or item.get("name") or "") for item in self.building_catalog if str(item.get("display_name") or item.get("name") or "").strip()]
        if self.building_values and self.upgrade_selected_building_name not in self.building_index_by_name:
            self.upgrade_selected_building_name = self.building_values[0]
        if not self.building_values:
            self.upgrade_selected_building_name = ""
        self.refresh_upgrade_state()

    def building_record(self, building_name: str | None = None) -> dict[str, Any] | None:
        key = str(building_name or self.upgrade_selected_building_name or "").strip()
        if not key:
            return None
        return self.building_index_by_name.get(key)

    def building_progress_key(self, record: dict[str, Any] | None = None, building_name: str | None = None) -> str:
        target = record or self.building_record(building_name)
        return str((target or {}).get("name") or (target or {}).get("display_name") or building_name or "").strip()

    def castle_building_levels(self, castle: dict[str, Any] | None = None) -> dict[str, Any]:
        record = castle or self.current_castle_record()
        if not record:
            return {}
        levels = record.get("building_levels")
        if not isinstance(levels, dict):
            levels = {}
            record["building_levels"] = levels
        return levels

    def saved_building_level(self, record: dict[str, Any] | None = None, castle: dict[str, Any] | None = None) -> str:
        key = self.building_progress_key(record)
        if not key:
            return ""
        return str(self.castle_building_levels(castle).get(key) or "").strip()

    def store_building_level(self, level_value: str, record: dict[str, Any] | None = None):
        castle = self.current_castle_record()
        if not castle:
            return
        key = self.building_progress_key(record)
        if not key:
            return
        normalized = str(level_value or "").strip()
        levels = self.castle_building_levels(castle)
        if normalized:
            levels[key] = normalized
        else:
            levels.pop(key, None)
        account = self.current_account()
        if account and self.active_castle_name:
            account.setdefault("castles", {})[self.active_castle_name] = castle
        self.save_profile_store()

    def short_badge_text(self, value: str) -> str:
        words = [part for part in str(value or "").replace("-", " ").split() if part]
        if not words:
            return "?"
        if len(words) == 1:
            return words[0][:2].upper()
        return (words[0][:1] + words[1][:1]).upper()

    def building_image_slug(self, value: str) -> str:
        text = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower())
        text = text.strip("_")
        return text or "building"

    def local_building_image_path(self, record: dict[str, Any] | None = None, building_name: str | None = None) -> Path | None:
        target = record or self.building_record(building_name)
        candidates = [
            str((target or {}).get("display_name") or "").strip(),
            str((target or {}).get("name") or "").strip(),
            str(building_name or "").strip(),
        ]
        for candidate in candidates:
            override = LOCAL_BUILDING_IMAGE_OVERRIDES.get(candidate)
            if override and override.exists():
                return override

        slug_sources = [
            str((target or {}).get("name") or "").strip(),
            str((target or {}).get("display_name") or "").strip(),
            str(building_name or "").strip(),
        ]
        for source in slug_sources:
            if not source:
                continue
            slug = self.building_image_slug(source)
            for extension in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"):
                local_path = LOCAL_BUILDING_IMAGE_DIR / f"{slug}{extension}"
                if local_path.exists():
                    return local_path
        return None

    def building_image_source(self, building_name: str) -> str:
        name = str(building_name or "Здание").strip() or "Здание"
        record = self.building_record(name)
        local_path = self.local_building_image_path(record, name)
        if local_path and local_path.exists():
            return str(local_path)

        image_url = str((record or {}).get("image_url") or "").strip()
        if not image_url:
            return ""
        target = self.cached_image_path(image_url)
        if target and target.exists():
            return str(target)
        self.resolve_image_source(image_url)
        return ""

    def building_resource_label(self, field_name: str) -> str:
        return {
            "build_tokens": "Молотки",
            "upgrade_tokens": "Жетоны улучшения",
            "talers": "Талеры",
            "ducats": "Дукаты",
            "plaster": "Гипс",
            "dragon_scale_tiles": "Чешуя дракона",
            "rubies": "Рубины",
        }.get(str(field_name or ""), str(field_name or "Ресурс"))

    def building_level_step_text(self, previous_level: str, row: dict[str, Any], resource_fields: list[str]) -> str:
        next_level = str(row.get("level") or "?").strip() or "?"
        resources: list[str] = []
        for field in resource_fields:
            value = row.get(field)
            if value in {None, ""}:
                continue
            amount = self.safe_int(value, 0)
            if amount <= 0:
                continue
            resources.append(f"{self.building_resource_label(field)}: {self.format_compact_number(amount)}")
        resource_text = ", ".join(resources) if resources else "Без затрат"
        return f"{previous_level} -> {next_level}  |  {resource_text}"

    def upgrade_level_index(self, level_labels: list[str], value: str) -> int:
        normalized = str(value or "").strip()
        try:
            return level_labels.index(normalized)
        except ValueError:
            return 0

    def on_upgrade_current_level_changed(self, value: str):
        self.upgrade_current_level_value = str(value or "").strip()
        self.store_building_level(self.upgrade_current_level_value)
        self.refresh_upgrade_state()

    def on_upgrade_target_level_changed(self, value: str):
        self.upgrade_target_level_value = str(value or "").strip()
        self.refresh_upgrade_state()

    def select_upgrade_building(self, building_name: str):
        self.upgrade_selected_building_name = str(building_name or "").strip()
        self.refresh_upgrade_state()

    def open_upgrade_building_detail(self, building_name: str):
        self.upgrade_selected_building_name = str(building_name or "").strip()
        self.refresh_upgrade_state()
        self.upgrade_view_mode = "detail"

    def show_upgrade_building_list(self):
        self.upgrade_view_mode = "list"

    def refresh_upgrade_state(self):
        record = self.building_record()
        if not self.building_catalog:
            self.upgrade_selected_building_name = ""
            self.upgrade_selected_building_badge = ""
            self.upgrade_level_values = []
            self.upgrade_view_mode = "list"
            self.upgrade_detail_title = "Профиль: —"
            self.upgrade_selected_building_category = "Каталог не загружен"
            self.upgrade_selected_building_description = "Не удалось загрузить каталог зданий. Проверь файл official_buildings_catalog.json."
            self.upgrade_selected_building_summary = "Данные об улучшениях пока недоступны."
            self.upgrade_selected_building_image_source = ""
            self.upgrade_current_level_value = ""
            self.upgrade_target_level_value = ""
            self.upgrade_output = "Каталог зданий пуст. Сначала синхронизируй данные улучшений."
            self.refresh_upgrade_building_list()
            return
        if record is None and self.building_catalog:
            self.upgrade_selected_building_name = str(self.building_catalog[0].get("display_name") or self.building_catalog[0].get("name") or "")
            record = self.building_record()
        if record is None:
            return
        level_labels = [str(item) for item in (record.get("level_labels") or []) if str(item).strip()]
        self.upgrade_level_values = level_labels
        saved_level = self.saved_building_level(record)
        if saved_level and saved_level in level_labels:
            self.upgrade_current_level_value = saved_level
        elif not self.upgrade_current_level_value or self.upgrade_current_level_value not in level_labels:
            self.upgrade_current_level_value = level_labels[0] if level_labels else ""
        if not self.upgrade_target_level_value or self.upgrade_target_level_value not in level_labels:
            self.upgrade_target_level_value = level_labels[-1] if level_labels else self.upgrade_current_level_value
        if level_labels:
            current_index = self.upgrade_level_index(level_labels, self.upgrade_current_level_value)
            target_index = self.upgrade_level_index(level_labels, self.upgrade_target_level_value)
            if target_index < current_index:
                self.upgrade_target_level_value = self.upgrade_current_level_value
        self.upgrade_selected_building_name = str(record.get("display_name") or record.get("name") or "")
        self.upgrade_selected_building_badge = self.short_badge_text(self.upgrade_selected_building_name)
        self.upgrade_selected_building_category = str(record.get("category") or "Инфраструктура")
        self.upgrade_selected_building_description = str(record.get("description") or "Описание здания пока не заполнено.")
        resources_text = ", ".join(self.building_resource_label(field) for field in (record.get("resource_fields") or [])) or "Ресурсы не указаны"
        castle_title = self.castle_display_name(self.active_castle_name or "Основной замок", self.current_castle_record())
        self.upgrade_detail_title = f"Профиль: {castle_title}"
        self.upgrade_selected_building_summary = (
            f"Профиль: {castle_title}\n"
            f"Доступные уровни: {level_labels[0] if level_labels else '—'} → {level_labels[-1] if level_labels else '—'}\n"
            f"Отмеченный уровень: {self.upgrade_current_level_value or '—'}\n"
            f"Ресурсы: {resources_text}"
        )
        self.upgrade_selected_building_image_source = self.building_image_source(self.upgrade_selected_building_name)
        self.calculate_upgrade()
        self.refresh_upgrade_building_list()

    def refresh_upgrade_building_list(self):
        if not self.root or "upgrade_building_list" not in self.root.ids:
            return
        container = self.root.ids.upgrade_building_list
        container.clear_widgets()
        if not self.building_catalog:
            empty = Factory.BodyText(size_hint_y=None, height=dp(46))
            empty.text = "Для текущего замка или мира нет подходящих зданий в каталоге."
            container.add_widget(empty)
            return
        for building in self.building_catalog:
            title = str(building.get("display_name") or building.get("name") or "Здание")
            subtitle = str(building.get("category") or "Инфраструктура")
            detail = str(building.get("description") or "")
            current_level = self.saved_building_level(building)
            row = WallUnitRow(
                selected=title == self.upgrade_selected_building_name,
                title_text=title,
                subtitle_text=subtitle,
                detail_text=detail,
                stats_text=f"Текущий ур.: {current_level or 'не отмечен'}",
                image_source=self.building_image_source(title),
                fallback_text=self.short_badge_text(title),
            )
            row.bind(on_release=lambda _instance, value=title: self.open_upgrade_building_detail(value))
            container.add_widget(row)

    def governor_general_record(self, governor: dict[str, Any] | None = None) -> dict[str, Any] | None:
        source = governor or self.governor_profile_from_form()
        general_name = str(source.get("general_name") or "").strip()
        general_id = str(source.get("general_id") or "").strip()
        if general_name and general_name != GOVERNOR_GENERAL_NONE:
            return self.general_index_by_name.get(general_name)
        if general_id:
            return self.general_index_by_id.get(general_id)
        return None

    def governor_skill_entry(self, general: dict[str, Any] | None, field_name: str) -> dict[str, Any] | None:
        if not general:
            return None
        spec = GOVERNOR_SKILL_SPECS.get(field_name) or {}
        prefixes = tuple(str(item).lower() for item in spec.get("raw_prefixes") or ())
        if not prefixes:
            return None
        for skill in general.get("skills") or []:
            raw_name = str(skill.get("raw_name") or skill.get("name") or "").strip().lower()
            if any(raw_name.startswith(prefix) for prefix in prefixes):
                return skill
        return None

    def governor_skill_max_level(self, general: dict[str, Any] | None, field_name: str) -> int:
        skill = self.governor_skill_entry(general, field_name)
        if not skill:
            return 0
        return max(self.safe_int(skill.get("max_level"), 0), self.safe_int(skill.get("current_level"), 0), len(skill.get("levels") or []))

    def governor_skill_value_per_level(self, skill: dict[str, Any] | None) -> float:
        if not skill:
            return 0.0
        effects = str(skill.get("effects") or "")
        if "&" not in effects:
            return 0.0
        return self.safe_float(effects.split("&", 1)[1], 0.0)

    def governor_skill_level_key(self, field_name: str) -> str:
        return f"skill_{field_name}_level"

    def governor_skill_selected_level(self, field_name: str, governor: dict[str, Any] | None = None) -> int:
        source = governor or self.governor_profile_from_form()
        return max(0, self.safe_int(source.get(self.governor_skill_level_key(field_name)), 0))

    def governor_auto_skill_values(self, governor: dict[str, Any] | None = None) -> dict[str, float]:
        source = governor or self.governor_profile_from_form()
        general = self.governor_general_record(source)
        totals = {field_name: 0.0 for field_name in GOVERNOR_SKILL_SPECS}
        for field_name in GOVERNOR_SKILL_SPECS:
            skill = self.governor_skill_entry(general, field_name)
            if not skill:
                continue
            max_level = self.governor_skill_max_level(general, field_name)
            selected_level = min(self.governor_skill_selected_level(field_name, source), max_level)
            totals[field_name] = round(self.governor_skill_value_per_level(skill) * selected_level, 2)
        return totals

    def build_governor_general_summary(self, governor: dict[str, Any] | None = None) -> str:
        source = governor or self.governor_profile_from_form()
        general = self.governor_general_record(source)
        if not general:
            return "Наместник не выбран. Ниже можно вручную ввести бонусы экипировки и строений."
        lines = [str(general.get("name") or "Наместник")]
        rarity_name = str(general.get("rarity_name") or "").strip()
        if rarity_name:
            lines.append(f"Редкость: {rarity_name}")
        auto_values = self.governor_auto_skill_values(source)
        skill_lines = []
        for field_name, spec in GOVERNOR_SKILL_SPECS.items():
            value = auto_values.get(field_name) or 0
            level = self.governor_skill_selected_level(field_name, source)
            max_level = self.governor_skill_max_level(general, field_name)
            if level <= 0 and value <= 0:
                continue
            suffix = "%" if field_name != "courtyard_size_bonus" else ""
            skill_lines.append(f"{spec['label']}: {value}{suffix} (ур. {level}/{max_level})")
        if skill_lines:
            lines.append("")
            lines.extend(skill_lines)
        else:
            lines.append("")
            lines.append("Укажи уровни защитных навыков ниже, чтобы автоподставить бонусы из каталога.")
        return "\n".join(lines)

    def refresh_governor_general_summary(self):
        self.governor_general_summary = self.build_governor_general_summary()

    def on_governor_general_selected(self, value: str):
        if not self.root:
            return
        ids = self.root.ids
        selected_name = str(value or "").strip()
        if selected_name == GOVERNOR_GENERAL_NONE:
            if "governor_general_name" in ids:
                ids.governor_general_name.text = GOVERNOR_GENERAL_NONE
            if "governor_general_id" in ids:
                ids.governor_general_id.text = ""
            self.refresh_governor_general_summary()
            return
        general = self.general_index_by_name.get(selected_name)
        if not general:
            self.refresh_governor_general_summary()
            return
        if "governor_general_name" in ids:
            ids.governor_general_name.text = str(general.get("name") or "")
        if "governor_general_id" in ids:
            ids.governor_general_id.text = str(general.get("general_id") or "")
        self.refresh_governor_general_summary()

    def on_governor_skill_input_changed(self, *_args):
        self.refresh_governor_general_summary()
        self.refresh_wall_scene()

    def governor_profile_from_form(self) -> dict[str, str]:
        ids = self.root.ids
        general_name = str(ids.governor_general_name.text or "").strip() if "governor_general_name" in ids else ""
        if general_name == GOVERNOR_GENERAL_NONE:
            general_name = ""
        return {
            "general_id": str(ids.governor_general_id.text or "").strip() if "governor_general_id" in ids else "",
            "general_name": general_name,
            "melee_bonus": ids.governor_melee_bonus.text,
            "ranged_bonus": ids.governor_ranged_bonus.text,
            "flank_bonus": ids.governor_flank_bonus.text if "governor_flank_bonus" in ids else "",
            "courtyard_bonus": ids.governor_courtyard_bonus.text,
            "center_bonus": ids.governor_center_bonus.text,
            "overall_bonus": ids.governor_overall_bonus.text,
            "wall_defense": ids.governor_wall_defense.text,
            "gate_defense": ids.governor_gate_defense.text,
            "moat_defense": ids.governor_moat_defense.text,
            "wall_limit_bonus": ids.governor_wall_limit_bonus.text,
            "wall_limit_percent_bonus": ids.governor_wall_limit_percent_bonus.text if "governor_wall_limit_percent_bonus" in ids else "",
            "courtyard_size_bonus": ids.governor_courtyard_size_bonus.text if "governor_courtyard_size_bonus" in ids else "",
            "skill_flank_bonus_level": ids.skill_flank_bonus_level.text if "skill_flank_bonus_level" in ids else "",
            "skill_center_bonus_level": ids.skill_center_bonus_level.text if "skill_center_bonus_level" in ids else "",
            "skill_courtyard_bonus_level": ids.skill_courtyard_bonus_level.text if "skill_courtyard_bonus_level" in ids else "",
            "skill_wall_limit_percent_bonus_level": ids.skill_wall_limit_percent_bonus_level.text if "skill_wall_limit_percent_bonus_level" in ids else "",
            "skill_courtyard_size_bonus_level": ids.skill_courtyard_size_bonus_level.text if "skill_courtyard_size_bonus_level" in ids else "",
        }

    def governor_from_form(self) -> dict[str, str]:
        profile = self.governor_profile_from_form()
        auto_values = self.governor_auto_skill_values(profile)
        result = dict(profile)
        base_wall_units = self.safe_int(self.root.ids.wall_units_base.text if self.root and "wall_units_base" in self.root.ids else "", 0)
        total_wall_limit_percent = self.safe_float(profile.get("wall_limit_percent_bonus"), 0.0) + auto_values.get("wall_limit_percent_bonus", 0.0)
        result["flank_bonus"] = str(self.safe_float(profile.get("flank_bonus"), 0.0) + auto_values.get("flank_bonus", 0.0))
        result["center_bonus"] = str(self.safe_float(profile.get("center_bonus"), 0.0) + auto_values.get("center_bonus", 0.0))
        result["courtyard_bonus"] = str(self.safe_float(profile.get("courtyard_bonus"), 0.0) + auto_values.get("courtyard_bonus", 0.0))
        result["wall_limit_percent_bonus"] = str(total_wall_limit_percent)
        result["courtyard_size_bonus"] = str(self.safe_float(profile.get("courtyard_size_bonus"), 0.0) + auto_values.get("courtyard_size_bonus", 0.0))
        additive_wall_limit = self.safe_int(profile.get("wall_limit_bonus"), 0)
        if base_wall_units > 0 and total_wall_limit_percent > 0:
            additive_wall_limit += int(round(base_wall_units * total_wall_limit_percent / 100.0))
        result["wall_limit_bonus"] = str(additive_wall_limit)
        return result

    def defense_tool_image_source(self, tool: dict[str, Any], eager: bool = False) -> str:
        url = str(tool.get("image_url") or "").strip()
        if not url:
            return ""
        target = self.cached_image_path(url)
        if target and target.exists():
            return str(target)
        if eager:
            return self.resolve_image_source(url)
        return ""

    def update_defense_tool_preview(self, tool_name: str):
        tool = self.defense_tool_display_index.get(str(tool_name)) or self.defense_tool_index.get(str(tool_name))
        if not tool:
            self._defense_tool_selected_name = ""
            self.defense_tool_picker_title = "Выбери оборонительное орудие"
            self.defense_tool_picker_output = "Оборонительное орудие не выбрано."
            self.defense_tool_picker_image_source = ""
            return
        self._defense_tool_selected_name = str(tool.get("display_name") or tool.get("name") or "")
        self.defense_tool_picker_title = self._defense_tool_selected_name
        self.defense_tool_picker_output = self.defense_tool_preview_text(tool)
        self.defense_tool_picker_image_source = self.defense_tool_image_source(tool, eager=True)

    def add_or_update_defense_tool_entry(self):
        if not self.root:
            return
        ids = self.root.ids
        tool_name = str(getattr(self, "_defense_tool_selected_name", "") or "").strip()
        zone = str(getattr(getattr(self, "_defense_tool_add_zone", None), "text", "all") or "all").strip().lower()
        count = self.safe_int(getattr(getattr(self, "_defense_tool_add_count", None), "text", ""), 0)
        tool = self.defense_tool_display_index.get(tool_name) or self.defense_tool_index.get(tool_name)
        if not tool:
            self.defense_tool_picker_output = "Сначала выбери орудие из каталога."
            return
        if zone not in DEFENSE_TOOL_ZONE_VALUES:
            zone = "all"
        if count <= 0:
            self.defense_tool_picker_output = "Укажи количество орудий больше нуля."
            return
        rows = self.parse_defensive_tool_lines(ids.defensive_tools_lines.text)
        editing_index = getattr(self, "_editing_defense_tool_index", None)
        payload = {
            "flank": zone,
            "name": str(tool.get("display_name") or tool.get("name") or tool_name),
            "count": str(count),
        }
        if editing_index is not None and 0 <= editing_index < len(rows):
            rows[editing_index] = payload
            self._editing_defense_tool_index = None
        else:
            rows.append(payload)
        ids.defensive_tools_lines.text = self.serialize_defensive_tool_lines(rows)
        self.defense_tool_picker_output = self.defense_tool_preview_text(tool)
        if getattr(self, "_defense_tool_add_count", None) is not None:
            self._defense_tool_add_count.text = ""
        if getattr(self, "_defense_tool_add_slider", None) is not None:
            self._defense_tool_add_slider.value = 0
        if getattr(self, "_defense_tool_add_zone", None) is not None:
            self._defense_tool_add_zone.text = "all"
        if getattr(self, "_defense_tool_add_apply_button", None) is not None:
            self._defense_tool_add_apply_button.text = "Добавить"
        if self.active_account_name:
            self.store_current_castle(silent=True)
        self.refresh_wall_scene()
        self.close_defense_tool_add_panel()

    def edit_defense_tool_entry(self, index: int):
        if not self.root:
            return
        rows = self.parse_defensive_tool_lines(self.root.ids.defensive_tools_lines.text)
        if index < 0 or index >= len(rows):
            return
        row = rows[index]
        popup = self.ensure_defense_tool_add_popup()
        self.update_defense_tool_preview(str(row.get("name") or ""))
        if getattr(self, "_defense_tool_add_zone", None) is not None:
            self._defense_tool_add_zone.text = str(row.get("flank") or "all")
        count = self.safe_int(row.get("count"), 0)
        if getattr(self, "_defense_tool_add_count", None) is not None:
            self._defense_tool_add_count.text = str(count) if count > 0 else ""
        if getattr(self, "_defense_tool_add_slider", None) is not None:
            self._defense_tool_add_slider.value = count
        if getattr(self, "_defense_tool_add_apply_button", None) is not None:
            self._defense_tool_add_apply_button.text = "Сохранить"
        self._editing_defense_tool_index = index
        popup.title = "Изменить оборонительное орудие"
        self.refresh_defense_tool_popup_ui()
        popup.open()

    def remove_defense_tool_entry(self, index: int):
        if not self.root:
            return
        rows = self.parse_defensive_tool_lines(self.root.ids.defensive_tools_lines.text)
        if index < 0 or index >= len(rows):
            return
        rows.pop(index)
        self.root.ids.defensive_tools_lines.text = self.serialize_defensive_tool_lines(rows)
        if getattr(self, "_editing_defense_tool_index", None) == index:
            self._editing_defense_tool_index = None
            self.close_defense_tool_add_panel()
        if self.active_account_name:
            self.store_current_castle(silent=True)
        self.refresh_wall_scene()

    def toggle_defense_tool_add_panel(self):
        popup = self.ensure_defense_tool_add_popup()
        self._editing_defense_tool_index = None
        popup.title = "Добавить оборонительное орудие"
        if not getattr(self, "_defense_tool_selected_name", "") and self.defense_tool_values:
            self.update_defense_tool_preview(self.defense_tool_values[0])
        if getattr(self, "_defense_tool_add_zone", None) is not None:
            self._defense_tool_add_zone.text = "all"
        if getattr(self, "_defense_tool_add_count", None) is not None:
            self._defense_tool_add_count.text = ""
        if getattr(self, "_defense_tool_add_slider", None) is not None:
            self._defense_tool_add_slider.value = 0
        if getattr(self, "_defense_tool_add_apply_button", None) is not None:
            self._defense_tool_add_apply_button.text = "Добавить"
        self.refresh_defense_tool_popup_ui()
        popup.open()

    def close_defense_tool_add_panel(self):
        popup = getattr(self, "_defense_tool_add_popup", None)
        if popup:
            popup.dismiss()

    def ensure_defense_tool_add_popup(self) -> Popup:
        popup = getattr(self, "_defense_tool_add_popup", None)
        if popup is not None:
            return popup

        content = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        search_input = Factory.AppInput()
        search_input.hint_text = "Поиск оборонительного орудия"
        search_input.bind(text=self.on_defense_tool_popup_search_changed)

        preview_card = BoxLayout(size_hint_y=None, height=dp(156), spacing=dp(10))
        preview_image = AsyncImage(size_hint_x=None, width=dp(88), fit_mode="contain")
        preview = Factory.OutputArea()
        preview_card.add_widget(preview_image)
        preview_card.add_widget(preview)

        list_scroll = ScrollView(do_scroll_x=False, size_hint=(1, 1), bar_width=dp(6))
        tool_list = GridLayout(cols=1, size_hint_y=None, spacing=dp(6), padding=[0, 0, 0, dp(6)])
        tool_list.bind(minimum_height=tool_list.setter("height"))
        list_scroll.add_widget(tool_list)

        controls = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        zone_spinner = Factory.AppSpinner(text="all", values=DEFENSE_TOOL_ZONE_VALUES)
        count_input = Factory.AppInput()
        count_input.hint_text = "Количество орудий"
        count_input.input_filter = "int"
        count_input.bind(text=self.on_defense_tool_popup_count_changed)
        controls.add_widget(zone_spinner)
        controls.add_widget(count_input)

        slider = Slider(min=0, max=5000, value=0, step=1, size_hint_y=None, height=dp(36))
        slider.bind(value=self.on_defense_tool_popup_slider_changed)

        buttons = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        cancel_button = Factory.SecondaryButton(text="Отмена")
        cancel_button.bind(on_release=lambda *_: self.close_defense_tool_add_panel())
        apply_button = Factory.AppButton(text="Добавить")
        apply_button.bind(on_release=lambda *_: self.add_or_update_defense_tool_entry())
        buttons.add_widget(cancel_button)
        buttons.add_widget(apply_button)

        content.add_widget(search_input)
        content.add_widget(preview_card)
        content.add_widget(list_scroll)
        content.add_widget(controls)
        content.add_widget(slider)
        content.add_widget(buttons)

        popup = Popup(
            title="Добавить оборонительное орудие",
            content=content,
            size_hint=(0.96, 0.92),
            auto_dismiss=True,
            separator_height=0,
        )
        popup.bind(on_dismiss=self.on_defense_tool_popup_dismiss)
        self._defense_tool_add_popup = popup
        self._defense_tool_add_search = search_input
        self._defense_tool_add_preview = preview
        self._defense_tool_add_preview_image = preview_image
        self._defense_tool_add_list = tool_list
        self._defense_tool_add_zone = zone_spinner
        self._defense_tool_add_count = count_input
        self._defense_tool_add_slider = slider
        self._defense_tool_add_apply_button = apply_button
        self._defense_tool_add_syncing = False
        return popup

    def on_defense_tool_popup_dismiss(self, *_args):
        self._editing_defense_tool_index = None
        if getattr(self, "_defense_tool_add_apply_button", None) is not None:
            self._defense_tool_add_apply_button.text = "Добавить"

    def on_defense_tool_popup_search_changed(self, _instance, _value: str):
        self.refresh_defense_tool_popup_ui()

    def filtered_defense_tool_popup_tools(self) -> list[dict[str, Any]]:
        search_value = str(getattr(self, "_defense_tool_add_search", None).text or "").strip().lower() if getattr(self, "_defense_tool_add_search", None) is not None else ""
        filtered: list[dict[str, Any]] = []
        for tool in self.defense_tool_catalog:
            haystack = " ".join(
                [
                    str(tool.get("display_name") or ""),
                    str(tool.get("name") or ""),
                    str(tool.get("category") or ""),
                ]
            ).lower()
            if search_value and search_value not in haystack:
                continue
            filtered.append(tool)
        return filtered

    def select_defense_tool_popup_tool(self, tool_name: str):
        self.update_defense_tool_preview(tool_name)
        self.refresh_defense_tool_popup_ui()

    def on_defense_tool_popup_count_changed(self, _instance, value: str):
        if getattr(self, "_defense_tool_add_syncing", False):
            return
        slider = getattr(self, "_defense_tool_add_slider", None)
        if slider is None:
            return
        count = max(0, self.safe_int(value, 0))
        if count > slider.max:
            slider.max = count
        self._defense_tool_add_syncing = True
        slider.value = count
        self._defense_tool_add_syncing = False

    def on_defense_tool_popup_slider_changed(self, _instance, value: float):
        if getattr(self, "_defense_tool_add_syncing", False):
            return
        count_input = getattr(self, "_defense_tool_add_count", None)
        if count_input is None:
            return
        self._defense_tool_add_syncing = True
        count_input.text = str(int(value)) if int(value) > 0 else ""
        self._defense_tool_add_syncing = False

    def defense_tool_popup_badge(self, tool: dict[str, Any]) -> str:
        category = str(tool.get("category") or "без категории")
        return f"Категория: {category}"

    def defense_tool_popup_detail_text(self, tool: dict[str, Any]) -> str:
        parts: list[str] = []
        if self.safe_int(tool.get("def_melee_bonus"), 0):
            parts.append(f"Ближняя защита +{self.safe_int(tool.get('def_melee_bonus'), 0)}%")
        if self.safe_int(tool.get("wall_capacity_bonus"), 0):
            parts.append(f"Лимит стены +{self.safe_int(tool.get('wall_capacity_bonus'), 0)}")
        if self.safe_int(tool.get("defense_power_bonus"), 0):
            parts.append(f"Сила защиты +{self.safe_int(tool.get('defense_power_bonus'), 0)}%")
        if self.safe_int(tool.get("yard_defense_power_bonus"), 0):
            parts.append(f"Двор +{self.safe_int(tool.get('yard_defense_power_bonus'), 0)}%")
        return " · ".join(parts[:2]) if parts else "Нет ключевых бонусов в текущей модели"

    def defense_tool_popup_stats_text(self, tool: dict[str, Any]) -> str:
        yard_kills = max(
            self.safe_int(tool.get("kill_attacking_any_yard"), 0),
            self.safe_int(tool.get("kill_attacking_melee_yard"), 0),
            self.safe_int(tool.get("kill_attacking_ranged_yard"), 0),
        )
        if yard_kills > 0:
            return f"Двор\n{yard_kills}"
        if self.safe_int(tool.get("wall_capacity_bonus"), 0):
            return f"Стена\n+{self.safe_int(tool.get('wall_capacity_bonus'), 0)}"
        if self.safe_int(tool.get("def_melee_bonus"), 0):
            return f"Ближн.\n+{self.safe_int(tool.get('def_melee_bonus'), 0)}%"
        if self.safe_int(tool.get("defense_power_bonus"), 0):
            return f"Сила\n+{self.safe_int(tool.get('defense_power_bonus'), 0)}%"
        return "Эффект\n0"

    def refresh_defense_tool_popup_ui(self):
        if getattr(self, "_defense_tool_add_popup", None) is None:
            return
        visible_tools = self.filtered_defense_tool_popup_tools()
        visible_names = {str(tool.get("display_name") or tool.get("name") or "") for tool in visible_tools}
        if visible_tools and getattr(self, "_defense_tool_selected_name", "") not in visible_names:
            first_name = str(visible_tools[0].get("display_name") or visible_tools[0].get("name") or "")
            self.update_defense_tool_preview(first_name)

        selected_tool = self.defense_tool_display_index.get(getattr(self, "_defense_tool_selected_name", "")) or self.defense_tool_index.get(getattr(self, "_defense_tool_selected_name", ""))
        if selected_tool:
            self._defense_tool_add_preview.text = self.defense_tool_preview_text(selected_tool)
            if getattr(self, "_defense_tool_add_preview_image", None) is not None:
                self._defense_tool_add_preview_image.source = self.defense_tool_image_source(selected_tool, eager=True)
        else:
            self._defense_tool_add_preview.text = "Нет орудий под текущий фильтр поиска."
            if getattr(self, "_defense_tool_add_preview_image", None) is not None:
                self._defense_tool_add_preview_image.source = ""

        self._defense_tool_add_list.clear_widgets()
        if not visible_tools:
            empty = Factory.BodyText(size_hint_y=None, height=dp(46))
            empty.text = "Нет подходящих оборонительных орудий. Попробуй изменить поиск."
            self._defense_tool_add_list.add_widget(empty)
            return

        for tool in visible_tools[:220]:
            display_name = str(tool.get("display_name") or tool.get("name") or "")
            row = WallUnitRow(
                selected=display_name == getattr(self, "_defense_tool_selected_name", ""),
                title_text=display_name,
                subtitle_text=self.defense_tool_popup_badge(tool),
                detail_text=self.defense_tool_popup_detail_text(tool),
                stats_text=self.defense_tool_popup_stats_text(tool),
                image_source=self.defense_tool_image_source(tool, eager=True),
            )
            row.bind(on_release=lambda _instance, value=display_name: self.select_defense_tool_popup_tool(value))
            self._defense_tool_add_list.add_widget(row)

    def edit_wall_unit_on_active_flank(self, unit_name: str):
        rows = self.parse_unit_lines(self.root.ids.unit_lines.text if self.root else "")
        current_row = next((row for row in rows if str(row.get("name") or "") == str(unit_name or "")), None)
        if not current_row:
            return
        count = self.get_unit_flank_count(current_row, self.wall_active_flank)
        popup = self.ensure_wall_add_popup()
        self._wall_edit_original_unit_name = str(unit_name or "")
        self._wall_selected_unit_name = str(unit_name or "")
        if getattr(self, "_wall_add_count", None) is not None:
            self._wall_add_count.text = str(count)
        if getattr(self, "_wall_add_slider", None) is not None:
            self._wall_add_slider.value = count
        if getattr(self, "_wall_add_apply_button", None) is not None:
            self._wall_add_apply_button.text = "Сохранить"
        popup.title = f"Изменить солдат · {self.flank_label(self.wall_active_flank)}"
        self.wall_add_panel_open = True
        self.refresh_wall_popup_ui()
        popup.open()

    def remove_wall_unit_from_active_flank(self, unit_name: str):
        if not self.root:
            return
        rows = self.parse_unit_lines(self.root.ids.unit_lines.text)
        updated_rows: list[dict[str, Any]] = []
        for row in rows:
            if str(row.get("name") or "") != str(unit_name or ""):
                updated_rows.append(row)
                continue
            placed = dict(row.get("placed") or {})
            placed[self.wall_active_flank] = "0"
            row["placed"] = placed
            placed_total = sum(self.get_unit_flank_count(row, flank) for flank in ("left", "center", "right"))
            if placed_total > 0:
                row["available"] = str(max(self.safe_int(row.get("available"), 0), placed_total))
                updated_rows.append(row)
        self.root.ids.unit_lines.text = self.serialize_unit_lines(updated_rows)
        if self.active_account_name:
            self.store_current_castle(silent=True)
        self.refresh_wall_scene()

    def unit_attack_strength(self, unit: dict[str, Any]) -> int:
        return self.safe_int(unit.get("attack_strength"), self.safe_int(unit.get("attack"), 0))

    def unit_melee_strength(self, unit: dict[str, Any]) -> int:
        return self.safe_int(unit.get("melee_strength"), self.safe_int(unit.get("melee_attack"), 0))

    def unit_ranged_strength(self, unit: dict[str, Any]) -> int:
        return self.safe_int(unit.get("ranged_strength"), self.safe_int(unit.get("ranged_attack"), 0))

    def infer_unit_role(self, unit: dict[str, Any]) -> str:
        role = str(unit.get("role") or "").strip().lower()
        if role in {"melee", "ranged"}:
            return role
        melee_strength = self.unit_melee_strength(unit)
        ranged_strength = self.unit_ranged_strength(unit)
        if melee_strength or ranged_strength:
            return "ranged" if ranged_strength > melee_strength else "melee"
        return "ranged" if self.safe_int(unit.get("ranged_def"), 0) > self.safe_int(unit.get("melee_def"), 0) else "melee"

    def is_special_wall_unit(self, unit: dict[str, Any]) -> bool:
        category = str(unit.get("category") or "").lower()
        name = str(unit.get("display_name") or unit.get("name") or "").lower()
        raw_name = str(unit.get("raw_name") or "").lower()
        joined = " ".join([category, name, raw_name])
        attack = self.unit_attack_strength(unit)
        return any(token in joined for token in ("quickattack", "dummy", "test", "placeholder")) or attack >= 100000

    def is_wall_defense_unit(self, unit: dict[str, Any]) -> bool:
        category = str(unit.get("category") or "").lower()
        name = str(unit.get("display_name") or unit.get("name") or "").lower()
        raw_name = str(unit.get("raw_name") or "").lower()
        joined = " ".join([category, name, raw_name])
        defense_score = self.safe_int(unit.get("melee_def"), 0) + self.safe_int(unit.get("ranged_def"), 0)
        attack = self.unit_attack_strength(unit)
        return any(token in joined for token in ("core defense", "defense", "defence", "sentinel", "guardian", "watchman")) or defense_score >= max(attack, 1) * 1.15

    def format_wall_unit_card(self, unit: dict[str, Any]) -> str:
        display_name = str(unit.get("display_name") or unit.get("name") or "Юнит")
        category = str(unit.get("category") or "без категории")
        return "\n".join(
            [
                display_name,
                category,
                "",
                f"Сила атаки: {self.unit_attack_strength(unit)}",
                f"Сила в ближнем: {self.unit_melee_strength(unit)}",
                f"Сила в дальнем: {self.unit_ranged_strength(unit)}",
                f"Защита ближнего боя: {self.safe_int(unit.get('melee_def'), 0)}",
                f"Защита дальнего боя: {self.safe_int(unit.get('ranged_def'), 0)}",
            ]
        )

    def format_wall_unit_button_text(self, unit: dict[str, Any]) -> str:
        display_name = str(unit.get("display_name") or unit.get("name") or "Юнит")
        return (
            f"{display_name}  |  АТК {self.unit_attack_strength(unit)}  |  "
            f"БЛ {self.unit_melee_strength(unit)}  |  ДАЛ {self.unit_ranged_strength(unit)}"
        )

    def wall_popup_unit_badge(self, unit: dict[str, Any]) -> str:
        role_text = "Ближний бой" if self.infer_unit_role(unit) == "melee" else "Стрелок"
        kind_text = "Защита" if self.is_wall_defense_unit(unit) else "Атака / гибрид"
        return f"{role_text} · {kind_text}"

    def wall_popup_unit_detail_text(self, unit: dict[str, Any]) -> str:
        return (
            f"Защита в ближнем: {self.safe_int(unit.get('melee_def'), 0)} · "
            f"Защита в дальнем: {self.safe_int(unit.get('ranged_def'), 0)}"
        )

    def wall_popup_unit_stats_text(self, unit: dict[str, Any]) -> str:
        if self.infer_unit_role(unit) == "ranged":
            return (
                f"Сила атаки: {self.unit_attack_strength(unit)}\n"
                f"Сила в дальнем: {self.unit_ranged_strength(unit)}"
            )
        return (
            f"Сила атаки: {self.unit_attack_strength(unit)}\n"
            f"Сила в ближнем: {self.unit_melee_strength(unit)}"
        )

    def wall_popup_unit_image_source(self, unit: dict[str, Any], eager: bool = False) -> str:
        url = str(unit.get("image_url") or "").strip()
        if not url:
            return ""
        target = self.cached_image_path(url)
        if target and target.exists():
            return str(target)
        if eager:
            return self.resolve_image_source(url)
        return ""

    def prefetch_wall_popup_images(self, units: list[dict[str, Any]], limit: int = 36):
        for unit in units[:limit]:
            url = str(unit.get("image_url") or "").strip()
            if not url:
                continue
            self.resolve_image_source(url)

    def wall_unit_sort_key(self, unit: dict[str, Any]) -> tuple[Any, ...]:
        melee_def = self.safe_int(unit.get("melee_def"), 0)
        ranged_def = self.safe_int(unit.get("ranged_def"), 0)
        attack = self.unit_attack_strength(unit)
        defense_score = melee_def + ranged_def
        is_special = self.is_special_wall_unit(unit)
        is_defense = self.is_wall_defense_unit(unit)
        role_priority = 0 if self.infer_unit_role(unit) == "melee" else 1
        if is_special:
            group_priority = 3
        elif is_defense:
            group_priority = 0
        elif defense_score > 0:
            group_priority = 1
        else:
            group_priority = 2
        power = max(melee_def, ranged_def) if group_priority == 0 else max(defense_score, attack)
        return (group_priority, role_priority, -power, -defense_score, -attack, str(unit.get("display_name") or unit.get("name") or ""))

    def load_unit_catalog(self):
        self.unit_catalog = sorted(
            [unit for unit in get_unit_catalog() if unit.get("melee_def") is not None or unit.get("ranged_def") is not None],
            key=self.wall_unit_sort_key,
        )
        self.unit_values = [str(unit.get("display_name") or unit["name"]) for unit in self.unit_catalog]
        self.unit_index = {str(unit["name"]): unit for unit in self.unit_catalog}
        self.unit_display_index = {str(unit.get("display_name") or unit["name"]): unit for unit in self.unit_catalog}
        self.attack_unit_catalog = [unit for unit in get_unit_catalog() if unit.get("attack") is not None]
        self.attack_unit_values = [str(unit.get("display_name") or unit["name"]) for unit in self.attack_unit_catalog]
        self.attack_unit_index = {str(unit["name"]): unit for unit in self.attack_unit_catalog}
        self.attack_unit_display_index = {str(unit.get("display_name") or unit["name"]): unit for unit in self.attack_unit_catalog}
        if self.unit_values:
            default_wall_unit = self.unit_values[0]
            self._wall_selected_unit_name = default_wall_unit
            if getattr(self, "_wall_add_popup", None) is not None:
                self.refresh_wall_popup_ui()
            self.update_unit_preview(default_wall_unit)
        if self.attack_unit_values and self.root and "attack_unit_picker" in self.root.ids:
            self.root.ids.attack_unit_picker.text = self.attack_unit_values[0]
            self.update_attack_unit_preview(self.attack_unit_values[0])

    def ensure_account(self, account_name: str) -> dict[str, Any]:
        accounts = self.profile_store.setdefault("accounts", {})
        account = accounts.get(account_name)
        if not account:
            account = default_account(account_name)
            accounts[account_name] = account
        account.setdefault("name", account_name)
        account.setdefault("avatar_key", "crown")
        for castle_name in ACCOUNT_CASTLE_NAMES:
            castle = account.setdefault("castles", {}).setdefault(castle_name, default_castle_record(castle_name))
            castle.setdefault("name", castle_name)
            castle.setdefault("display_name", castle_name)
            castle.setdefault("building_levels", {})
        for castle_name, castle in account.setdefault("castles", {}).items():
            if isinstance(castle, dict):
                castle.setdefault("name", castle_name)
                castle.setdefault("display_name", castle_name)
                castle.setdefault("building_levels", {})
        return account

    def build_castle_values(self, account: dict[str, Any]) -> list[str]:
        castles = account.setdefault("castles", {})
        ordered = [castle_name for castle_name in ACCOUNT_CASTLE_NAMES if castle_name in castles]
        custom = sorted(castle_name for castle_name in castles if castle_name not in ACCOUNT_CASTLE_NAMES)
        return ordered + custom

    def set_main_tab(self, tab_name: str):
        normalized = str(tab_name or "profile").strip().lower()
        if normalized not in {"profile", "battle", "upgrade"}:
            normalized = "profile"
        self.main_tab = normalized
        if not self.root or "main_tabs" not in self.root.ids:
            return
        tabs = self.root.ids.main_tabs
        target_id = {
            "profile": "tab_profile",
            "battle": "tab_battle",
            "upgrade": "tab_upgrade",
        }.get(normalized)
        target_tab = self.root.ids.get(target_id) if target_id else None
        if target_tab is not None:
            tabs.switch_to(target_tab)
        self.hide_main_tab_strip()

    def format_compact_number(self, value: float | int) -> str:
        rounded = int(round(self.safe_float(value, 0.0)))
        return f"{rounded:,}".replace(",", " ")

    def castle_power_breakdown(self, castle: dict[str, Any] | None = None) -> tuple[int, float, float]:
        record = castle or {}
        units = self.parse_unit_lines(str(record.get("units_text") or ""))
        governor = record.get("governor") or default_governor()
        total_units = sum(self.safe_int(unit.get("available"), 0) for unit in units)
        base_melee = sum(self.safe_int(unit.get("available"), 0) * self.safe_float(unit.get("melee_def"), 0.0) for unit in units)
        base_ranged = sum(self.safe_int(unit.get("available"), 0) * self.safe_float(unit.get("ranged_def"), 0.0) for unit in units)
        overall_bonus = self.safe_float(governor.get("overall_bonus"), 0.0)
        melee_bonus = self.safe_float(governor.get("melee_bonus"), 0.0)
        ranged_bonus = self.safe_float(governor.get("ranged_bonus"), 0.0)
        base_power = base_melee + base_ranged
        bonus_power = (base_melee * ((melee_bonus + overall_bonus) / 100.0)) + (base_ranged * ((ranged_bonus + overall_bonus) / 100.0))
        return total_units, base_power, max(0.0, bonus_power)

    def account_avatar_source(self, account_name: str, avatar_key: str) -> str:
        key = str(avatar_key or "crown").strip().lower()
        palette = {
            "crown": "7C5222",
            "knight": "2F4E7B",
            "falcon": "355C46",
            "wolf": "5E4A69",
        }
        label = ACCOUNT_AVATAR_LABELS.get(key, "Аккаунт")
        initials = (str(account_name or "A").strip()[:1] or "A").upper()
        return self.resolve_image_source(placeholder_image_url(f"{label} {initials}", palette.get(key, "2F4E7B"), size="128x128"))

    def castle_type_label(self, castle_key: str) -> str:
        value = str(castle_key or "").strip().lower()
        if "аванпост" in value:
            return "Аванпост"
        if value == "основной замок":
            return "Основной замок"
        return "Мир / событие"

    def castle_display_name(self, castle_key: str, castle: dict[str, Any] | None = None) -> str:
        record = castle or (self.current_account() or {}).get("castles", {}).get(castle_key, {})
        return str(record.get("display_name") or castle_key or record.get("name") or "Профиль")

    def castle_card_image_source(self, castle_key: str, castle: dict[str, Any] | None = None) -> str:
        record = castle or (self.current_account() or {}).get("castles", {}).get(castle_key, {})
        kind = self.castle_type_label(castle_key)
        if str(castle_key or "").strip().lower() == "основной замок" and MAIN_CASTLE_IMAGE_FILE.exists():
            return str(MAIN_CASTLE_IMAGE_FILE)
        colors = {
            "Основной замок": "6A3B23",
            "Аванпост": "2F5C7A",
            "Мир / событие": "5C4A7A",
        }
        short_text = self.castle_display_name(castle_key, record)[:18]
        return self.resolve_image_source(placeholder_image_url(short_text, colors.get(kind, "2F5C7A")))

    def castle_card_summary_text(self, castle_key: str, castle: dict[str, Any] | None = None) -> str:
        record = castle or (self.current_account() or {}).get("castles", {}).get(castle_key, {})
        total_units, base_power, bonus_power = self.castle_power_breakdown(record)
        return (
            f"Всего солдат в замке: {self.format_compact_number(total_units)}\n"
            f"Боевая мощь солдат в замке: {self.format_compact_number(base_power)} + {self.format_compact_number(bonus_power)}"
        )

    def refresh_active_account_state(self):
        account = self.current_account()
        if not account:
            self.active_account_avatar_label = "Локальный аккаунт"
            self.active_account_avatar_source = ""
            self.active_castle_card_title = "Профиль не выбран"
            self.active_castle_card_subtitle = "Всего солдат в замке: 0"
            self.active_castle_card_summary = "Открой аккаунт, затем выбери карточку профиля ниже."
            self.active_castle_card_image_source = ""
            return
        avatar_key = str(account.get("avatar_key") or "crown")
        self.active_account_avatar_label = f"{account.get('name') or self.active_account_name} · {ACCOUNT_AVATAR_LABELS.get(avatar_key, 'Аккаунт')}"
        self.active_account_avatar_source = self.account_avatar_source(str(account.get("name") or self.active_account_name), avatar_key)
        castle = self.current_castle_record()
        if not castle:
            self.active_castle_card_title = "Профиль не выбран"
            self.active_castle_card_subtitle = "Всего солдат в замке: 0"
            self.active_castle_card_summary = "У аккаунта нет активного профиля."
            self.active_castle_card_image_source = ""
            return
        total_units, base_power, bonus_power = self.castle_power_breakdown(castle)
        self.active_castle_card_title = self.castle_display_name(self.active_castle_name, castle)
        self.active_castle_card_subtitle = f"Всего солдат в замке: {self.format_compact_number(total_units)}"
        self.active_castle_card_summary = f"Боевая мощь солдат в замке: {self.format_compact_number(base_power)} + {self.format_compact_number(bonus_power)}"
        self.active_castle_card_image_source = self.castle_card_image_source(self.active_castle_name, castle)

    def open_profile_menu(self):
        popup = self.ensure_profile_menu_popup()
        self.refresh_active_account_state()
        if getattr(self, "_profile_menu_avatar", None) is not None:
            self._profile_menu_avatar.source = self.active_account_avatar_source
        if getattr(self, "_profile_menu_summary", None) is not None:
            summary_lines = [self.active_account_avatar_label]
            if self.active_account_name:
                summary_lines.append(f"Аккаунт: {self.active_account_name}")
            summary_lines.append(f"Профиль: {self.active_castle_card_title}")
            summary_lines.append(self.active_castle_card_subtitle)
            self._profile_menu_summary.text = "\n".join(summary_lines)
        popup.open()

    def close_profile_menu(self):
        popup = getattr(self, "_profile_menu_popup", None)
        if popup:
            popup.dismiss()

    def ensure_profile_menu_popup(self) -> Popup:
        popup = getattr(self, "_profile_menu_popup", None)
        if popup is not None:
            return popup

        content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12))
        header = BoxLayout(size_hint_y=None, height=dp(92), spacing=dp(10))
        avatar = AsyncImage(size_hint_x=None, width=dp(72), fit_mode="contain")
        summary = Factory.OutputArea()
        header.add_widget(avatar)
        header.add_widget(summary)

        edit_profile = Factory.AppButton(text="Редактировать профиль")
        edit_profile.bind(on_release=lambda *_: self.open_profile_editor_from_menu())
        switch_account = Factory.SecondaryButton(text="Изменить аккаунт")
        switch_account.bind(on_release=lambda *_: self.open_account_manager_from_menu())
        change_avatar = Factory.SecondaryButton(text="Сменить аватар")
        change_avatar.bind(on_release=lambda *_: self.open_avatar_picker_from_menu())
        about_button = Factory.SecondaryButton(text="О программе")
        about_button.bind(on_release=lambda *_: self.open_about_from_menu())
        close_button = Factory.DangerButton(text="Закрыть")
        close_button.bind(on_release=lambda *_: self.close_profile_menu())

        content.add_widget(header)
        content.add_widget(edit_profile)
        content.add_widget(switch_account)
        content.add_widget(change_avatar)
        content.add_widget(about_button)
        content.add_widget(close_button)

        popup = Popup(
            title="Меню профиля",
            content=content,
            size_hint=(0.82, None),
            height=dp(430),
            auto_dismiss=True,
            separator_height=0,
        )
        self._profile_menu_popup = popup
        self._profile_menu_avatar = avatar
        self._profile_menu_summary = summary
        return popup

    def open_profile_editor_from_menu(self):
        self.close_profile_menu()
        self.set_main_tab("profile")

    def open_account_manager_from_menu(self):
        self.close_profile_menu()
        self.open_account_manager_popup()

    def open_avatar_picker_from_menu(self):
        self.close_profile_menu()
        self.open_avatar_picker_popup()

    def open_about_from_menu(self):
        self.close_profile_menu()
        self.open_about_popup()

    def open_account_manager_popup(self):
        popup = self.ensure_account_manager_popup()
        if getattr(self, "_account_manage_name_input", None) is not None:
            self._account_manage_name_input.text = self.active_account_name
        popup.open()

    def ensure_account_manager_popup(self) -> Popup:
        popup = getattr(self, "_account_manage_popup", None)
        if popup is not None:
            return popup

        content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12))
        intro = Factory.BodyText(text="Открой другой локальный аккаунт или создай новый. Аватар привяжется к активному аккаунту.")
        name_input = Factory.AppInput()
        name_input.hint_text = "Имя аккаунта"
        buttons = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        cancel_button = Factory.SecondaryButton(text="Отмена")
        cancel_button.bind(on_release=lambda *_: self.close_account_manager_popup())
        apply_button = Factory.AppButton(text="Открыть аккаунт")
        apply_button.bind(on_release=lambda *_: self.apply_account_switch())
        buttons.add_widget(cancel_button)
        buttons.add_widget(apply_button)
        content.add_widget(intro)
        content.add_widget(name_input)
        content.add_widget(buttons)

        popup = Popup(
            title="Аккаунт",
            content=content,
            size_hint=(0.8, None),
            height=dp(220),
            auto_dismiss=True,
            separator_height=0,
        )
        self._account_manage_popup = popup
        self._account_manage_name_input = name_input
        return popup

    def close_account_manager_popup(self):
        popup = getattr(self, "_account_manage_popup", None)
        if popup:
            popup.dismiss()

    def apply_account_switch(self):
        name_input = getattr(self, "_account_manage_name_input", None)
        account_name = str(name_input.text or "").strip() if name_input is not None else ""
        if not account_name:
            self.profile_output = "Введи имя аккаунта, чтобы открыть локальный профиль."
            return
        if self.root and "account_name" in self.root.ids:
            self.root.ids.account_name.text = account_name
        self.create_or_open_account()
        self.close_account_manager_popup()

    def open_about_popup(self):
        popup = getattr(self, "_about_popup", None)
        if popup is None:
            content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12))
            text = Factory.OutputArea()
            text.text = "Empire 4 Kingdoms Calculator\n\nЛокальный калькулятор профилей замка, обороны, атак по волнам и улучшений.\n\nТеперь профили, аккаунт и аватар вынесены в отдельные меню и карточки."
            close_button = Factory.AppButton(text="Закрыть")
            close_button.bind(on_release=lambda *_: popup.dismiss())
            content.add_widget(text)
            content.add_widget(close_button)
            popup = Popup(
                title="О программе",
                content=content,
                size_hint=(0.84, None),
                height=dp(300),
                auto_dismiss=True,
                separator_height=0,
            )
            self._about_popup = popup
        popup.open()

    def open_avatar_picker_popup(self):
        popup = self.ensure_avatar_picker_popup()
        self.refresh_avatar_picker_popup()
        popup.open()

    def ensure_avatar_picker_popup(self) -> Popup:
        popup = getattr(self, "_avatar_picker_popup", None)
        if popup is not None:
            return popup

        content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12))
        intro = Factory.BodyText(text="Выбери аватар для текущего аккаунта. Он будет показываться в меню профиля.")
        scroll = ScrollView(do_scroll_x=False)
        grid = GridLayout(cols=1, size_hint_y=None, spacing=dp(8), padding=[0, 0, 0, dp(6)])
        grid.bind(minimum_height=grid.setter("height"))
        scroll.add_widget(grid)
        close_button = Factory.SecondaryButton(text="Закрыть")
        close_button.bind(on_release=lambda *_: self.close_avatar_picker_popup())
        content.add_widget(intro)
        content.add_widget(scroll)
        content.add_widget(close_button)

        popup = Popup(
            title="Сменить аватар",
            content=content,
            size_hint=(0.86, 0.82),
            auto_dismiss=True,
            separator_height=0,
        )
        self._avatar_picker_popup = popup
        self._avatar_picker_list = grid
        return popup

    def refresh_avatar_picker_popup(self):
        container = getattr(self, "_avatar_picker_list", None)
        if container is None:
            return
        container.clear_widgets()
        account_name = self.active_account_name or "Аккаунт"
        active_key = str((self.current_account() or {}).get("avatar_key") or "crown")
        for key, label in ACCOUNT_AVATAR_LABELS.items():
            row = WallUnitRow(
                selected=key == active_key,
                title_text=label,
                subtitle_text="Аватар аккаунта",
                detail_text=f"Будет использоваться для аккаунта {account_name}",
                stats_text="Активен" if key == active_key else "Выбрать",
                image_source=self.account_avatar_source(account_name, key),
            )
            row.bind(on_release=lambda _instance, value=key: self.set_account_avatar(value))
            container.add_widget(row)

    def close_avatar_picker_popup(self):
        popup = getattr(self, "_avatar_picker_popup", None)
        if popup:
            popup.dismiss()

    def set_account_avatar(self, avatar_key: str):
        account = self.current_account()
        if not account:
            self.profile_output = "Сначала открой аккаунт, затем можно менять аватар."
            return
        account["avatar_key"] = str(avatar_key or "crown")
        self.save_profile_store()
        self.refresh_active_account_state()
        self.refresh_profile_output(f"Аватар аккаунта обновлён: {ACCOUNT_AVATAR_LABELS.get(account['avatar_key'], 'Аккаунт')}")
        self.refresh_avatar_picker_popup()

    def open_castle_selector_popup(self):
        popup = self.ensure_castle_selector_popup()
        if getattr(self, "_castle_selector_add_input", None) is not None:
            self._castle_selector_add_input.text = ""
        self.refresh_castle_selector_popup()
        popup.open()

    def close_castle_selector_popup(self):
        popup = getattr(self, "_castle_selector_popup", None)
        if popup:
            popup.dismiss()

    def ensure_castle_selector_popup(self) -> Popup:
        popup = getattr(self, "_castle_selector_popup", None)
        if popup is not None:
            return popup

        content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12))
        intro = Factory.BodyText(text="Выбери замок, аванпост или мир текущего аккаунта. Здесь же можно быстро добавить новый профиль.")
        scroll = ScrollView(do_scroll_x=False)
        grid = GridLayout(cols=1, size_hint_y=None, spacing=dp(8), padding=[0, 0, 0, dp(6)])
        grid.bind(minimum_height=grid.setter("height"))
        scroll.add_widget(grid)
        add_box = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        add_input = Factory.AppInput()
        add_input.hint_text = "Новый замок / аванпост / мир"
        add_button = Factory.AppButton(text="Добавить")
        add_button.bind(on_release=lambda *_: self.add_castle_profile_from_popup())
        add_box.add_widget(add_input)
        add_box.add_widget(add_button)
        close_button = Factory.SecondaryButton(text="Закрыть")
        close_button.bind(on_release=lambda *_: self.close_castle_selector_popup())

        content.add_widget(intro)
        content.add_widget(scroll)
        content.add_widget(add_box)
        content.add_widget(close_button)

        popup = Popup(
            title="Профили замков",
            content=content,
            size_hint=(0.92, 0.88),
            auto_dismiss=True,
            separator_height=0,
        )
        self._castle_selector_popup = popup
        self._castle_selector_list = grid
        self._castle_selector_add_input = add_input
        return popup

    def refresh_castle_selector_popup(self):
        container = getattr(self, "_castle_selector_list", None)
        if container is None:
            return
        container.clear_widgets()
        account = self.current_account()
        if not account:
            empty = Factory.BodyText(size_hint_y=None, height=dp(46))
            empty.text = "Сначала открой аккаунт, чтобы управлять профилями замков."
            container.add_widget(empty)
            return
        for castle_key in self.castle_values:
            castle = account.setdefault("castles", {}).setdefault(castle_key, default_castle_record(castle_key))
            title = self.castle_display_name(castle_key, castle)
            detail = self.castle_card_summary_text(castle_key, castle)
            subtitle = f"{self.castle_type_label(castle_key)} · {castle_key}"
            row = WallUnitRow(
                selected=castle_key == self.active_castle_name,
                title_text=title,
                subtitle_text=subtitle,
                detail_text=detail,
                stats_text="Активный" if castle_key == self.active_castle_name else "Открыть",
                image_source=self.castle_card_image_source(castle_key, castle),
            )
            row.bind(on_release=lambda _instance, value=castle_key: self.select_castle_from_popup(value))
            container.add_widget(row)

    def add_castle_profile_from_popup(self):
        add_input = getattr(self, "_castle_selector_add_input", None)
        value = str(add_input.text or "").strip() if add_input is not None else ""
        if self.root and "new_castle_name" in self.root.ids:
            self.root.ids.new_castle_name.text = value
        self.add_castle_profile()
        self.refresh_castle_selector_popup()

    def select_castle_from_popup(self, castle_name: str):
        if self.root and "castle_spinner" in self.root.ids:
            self.root.ids.castle_spinner.text = str(castle_name or "")
        else:
            self.select_castle(castle_name)
        self.close_castle_selector_popup()

    def on_current_profile_name_changed(self, value: str):
        account = self.current_account()
        castle = self.current_castle_record()
        if not account or not castle or not self.active_castle_name:
            return
        display_name = str(value or "").strip() or self.active_castle_name
        castle["display_name"] = display_name
        account.setdefault("castles", {})[self.active_castle_name] = castle
        self.save_profile_store()
        self.refresh_active_account_state()
        self.refresh_castle_selector_popup()

    def safe_int(self, value: Any, default: int = 0) -> int:
        try:
            cleaned = str(value).strip().replace("\xa0", " ").replace(" ", "").replace(",", ".")
            return int(float(cleaned))
        except (TypeError, ValueError):
            return default

    def get_attack_wave_count(self) -> int:
        return max(1, min(12, self.safe_int(self.attack_wave_count, 1)))

    def update_wave_values(self, value: str):
        wave_count = max(1, min(12, self.safe_int(value, 1)))
        self.attack_wave_count = str(wave_count)
        self.wave_values = [str(index) for index in range(1, wave_count + 1)]
        if self.root and "attack_unit_wave" in self.root.ids:
            current_wave = str(self.root.ids.attack_unit_wave.text or "1").strip() or "1"
            if current_wave not in self.wave_values:
                self.root.ids.attack_unit_wave.text = "1"
        if self.root and "attack_wave_count" in self.root.ids:
            field = self.root.ids.attack_wave_count
            if field.text != self.attack_wave_count:
                field.text = self.attack_wave_count

    def build_profile_output(self, notice: str | None = None) -> str:
        account = self.current_account()
        if not account:
            return notice or "Создай аккаунт и выбери профиль замка."
        castle = self.current_castle_record() or default_castle_record(self.active_castle_name or "Замок")
        units = self.parse_unit_lines(str(castle.get("units_text") or ""))
        defense_tools = self.parse_defensive_tool_lines(str(castle.get("defensive_tools_text") or ""))
        total_units = sum(self.safe_int(unit.get("available"), 0) for unit in units)
        governor = castle.get("governor") or default_governor()
        governor_name = str(governor.get("general_name") or "").strip()
        intro = f"{notice}\n" if notice else ""
        return (
            f"{intro}Аккаунт: {self.active_account_name}\n"
            f"Профилей замков: {len(account.get('castles', {}))}\n"
            f"Активный профиль: {self.castle_display_name(self.active_castle_name or str(castle.get('name') or ''), castle)}\n"
            f"Записей гарнизона: {len(units)}\n"
            f"Оборонительных орудий: {len(defense_tools)}\n"
            f"Всего солдат в профиле: {total_units}\n"
            f"Наместник: {governor_name or 'не выбран'}\n"
            f"Бонус наместника к общей защите: {governor.get('overall_bonus') or 0}%\n"
            f"Лимит стены: +{governor.get('wall_limit_bonus') or 0}"
        )

    def refresh_profile_output(self, notice: str | None = None):
        self.profile_output = self.build_profile_output(notice)
        self.refresh_active_account_state()

    def flank_label(self, flank_key: str) -> str:
        labels = {"left": "Левый фланг", "center": "Центральный фланг", "right": "Правый фланг"}
        return labels.get(str(flank_key or "").strip().lower(), "Центральный фланг")

    def get_unit_flank_count(self, unit: dict[str, Any], flank_key: str) -> int:
        placed = unit.get("placed") or {}
        if isinstance(placed, dict):
            return self.safe_int(placed.get(flank_key), 0)
        return self.safe_int(unit.get(flank_key), 0)

    def serialize_unit_lines(self, units: list[dict[str, Any]]) -> str:
        rows: list[str] = []
        for unit in units:
            rows.append(
                ",".join(
                    [
                        str(unit.get("name") or ""),
                        str(unit.get("available") or "0"),
                        str(unit.get("melee_def") or "0"),
                        str(unit.get("ranged_def") or "0"),
                        str(self.get_unit_flank_count(unit, "left")),
                        str(self.get_unit_flank_count(unit, "center")),
                        str(self.get_unit_flank_count(unit, "right")),
                    ]
                )
            )
        return "\n".join(rows)

    def build_active_wall_units_output(self, units: list[dict[str, Any]], flank_key: str) -> str:
        ranked = sorted(
            (
                (str(unit.get("name") or "Юнит"), self.get_unit_flank_count(unit, flank_key))
                for unit in units
                if self.get_unit_flank_count(unit, flank_key) > 0
            ),
            key=lambda item: item[1],
            reverse=True,
        )
        if not ranked:
            return f"{self.flank_label(flank_key)}\n\nПока пусто. Нажми '+' и добавь солдат на этот участок стены."
        lines = [self.flank_label(flank_key), ""]
        for index, (name, count) in enumerate(ranked[:8], start=1):
            lines.append(f"{index}. {name} — {count}")
        if len(ranked) > 8:
            lines.append("")
            lines.append(f"И ещё {len(ranked) - 8} типов юнитов")
        return "\n".join(lines)

    def refresh_wall_active_units_list(self, units: list[dict[str, Any]], flank_key: str):
        if not self.root or "wall_active_units_list" not in self.root.ids:
            return
        container = self.root.ids.wall_active_units_list
        container.clear_widgets()
        ranked_units = [unit for unit in units if self.get_unit_flank_count(unit, flank_key) > 0]
        ranked_units.sort(key=lambda item: self.get_unit_flank_count(item, flank_key), reverse=True)
        if not ranked_units:
            empty = Factory.BodyText(size_hint_y=None, height=dp(46))
            empty.text = "На этом фланге пока пусто. Нажми '+ Солдаты', чтобы добавить защитников."
            container.add_widget(empty)
            return
        for unit in ranked_units:
            name = str(unit.get("name") or "Юнит")
            flank_count = self.get_unit_flank_count(unit, flank_key)
            total_count = sum(self.get_unit_flank_count(unit, key) for key in ("left", "center", "right"))
            row = BoxLayout(size_hint_y=None, height=dp(58), spacing=dp(8))
            info = Label(
                text=f"{name}\nНа фланге: {flank_count} · Всего на стене: {total_count}",
                text_size=(0, None),
                halign="left",
                valign="middle",
                color=(0.96, 0.98, 1, 1),
            )
            info.bind(width=lambda instance, value: setattr(instance, "text_size", (value, None)))
            edit_button = Factory.SecondaryButton(text="Изм.", size_hint_x=None, width=dp(76))
            edit_button.bind(on_release=lambda _instance, value=name: self.edit_wall_unit_on_active_flank(value))
            delete_button = Factory.DangerButton(text="Удал.", size_hint_x=None, width=dp(82))
            delete_button.bind(on_release=lambda _instance, value=name: self.remove_wall_unit_from_active_flank(value))
            row.add_widget(info)
            row.add_widget(edit_button)
            row.add_widget(delete_button)
            container.add_widget(row)

    def serialize_defensive_tool_lines(self, rows: list[dict[str, Any]]) -> str:
        serialized: list[str] = []
        for row in rows:
            zone = str(row.get("flank") or row.get("zone") or "all")
            name = str(row.get("name") or "")
            count = str(row.get("count") or "0")
            if not name or self.safe_int(count, 0) <= 0:
                continue
            serialized.append(",".join([zone or "all", name, count]))
        return "\n".join(serialized)

    def defense_tool_preview_text(self, tool: dict[str, Any]) -> str:
        lines = [str(tool.get("display_name") or tool.get("name") or "Орудие")]
        category = str(tool.get("category") or "без категории")
        lines.append(category)
        lines.append("")
        effects = []
        if self.safe_int(tool.get("def_melee_bonus"), 0):
            effects.append(f"Ближняя защита: +{self.safe_int(tool.get('def_melee_bonus'), 0)}%")
        if self.safe_int(tool.get("wall_capacity_bonus"), 0):
            effects.append(f"Лимит стены: +{self.safe_int(tool.get('wall_capacity_bonus'), 0)}")
        if self.safe_int(tool.get("defense_power_bonus"), 0):
            effects.append(f"Общая сила защиты: +{self.safe_int(tool.get('defense_power_bonus'), 0)}%")
        if self.safe_int(tool.get("yard_defense_power_bonus"), 0):
            effects.append(f"Сила двора: +{self.safe_int(tool.get('yard_defense_power_bonus'), 0)}%")
        if self.safe_int(tool.get("kill_attacking_any_yard"), 0):
            effects.append(f"Убийства атакующих во дворе: {self.safe_int(tool.get('kill_attacking_any_yard'), 0)}")
        if self.safe_int(tool.get("kill_attacking_melee_yard"), 0):
            effects.append(f"Убийства мили во дворе: {self.safe_int(tool.get('kill_attacking_melee_yard'), 0)}")
        if self.safe_int(tool.get("kill_attacking_ranged_yard"), 0):
            effects.append(f"Убийства стрелков во дворе: {self.safe_int(tool.get('kill_attacking_ranged_yard'), 0)}")
        if not effects:
            effects.append("Нет поддерживаемых эффектов в текущей модели.")
        lines.extend(effects)
        return "\n".join(lines)

    def refresh_defense_tools_list(self):
        if not self.root or "defense_tools_list" not in self.root.ids:
            return
        container = self.root.ids.defense_tools_list
        container.clear_widgets()
        rows = self.parse_defensive_tool_lines(self.root.ids.defensive_tools_lines.text)
        if not rows:
            empty = Factory.BodyText(size_hint_y=None, height=dp(46))
            empty.text = "Оборонительные орудия ещё не добавлены. Используй форму выше, чтобы собрать защиту по участкам."
            container.add_widget(empty)
            return
        for index, row_data in enumerate(rows):
            zone = str(row_data.get("flank") or "all")
            label = DEFENSE_TOOL_ZONE_LABELS.get(zone, zone)
            name = str(row_data.get("name") or "Орудие")
            count = self.safe_int(row_data.get("count"), 0)
            row = BoxLayout(size_hint_y=None, height=dp(58), spacing=dp(8))
            info = Label(
                text=f"{name}\n{label} · Кол-во: {count}",
                text_size=(0, None),
                halign="left",
                valign="middle",
                color=(0.96, 0.98, 1, 1),
            )
            info.bind(width=lambda instance, value: setattr(instance, "text_size", (value, None)))
            edit_button = Factory.SecondaryButton(text="Изм.", size_hint_x=None, width=dp(76))
            edit_button.bind(on_release=lambda _instance, value=index: self.edit_defense_tool_entry(value))
            delete_button = Factory.DangerButton(text="Удал.", size_hint_x=None, width=dp(82))
            delete_button.bind(on_release=lambda _instance, value=index: self.remove_defense_tool_entry(value))
            row.add_widget(info)
            row.add_widget(edit_button)
            row.add_widget(delete_button)
            container.add_widget(row)

    def set_wall_active_flank(self, flank_key: str):
        normalized = str(flank_key or "center").strip().lower()
        if normalized not in {"left", "center", "right"}:
            normalized = "center"
        self.wall_active_flank = normalized
        self.wall_active_flank_label = self.flank_label(normalized)
        self.refresh_wall_scene()

    def toggle_wall_add_panel(self):
        popup = self.ensure_wall_add_popup()
        self.wall_add_panel_open = True
        self._wall_edit_original_unit_name = None
        popup.title = f"Добавить солдат · {self.flank_label(self.wall_active_flank)}"
        if getattr(self, "_wall_add_count", None):
            self._wall_add_count.text = ""
        if getattr(self, "_wall_add_slider", None):
            self._wall_add_slider.value = 0
        if getattr(self, "_wall_add_apply_button", None) is not None:
            self._wall_add_apply_button.text = "Добавить"
        self.refresh_wall_popup_ui()
        popup.open()

    def close_wall_add_panel(self):
        self.wall_add_panel_open = False
        popup = getattr(self, "_wall_add_popup", None)
        if popup:
            popup.dismiss()

    def ensure_wall_add_popup(self) -> Popup:
        popup = getattr(self, "_wall_add_popup", None)
        if popup is not None:
            return popup

        content = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        tabs = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        melee_button = Factory.AppButton(text="Солдаты ближнего боя")
        melee_button.bind(on_release=lambda *_: self.set_wall_popup_role_filter("melee"))
        ranged_button = Factory.SecondaryButton(text="Стрелок")
        ranged_button.bind(on_release=lambda *_: self.set_wall_popup_role_filter("ranged"))
        tabs.add_widget(melee_button)
        tabs.add_widget(ranged_button)

        controls = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        search_input = Factory.AppInput()
        search_input.hint_text = "Поиск солдата"
        search_input.bind(text=self.on_wall_popup_search_changed)
        defense_toggle = Factory.SecondaryButton(text="Только защитные")
        defense_toggle.bind(on_release=lambda *_: self.toggle_wall_popup_defense_only())
        controls.add_widget(search_input)
        controls.add_widget(defense_toggle)

        preview_card = BoxLayout(size_hint_y=None, height=dp(156), spacing=dp(10))
        preview_image = AsyncImage(size_hint_x=None, width=dp(88), fit_mode="contain")
        preview = Factory.OutputArea()
        preview_card.add_widget(preview_image)
        preview_card.add_widget(preview)

        list_scroll = ScrollView(do_scroll_x=False, size_hint=(1, 1), bar_width=dp(6))
        unit_list = GridLayout(cols=1, size_hint_y=None, spacing=dp(6), padding=[0, 0, 0, dp(6)])
        unit_list.bind(minimum_height=unit_list.setter("height"))
        list_scroll.add_widget(unit_list)

        count_input = Factory.AppInput(size_hint_y=None, height=dp(44))
        count_input.hint_text = "Количество солдат"
        count_input.input_filter = "int"
        count_input.bind(text=self.on_wall_popup_count_changed)

        slider = Slider(min=0, max=200000, value=0, step=1, size_hint_y=None, height=dp(36))
        slider.bind(value=self.on_wall_popup_slider_changed)

        buttons = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        cancel_button = Factory.SecondaryButton(text="Отмена")
        cancel_button.bind(on_release=lambda *_: self.close_wall_add_panel())
        apply_button = Factory.AppButton(text="Добавить")
        apply_button.bind(on_release=lambda *_: self.add_selected_unit_to_garrison())
        buttons.add_widget(cancel_button)
        buttons.add_widget(apply_button)

        content.add_widget(tabs)
        content.add_widget(controls)
        content.add_widget(preview_card)
        content.add_widget(list_scroll)
        content.add_widget(count_input)
        content.add_widget(slider)
        content.add_widget(buttons)

        popup = Popup(
            title="Добавить солдат",
            content=content,
            size_hint=(0.96, 0.92),
            auto_dismiss=True,
            separator_height=0,
        )
        popup.bind(on_dismiss=self.on_wall_popup_dismiss)
        self._wall_add_popup = popup
        self._wall_add_melee_button = melee_button
        self._wall_add_ranged_button = ranged_button
        self._wall_add_search = search_input
        self._wall_add_defense_toggle = defense_toggle
        self._wall_add_preview = preview
        self._wall_add_preview_image = preview_image
        self._wall_add_list = unit_list
        self._wall_add_selected_button = None
        self._wall_add_count = count_input
        self._wall_add_slider = slider
        self._wall_add_apply_button = apply_button
        self._wall_add_syncing = False
        self._wall_popup_role_filter = "melee"
        self._wall_popup_defense_only = True
        self._wall_popup_visible_units = []
        self._wall_selected_unit_name = self.unit_values[0] if self.unit_values else ""
        self._wall_edit_original_unit_name = None
        return popup

    def on_wall_popup_dismiss(self, *_args):
        self.wall_add_panel_open = False
        self._wall_edit_original_unit_name = None
        if getattr(self, "_wall_add_apply_button", None) is not None:
            self._wall_add_apply_button.text = "Добавить"

    def set_wall_popup_role_filter(self, role: str):
        self._wall_popup_role_filter = "ranged" if str(role or "").strip().lower() == "ranged" else "melee"
        self.refresh_wall_popup_ui()

    def toggle_wall_popup_defense_only(self):
        self._wall_popup_defense_only = not getattr(self, "_wall_popup_defense_only", True)
        self.refresh_wall_popup_ui()

    def on_wall_popup_search_changed(self, _instance, _value: str):
        self.refresh_wall_popup_ui()

    def filtered_wall_popup_units(self) -> list[dict[str, Any]]:
        search_value = str(getattr(self, "_wall_add_search", None).text or "").strip().lower() if getattr(self, "_wall_add_search", None) is not None else ""
        role_filter = getattr(self, "_wall_popup_role_filter", "melee")
        defense_only = getattr(self, "_wall_popup_defense_only", True)
        filtered: list[dict[str, Any]] = []
        for unit in self.unit_catalog:
            if self.infer_unit_role(unit) != role_filter:
                continue
            if defense_only and not self.is_wall_defense_unit(unit):
                continue
            haystack = " ".join(
                [
                    str(unit.get("display_name") or ""),
                    str(unit.get("name") or ""),
                    str(unit.get("category") or ""),
                ]
            ).lower()
            if search_value and search_value not in haystack:
                continue
            filtered.append(unit)
        return filtered

    def select_wall_popup_unit(self, unit_name: str):
        self._wall_selected_unit_name = str(unit_name or "")
        self.update_unit_preview(self._wall_selected_unit_name)
        self.refresh_wall_popup_ui()

    def refresh_wall_popup_ui(self):
        if getattr(self, "_wall_add_popup", None) is None:
            return
        role_filter = getattr(self, "_wall_popup_role_filter", "melee")
        self._wall_add_melee_button.background_color = (0.79, 0.67, 0.42, 1) if role_filter == "melee" else (0.16, 0.23, 0.34, 1)
        self._wall_add_ranged_button.background_color = (0.79, 0.67, 0.42, 1) if role_filter == "ranged" else (0.16, 0.23, 0.34, 1)
        defense_only = getattr(self, "_wall_popup_defense_only", True)
        self._wall_add_defense_toggle.text = "Только защитные" if defense_only else "Показывать атаку и деф"
        self._wall_add_defense_toggle.background_color = (0.27, 0.43, 0.22, 1) if defense_only else (0.16, 0.23, 0.34, 1)

        visible_units = self.filtered_wall_popup_units()
        self._wall_popup_visible_units = visible_units
        self.prefetch_wall_popup_images(visible_units)
        if visible_units and self._wall_selected_unit_name not in {str(unit.get("display_name") or unit.get("name") or "") for unit in visible_units}:
            self._wall_selected_unit_name = str(visible_units[0].get("display_name") or visible_units[0].get("name") or "")

        selected_unit = self.unit_display_index.get(self._wall_selected_unit_name) or self.unit_index.get(self._wall_selected_unit_name)
        if selected_unit:
            self._wall_add_preview.text = self.format_wall_unit_card(selected_unit)
            if getattr(self, "_wall_add_preview_image", None) is not None:
                self._wall_add_preview_image.source = self.wall_popup_unit_image_source(selected_unit, eager=True)
        else:
            self._wall_add_preview.text = "Нет юнитов под текущий фильтр. Попробуй сменить вкладку или отключить фильтр защитных."
            if getattr(self, "_wall_add_preview_image", None) is not None:
                self._wall_add_preview_image.source = ""

        self._wall_add_list.clear_widgets()
        if not visible_units:
            empty = Factory.BodyText(size_hint_y=None, height=dp(46))
            empty.text = "Нет доступных юнитов для текущего фильтра."
            self._wall_add_list.add_widget(empty)
            return

        for unit in visible_units[:220]:
            display_name = str(unit.get("display_name") or unit.get("name") or "")
            row = WallUnitRow(
                selected=display_name == self._wall_selected_unit_name,
                title_text=display_name,
                subtitle_text=self.wall_popup_unit_badge(unit),
                detail_text=self.wall_popup_unit_detail_text(unit),
                stats_text=self.wall_popup_unit_stats_text(unit),
                image_source=self.wall_popup_unit_image_source(unit, eager=True),
            )
            row.bind(on_release=lambda _instance, value=display_name: self.select_wall_popup_unit(value))
            self._wall_add_list.add_widget(row)

    def on_wall_popup_count_changed(self, _instance, value: str):
        if getattr(self, "_wall_add_syncing", False):
            return
        slider = getattr(self, "_wall_add_slider", None)
        if slider is None:
            return
        count = max(0, self.safe_int(value, 0))
        if count > slider.max:
            slider.max = count
        self._wall_add_syncing = True
        slider.value = count
        self._wall_add_syncing = False

    def on_wall_popup_slider_changed(self, _instance, value: float):
        if getattr(self, "_wall_add_syncing", False):
            return
        count_input = getattr(self, "_wall_add_count", None)
        if count_input is None:
            return
        self._wall_add_syncing = True
        count_input.text = str(int(value)) if int(value) > 0 else ""
        self._wall_add_syncing = False

    def build_wall_sector_summary(self, units: list[dict[str, Any]], flank_key: str, title: str) -> str:
        total = sum(self.get_unit_flank_count(unit, flank_key) for unit in units)
        if total <= 0:
            return f"{title}\n0 солдат\nПустой сектор"
        ranked = sorted(
            (
                (str(unit.get("name") or "Юнит"), self.get_unit_flank_count(unit, flank_key))
                for unit in units
                if self.get_unit_flank_count(unit, flank_key) > 0
            ),
            key=lambda item: item[1],
            reverse=True,
        )
        top_rows = ", ".join(f"{name} {count}" for name, count in ranked[:2])
        types_count = len(ranked)
        return f"{title}\n{total} солдат\n{types_count} типов: {top_rows}"

    def refresh_wall_scene(self):
        units_text = ""
        wall_base = ""
        wall_bonus = ""
        castle_name = self.active_castle_name or "Замок"
        if self.root:
            ids = self.root.ids
            if "unit_lines" in ids:
                units_text = str(ids.unit_lines.text or "")
            if "wall_units_base" in ids:
                wall_base = str(ids.wall_units_base.text or "")
            wall_bonus = str(self.governor_from_form().get("wall_limit_bonus") or "") if self.root else ""
            if "castle_spinner" in ids and not self.active_castle_name:
                castle_name = str(ids.castle_spinner.text or castle_name)

        units = self.parse_unit_lines(units_text)
        left_total = sum(self.get_unit_flank_count(unit, "left") for unit in units)
        center_total = sum(self.get_unit_flank_count(unit, "center") for unit in units)
        right_total = sum(self.get_unit_flank_count(unit, "right") for unit in units)
        wall_total = left_total + center_total + right_total
        wall_capacity = self.safe_int(wall_base, 0) + self.safe_int(wall_bonus, 0)

        self.wall_scene_caption = f"Стена замка: {castle_name}"
        if wall_capacity > 0:
            self.wall_scene_totals = f"На стене {wall_total} солдат · лимит {wall_capacity}"
        else:
            self.wall_scene_totals = f"На стене {wall_total} солдат"
        self.wall_active_flank_label = self.flank_label(self.wall_active_flank)
        self.wall_left_summary = self.build_wall_sector_summary(units, "left", "Левый фланг")
        self.wall_center_summary = self.build_wall_sector_summary(units, "center", "Центр")
        self.wall_right_summary = self.build_wall_sector_summary(units, "right", "Правый фланг")
        self.wall_active_units_output = self.build_active_wall_units_output(units, self.wall_active_flank)
        self.refresh_wall_active_units_list(units, self.wall_active_flank)
        self.refresh_defense_tools_list()

    def add_castle_profile(self):
        if not self.active_account_name:
            self.create_or_open_account()
            if not self.active_account_name:
                self.profile_output = "Сначала введи имя аккаунта и открой его."
                return
        new_name = self.root.ids.new_castle_name.text.strip()
        if not new_name:
            self.refresh_profile_output("Введи название нового замка, аванпоста или мира.")
            return
        account = self.current_account()
        if not account:
            return
        castles = account.setdefault("castles", {})
        castles.setdefault(new_name, default_castle_record(new_name))
        self.castle_values = self.build_castle_values(account)
        self.root.ids.new_castle_name.text = ""
        self._suspend_castle_events = True
        self.root.ids.castle_spinner.text = new_name
        self._suspend_castle_events = False
        self.active_castle_name = new_name
        self.load_castle_to_form(new_name)
        self.save_profile_store()
        self.refresh_profile_output(f"Добавлен новый профиль: {new_name}")
        self.refresh_castle_selector_popup()

    def activate_account(self, account_name: str, castle_name: str | None = None):
        account = self.ensure_account(account_name)
        self.active_account_name = account_name
        self.profile_store["active_account"] = account_name
        self.castle_values = self.build_castle_values(account)
        if self.root and "account_name" in self.root.ids:
            self.root.ids.account_name.text = account_name
        target_castle = castle_name or self.active_castle_name or self.castle_values[0]
        if target_castle not in account["castles"]:
            target_castle = self.castle_values[0]
        self._suspend_castle_events = True
        self.active_castle_name = target_castle
        if self.root and "castle_spinner" in self.root.ids:
            self.root.ids.castle_spinner.text = target_castle
        self.load_castle_to_form(target_castle)
        self._suspend_castle_events = False
        self.refresh_profile_output(f"Файл профиля: {self.profiles_path()}")
        self.save_profile_store()
        self.refresh_castle_selector_popup()

    def create_or_open_account(self):
        account_name = self.root.ids.account_name.text.strip() if self.root and "account_name" in self.root.ids else ""
        if not account_name:
            self.profile_output = "Введи имя аккаунта, чтобы создать локальный профиль."
            return
        self.activate_account(account_name)

    def select_castle(self, castle_name: str):
        if self._suspend_castle_events:
            return
        if not castle_name or not self.active_account_name:
            return
        if castle_name == self.active_castle_name:
            return
        self.store_current_castle(silent=True)
        self.active_castle_name = castle_name
        self.load_castle_to_form(castle_name)
        self.refresh_profile_output(f"Выбран профиль: {castle_name}")
        self.save_profile_store()
        self.refresh_castle_selector_popup()

    def current_account(self) -> dict[str, Any] | None:
        if not self.active_account_name:
            return None
        return self.profile_store.get("accounts", {}).get(self.active_account_name)

    def current_castle_record(self) -> dict[str, Any] | None:
        account = self.current_account()
        if not account or not self.active_castle_name:
            return None
        return account.get("castles", {}).get(self.active_castle_name)

    def commander_from_form(self) -> dict[str, str]:
        ids = self.root.ids
        return {
            "melee_bonus": ids.commander_melee_bonus.text,
            "ranged_bonus": ids.commander_ranged_bonus.text,
            "overall_bonus": ids.commander_overall_bonus.text,
            "flank_bonus": ids.commander_flank_bonus.text,
            "center_bonus": ids.commander_center_bonus.text,
            "courtyard_bonus": ids.commander_courtyard_bonus.text,
            "wall_bonus": ids.commander_wall_bonus.text,
            "gate_bonus": ids.commander_gate_bonus.text,
            "moat_bonus": ids.commander_moat_bonus.text,
        }

    def castle_from_form(self) -> dict[str, Any]:
        ids = self.root.ids
        current_castle = self.current_castle_record() or {}
        return {
            "name": self.active_castle_name or ids.castle_spinner.text or "Замок",
            "display_name": str(current_castle.get("display_name") or self.active_castle_name or ids.castle_spinner.text or "Замок"),
            "wall_units_base": ids.wall_units_base.text,
            "defensive_resources_note": ids.defensive_resources_note.text,
            "governor": self.governor_profile_from_form(),
            "commander": self.commander_from_form(),
            "building_levels": dict(current_castle.get("building_levels") or {}),
            "units_text": ids.unit_lines.text,
            "defensive_tools_text": ids.defensive_tools_lines.text,
        }

    def store_current_castle(self, silent: bool = False):
        account = self.current_account()
        if not account or not self.active_castle_name:
            return
        account.setdefault("castles", {})[self.active_castle_name] = self.castle_from_form()
        self.castle_values = self.build_castle_values(account)
        self.save_profile_store()
        self.refresh_active_account_state()
        self.refresh_castle_selector_popup()
        if not silent:
            self.refresh_profile_output(f"Профиль '{self.active_castle_name}' сохранён.")

    def load_castle_to_form(self, castle_name: str):
        account = self.current_account()
        if not account:
            return
        castle = account.setdefault("castles", {}).setdefault(castle_name, default_castle_record(castle_name))
        governor = castle.get("governor") or default_governor()
        commander = castle.get("commander") or default_commander()
        ids = self.root.ids
        if "castle_spinner" in ids:
            ids.castle_spinner.text = castle_name
        if "current_profile_display_name" in ids:
            desired_name = str(castle.get("display_name") or castle_name)
            if ids.current_profile_display_name.text != desired_name:
                ids.current_profile_display_name.text = desired_name
        ids.wall_units_base.text = str(castle.get("wall_units_base") or "")
        ids.defensive_resources_note.text = str(castle.get("defensive_resources_note") or "")
        ids.unit_lines.text = str(castle.get("units_text") or "")
        ids.defensive_tools_lines.text = str(castle.get("defensive_tools_text") or "")
        if "governor_general_picker" in ids:
            ids.governor_general_picker.text = str(governor.get("general_name") or GOVERNOR_GENERAL_NONE)
        if "governor_general_name" in ids:
            ids.governor_general_name.text = str(governor.get("general_name") or GOVERNOR_GENERAL_NONE)
        if "governor_general_id" in ids:
            ids.governor_general_id.text = str(governor.get("general_id") or "")
        ids.governor_melee_bonus.text = str(governor.get("melee_bonus") or "")
        ids.governor_ranged_bonus.text = str(governor.get("ranged_bonus") or "")
        if "governor_flank_bonus" in ids:
            ids.governor_flank_bonus.text = str(governor.get("flank_bonus") or "")
        ids.governor_courtyard_bonus.text = str(governor.get("courtyard_bonus") or "")
        ids.governor_center_bonus.text = str(governor.get("center_bonus") or "")
        ids.governor_overall_bonus.text = str(governor.get("overall_bonus") or "")
        ids.governor_wall_defense.text = str(governor.get("wall_defense") or "")
        ids.governor_gate_defense.text = str(governor.get("gate_defense") or "")
        ids.governor_moat_defense.text = str(governor.get("moat_defense") or "")
        ids.governor_wall_limit_bonus.text = str(governor.get("wall_limit_bonus") or "")
        if "governor_wall_limit_percent_bonus" in ids:
            ids.governor_wall_limit_percent_bonus.text = str(governor.get("wall_limit_percent_bonus") or "")
        if "governor_courtyard_size_bonus" in ids:
            ids.governor_courtyard_size_bonus.text = str(governor.get("courtyard_size_bonus") or "")
        if "skill_flank_bonus_level" in ids:
            ids.skill_flank_bonus_level.text = str(governor.get("skill_flank_bonus_level") or "")
        if "skill_center_bonus_level" in ids:
            ids.skill_center_bonus_level.text = str(governor.get("skill_center_bonus_level") or "")
        if "skill_courtyard_bonus_level" in ids:
            ids.skill_courtyard_bonus_level.text = str(governor.get("skill_courtyard_bonus_level") or "")
        if "skill_wall_limit_percent_bonus_level" in ids:
            ids.skill_wall_limit_percent_bonus_level.text = str(governor.get("skill_wall_limit_percent_bonus_level") or "")
        if "skill_courtyard_size_bonus_level" in ids:
            ids.skill_courtyard_size_bonus_level.text = str(governor.get("skill_courtyard_size_bonus_level") or "")
        ids.commander_melee_bonus.text = str(commander.get("melee_bonus") or "")
        ids.commander_ranged_bonus.text = str(commander.get("ranged_bonus") or "")
        ids.commander_overall_bonus.text = str(commander.get("overall_bonus") or "")
        ids.commander_flank_bonus.text = str(commander.get("flank_bonus") or "")
        ids.commander_center_bonus.text = str(commander.get("center_bonus") or "")
        ids.commander_courtyard_bonus.text = str(commander.get("courtyard_bonus") or "")
        ids.commander_wall_bonus.text = str(commander.get("wall_bonus") or "")
        ids.commander_gate_bonus.text = str(commander.get("gate_bonus") or "")
        ids.commander_moat_bonus.text = str(commander.get("moat_bonus") or "")
        if self.defense_tool_values:
            self.update_defense_tool_preview(self.defense_tool_values[0])
        else:
            self.update_defense_tool_preview("")
        self.refresh_governor_general_summary()
        if self.unit_values:
            self.update_unit_preview(self.unit_values[0])
        self.refresh_wall_scene()
        self.refresh_profile_output()
        self.refresh_available_building_catalog()
        self.refresh_profile_output()

    def update_unit_preview(self, unit_name: str):
        unit = self.unit_display_index.get(str(unit_name)) or self.unit_index.get(str(unit_name))
        if not unit:
            self.unit_picker_image_source = ""
            self.unit_picker_output = "Юнит не выбран."
            if getattr(self, "_wall_add_preview", None) is not None:
                self._wall_add_preview.text = self.unit_picker_output
            if getattr(self, "_wall_add_preview_image", None) is not None:
                self._wall_add_preview_image.source = ""
            return
        self.unit_picker_image_source = self.wall_popup_unit_image_source(unit, eager=True)
        self.unit_picker_output = self.format_wall_unit_card(unit)
        if getattr(self, "_wall_add_preview", None) is not None:
            self._wall_add_preview.text = self.unit_picker_output
        if getattr(self, "_wall_add_preview_image", None) is not None:
            self._wall_add_preview_image.source = self.unit_picker_image_source

    def add_selected_unit_to_garrison(self):
        ids = self.root.ids
        count_input = getattr(self, "_wall_add_count", None)
        unit_name = str(getattr(self, "_wall_selected_unit_name", "") or "").strip()
        unit = self.unit_display_index.get(unit_name) or self.unit_index.get(unit_name)
        if not unit:
            self.unit_picker_output = "Сначала выбери солдата из списка."
            return

        count = self.safe_int(count_input.text if count_input else "", 0)
        if count <= 0:
            self.unit_picker_output = "Укажи количество солдат для выбранного фланга."
            return

        rows = self.parse_unit_lines(ids.unit_lines.text)
        unit_name_value = str(unit.get("display_name") or unit["name"])
        editing_name = str(getattr(self, "_wall_edit_original_unit_name", "") or "").strip()
        if editing_name:
            for row in rows:
                if str(row.get("name") or "") != editing_name:
                    continue
                placed = dict(row.get("placed") or {})
                placed.setdefault("left", "0")
                placed.setdefault("center", "0")
                placed.setdefault("right", "0")
                placed[self.wall_active_flank] = "0"
                row["placed"] = placed
        current_row = next((row for row in rows if str(row.get("name") or "") == unit_name_value), None)
        if not current_row:
            current_row = {
                "name": unit_name_value,
                "available": "0",
                "melee_def": str(unit.get("melee_def") or 0),
                "ranged_def": str(unit.get("ranged_def") or 0),
                "placed": {"left": "0", "center": "0", "right": "0"},
            }
            rows.append(current_row)

        placed = dict(current_row.get("placed") or {})
        placed.setdefault("left", "0")
        placed.setdefault("center", "0")
        placed.setdefault("right", "0")
        if editing_name:
            placed[self.wall_active_flank] = str(count)
        else:
            placed[self.wall_active_flank] = str(self.safe_int(placed.get(self.wall_active_flank), 0) + count)
        current_row["placed"] = placed
        current_row["melee_def"] = str(unit.get("melee_def") or current_row.get("melee_def") or 0)
        current_row["ranged_def"] = str(unit.get("ranged_def") or current_row.get("ranged_def") or 0)
        placed_total = sum(self.get_unit_flank_count(current_row, flank) for flank in ("left", "center", "right"))
        current_row["available"] = str(max(self.safe_int(current_row.get("available"), 0), placed_total))

        cleaned_rows: list[dict[str, Any]] = []
        for row in rows:
            placed_total = sum(self.get_unit_flank_count(row, flank) for flank in ("left", "center", "right"))
            available_total = self.safe_int(row.get("available"), 0)
            if placed_total <= 0 and available_total <= 0:
                continue
            cleaned_rows.append(row)

        ids.unit_lines.text = self.serialize_unit_lines(cleaned_rows)
        if count_input is not None:
            count_input.text = ""
        if getattr(self, "_wall_add_slider", None) is not None:
            self._wall_add_slider.value = 0
        self.unit_picker_output = (
            f"{unit_name_value} обновлён на участке: {self.flank_label(self.wall_active_flank)}."
            if editing_name
            else f"{unit_name_value} добавлен на участок: {self.flank_label(self.wall_active_flank)}."
        )
        self.refresh_wall_scene()
        self.close_wall_add_panel()
        if self.active_account_name:
            self.store_current_castle(silent=True)

    def update_attack_unit_preview(self, unit_name: str):
        unit = self.attack_unit_display_index.get(str(unit_name)) or self.attack_unit_index.get(str(unit_name))
        if not unit:
            self.attack_unit_picker_image_source = ""
            self.attack_unit_picker_output = "Атакующий юнит не выбран."
            return
        self.attack_unit_picker_image_source = self.resolve_image_source(str(unit.get("image_url") or ""))
        display_name = str(unit.get("display_name") or unit["name"])
        self.attack_unit_picker_output = (
            f"{display_name} | Категория: {unit.get('category') or 'без категории'} | "
            f"Атака: {unit.get('attack') or 0}"
        )

    def is_ranged_attacker(self, unit: dict[str, Any]) -> bool:
        role = str(unit.get("role") or "").strip().lower()
        if role:
            return role == "ranged"
        name = str(unit.get("name") or "").lower()
        return any(keyword in name for keyword in ("bow", "crossbow", "archer", "slingshot", "pyromaniac"))

    def add_selected_attack_unit(self):
        ids = self.root.ids
        unit_name = str(ids.attack_unit_picker.text or "").strip()
        unit = self.attack_unit_display_index.get(unit_name) or self.attack_unit_index.get(unit_name)
        if not unit:
            self.attack_unit_picker_output = "Сначала выбери атакующего солдата из списка."
            return

        flank = str(ids.attack_unit_flank.text or "left").strip().lower() or "left"
        wave = str(ids.attack_unit_wave.text or "1").strip() or "1"
        count = ids.attack_unit_count.text.strip() or "0"
        role = "ranged" if self.is_ranged_attacker(unit) else "melee"
        row = ",".join([flank, wave, str(unit.get("display_name") or unit["name"]), count, str(unit.get("attack") or 0), role])
        existing = ids.attack_unit_lines.text.strip()
        ids.attack_unit_lines.text = f"{existing}\n{row}" if existing else row
        ids.attack_unit_count.text = ""
        self.attack_unit_picker_output = f"{str(unit.get('display_name') or unit['name'])} добавлен в {flank} фланг, волна {wave}."

    def parse_attack_unit_lines(self, text: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = [part.strip() for part in line.split(",")]
            while len(parts) < 6:
                parts.append("")
            rows.append(
                {
                    "flank": parts[0],
                    "wave": parts[1],
                    "name": parts[2],
                    "count": parts[3],
                    "attack": parts[4],
                    "role": parts[5],
                }
            )
        return rows

    def parse_defensive_tool_lines(self, text: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = [part.strip() for part in line.split(",")]
            if len(parts) == 2:
                zone = "all"
                name, count = parts
            else:
                while len(parts) < 3:
                    parts.append("")
                zone, name, count = parts[0], parts[1], parts[2]
            rows.append(
                {
                    "flank": zone or "all",
                    "name": name,
                    "count": count,
                }
            )
        return rows

    def parse_upgrade_lines(self, text: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = [part.strip() for part in line.split(",")]
            while len(parts) < 4:
                parts.append("")
            rows.append(
                {
                    "level": parts[0],
                    "hammers": parts[1],
                    "tokens": parts[2],
                    "note": parts[3],
                }
            )
        return rows

    def parse_unit_lines(self, text: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = [part.strip() for part in line.split(",")]
            while len(parts) < 7:
                parts.append("0")
            rows.append(
                {
                    "name": parts[0],
                    "available": parts[1],
                    "melee_def": parts[2],
                    "ranged_def": parts[3],
                    "placed": {
                        "left": parts[4],
                        "center": parts[5],
                        "right": parts[6],
                    },
                }
            )
        return rows

    def parse_attack_tool_lines(self, text: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = [part.strip() for part in line.split(",")]
            if len(parts) == 2:
                flank = "all"
                wave = "1"
                name, count = parts
            elif len(parts) == 3:
                flank = parts[0]
                wave = "1"
                name, count = parts[1], parts[2]
            else:
                while len(parts) < 4:
                    parts.append("")
                flank, wave, name, count = parts[0], parts[1], parts[2], parts[3]
            rows.append(
                {
                    "flank": flank or "all",
                    "wave": wave or "1",
                    "name": name,
                    "count": count,
                }
            )
        return rows

    def calculate_upgrade(self):
        record = self.building_record()
        if not record:
            self.upgrade_output = "Сначала выбери здание из списка улучшений."
            return
        payload = {
            "building_name": record.get("display_name") or record.get("name") or "Здание",
            "current_level": self.upgrade_current_level_value,
            "target_level": self.upgrade_target_level_value,
            "levels": record.get("levels") or [],
            "resource_fields": record.get("resource_fields") or [],
        }
        result = calculate_building_upgrade_plan(payload)
        resource_fields = [str(field).strip() for field in (record.get("resource_fields") or []) if str(field).strip()]
        lines = [
            f"Здание: {result['building_name']}",
            f"Категория: {self.upgrade_selected_building_category}",
            f"Уровни: {result['current_level']} -> {result['target_level']}",
            "",
            "Итого за диапазон:",
        ]
        for field in resource_fields:
            lines.append(f"{self.building_resource_label(field)}: {self.format_compact_number(result['resource_totals'].get(field, 0))}")
        lines.append(f"Учтено шагов улучшения: {len(result.get('used_levels') or [])}")
        used_levels = result.get("used_levels") or []
        if used_levels:
            lines.append("")
            lines.append("По уровням:")
            previous_level = str(result.get("current_level") or "").strip()
            for row in used_levels:
                lines.append(self.building_level_step_text(previous_level, row, resource_fields))
                previous_level = str(row.get("level") or previous_level).strip() or previous_level
        if result.get("warnings"):
            lines.append("")
            lines.append("Предупреждения:")
            lines.extend(result["warnings"])
        self.upgrade_output = "\n".join(lines)

    def calculate_profile_defense(self):
        if not self.active_account_name:
            self.create_or_open_account()
            if not self.active_account_name:
                self.defense_output = "Сначала создай аккаунт и выбери замок."
                return

        self.store_current_castle(silent=True)
        current_castle = self.current_castle_record() or default_castle_record(self.active_castle_name or "Замок")
        payload = {
            "max_waves": self.get_attack_wave_count(),
            "castle": {
                "name": current_castle.get("name") or self.active_castle_name,
                "wall_units_base": self.root.ids.wall_units_base.text,
                "defensive_resources_note": self.root.ids.defensive_resources_note.text,
            },
            "governor": self.governor_from_form(),
            "commander": self.commander_from_form(),
            "units": self.parse_unit_lines(self.root.ids.unit_lines.text),
            "attack_units": self.parse_attack_unit_lines(self.root.ids.attack_unit_lines.text),
            "attack_tools": self.parse_attack_tool_lines(self.root.ids.attack_tools_lines.text),
            "defense_tools": self.parse_defensive_tool_lines(self.root.ids.defensive_tools_lines.text),
            "flanks": {
                "left": {
                    "enemy_melee": self.root.ids.left_enemy_melee.text,
                    "enemy_ranged": self.root.ids.left_enemy_ranged.text,
                    "tool_melee_bonus": self.root.ids.left_tool_melee.text,
                    "tool_ranged_bonus": self.root.ids.left_tool_ranged.text,
                    "extra_bonus_percent": self.root.ids.left_extra_bonus.text,
                },
                "center": {
                    "enemy_melee": self.root.ids.center_enemy_melee.text,
                    "enemy_ranged": self.root.ids.center_enemy_ranged.text,
                    "tool_melee_bonus": self.root.ids.center_tool_melee.text,
                    "tool_ranged_bonus": self.root.ids.center_tool_ranged.text,
                    "extra_bonus_percent": self.root.ids.center_extra_bonus.text,
                },
                "right": {
                    "enemy_melee": self.root.ids.right_enemy_melee.text,
                    "enemy_ranged": self.root.ids.right_enemy_ranged.text,
                    "tool_melee_bonus": self.root.ids.right_tool_melee.text,
                    "tool_ranged_bonus": self.root.ids.right_tool_ranged.text,
                    "extra_bonus_percent": self.root.ids.right_extra_bonus.text,
                },
            },
        }
        result = calculate_profile_defense_plan(payload)
        summary = result["summary"]
        overview = result["castle_overview"]
        courtyard = result["courtyard"]
        attack_summary = result["attack_summary"]
        losses = result["losses"]
        lines = [
            f"Аккаунт: {self.active_account_name}",
            f"Замок: {overview['castle_name']}",
            f"Всего защитников: {overview['total_units']}",
            f"На стене: {overview['units_on_wall']} / {overview['wall_unit_limit_total'] or 'лимит не задан'}",
            f"Сырая мощь защиты: {overview['base_total_power']}",
            f"Мощь с общими бонусами: {overview['boosted_total_power']}",
            f"Настроено волн атаки: {attack_summary['configured_max_waves']}",
            f"Использовано волн: {attack_summary['used_waves_count']} ({', '.join(attack_summary['used_waves']) if attack_summary['used_waves'] else 'нет'})",
            f"Сырая мощь атаки: {attack_summary['base_total_attack']}",
            f"Мощь атаки с учётом волн и орудий: {attack_summary['boosted_total_attack']}",
            f"Мощь двора: {courtyard['estimated_power']}",
            f"Сила прорыва во двор: {courtyard['breach_attack_power']}",
            f"Потери во дворе от орудий: {courtyard['estimated_losses']}",
            "",
            f"Общая защита по флангам: {summary['overall_defense']}",
            f"Общая атака врага: {summary['overall_enemy_attack']}",
            f"Запас/дефицит: {summary['overall_margin']}",
            f"Самый слабый фланг: {summary['weakest_flank']}",
            f"Удержаны фланги: {', '.join(summary['held_flanks']) if summary['held_flanks'] else 'нет'}",
            f"Прорваны фланги: {', '.join(summary['breached_flanks']) if summary['breached_flanks'] else 'нет'}",
            f"Исход замка: {'замок падает' if summary['castle_falls'] else 'замок держится'}",
            f"Потери атакующего на стене: {losses['attacker_wall_losses']}",
            f"Потери защитника на стене: {losses['defender_wall_losses']}",
            f"Суммарные потери атакующего: {losses['attacker_total_losses']}",
            f"Суммарные потери защитника: {losses['defender_total_losses']}",
            "",
        ]

        if result["defense_tools"]["selected"]:
            lines.append("Оборонительные орудия:")
            for tool in result["defense_tools"]["selected"]:
                lines.append(f"- {tool['flank']}: {tool['count']} x {tool['name']}")
            lines.append("")

        if result["attack_tools"]["selected"]:
            lines.append("Орудия атакующего:")
            for tool in result["attack_tools"]["selected"]:
                lines.append(f"- {tool['flank']} / волна {tool['wave']}: {tool['count']} x {tool['name']}")
            lines.append("")

        if result["attack_units"]["selected"]:
            lines.append("Атакующие солдаты:")
            for unit in result["attack_units"]["selected"]:
                lines.append(f"- {unit['flank']} / волна {unit['wave']}: {unit['count']} x {unit['name']} ({unit['role']})")
            lines.append("")

        for flank_key in ("left", "center", "right"):
            flank = result["flanks"][flank_key]
            lines.append(flank["label"].upper())
            lines.append(f"Защита ближ.: {flank['final_melee_defense']} против {flank['enemy_melee']}")
            lines.append(f"Защита дальн.: {flank['final_ranged_defense']} против {flank['enemy_ranged']}")
            lines.append(f"Баланс: {flank['total_margin']}")
            lines.append(f"Стена: {'удержана' if flank['wall_held'] else 'прорвана'}")
            lines.append(f"Потери атакующего / защитника: {flank['attacker_losses']} / {flank['defender_losses']}")
            if flank["waves"]:
                for wave in flank["waves"]:
                    lines.append(f"Волна {wave['wave']}: ближ. {wave['melee_attack']} / дальн. {wave['ranged_attack']}")
            if flank["applied_tool_effects"]:
                lines.append(f"Эффекты орудий: {flank['applied_tool_effects']}")
            if flank["applied_defense_tools"]:
                lines.append(f"Эффекты обороны: {flank['applied_defense_tools']}")
            if flank["advice"]:
                for advice in flank["advice"]:
                    lines.append(f"- {advice}")
            lines.append("")

        if result["attack_recommendations"]:
            lines.append("Рекомендации для атаки:")
            for item in result["attack_recommendations"]:
                lines.append(f"- {item}")
            lines.append("")

        if result["reserve_left"]:
            lines.append("Резерв:")
            for item in result["reserve_left"]:
                lines.append(f"{item['reserve']} x {item['name']}")

        if overview["defensive_resources_note"]:
            lines.append("")
            lines.append(f"Ресурсы обороны: {overview['defensive_resources_note']}")

        if result["warnings"]:
            lines.append("")
            lines.append("Предупреждения:")
            lines.extend(result["warnings"])
        self.defense_output = "\n".join(lines).strip()

if __name__ == "__main__":
    EmpireCalcApp().run()
