from __future__ import annotations

import json
from pathlib import Path
from tkinter import BOTH, HORIZONTAL, LEFT, RIGHT, VERTICAL, X, Y, Canvas, StringVar, Tk, Toplevel, filedialog, ttk
from typing import Any

from .paths import LIVE_ACTION_MAP_PATH, SCREEN_PROFILE_PATH

TARGET_DEFINITIONS: list[dict[str, str]] = [
    {"key": "player_name_region", "label": "Имя игрока", "kind": "region"},
    {"key": "food_region", "label": "Еда", "kind": "region"},
    {"key": "wood_region", "label": "Дерево", "kind": "region"},
    {"key": "stone_region", "label": "Камень", "kind": "region"},
    {"key": "coins_region", "label": "Монеты", "kind": "region"},
    {"key": "rubies_region", "label": "Рубины", "kind": "region"},
    {"key": "collect_food", "label": "Сбор еды", "kind": "point"},
    {"key": "collect_wood", "label": "Сбор дерева", "kind": "point"},
    {"key": "collect_stone", "label": "Сбор камня", "kind": "point"},
    {"key": "upgrade_farm", "label": "Апгрейд фермы", "kind": "point"},
    {"key": "upgrade_lumberyard", "label": "Апгрейд лесопилки", "kind": "point"},
    {"key": "upgrade_quarry", "label": "Апгрейд каменоломни", "kind": "point"},
    {"key": "build_house", "label": "Построить дом", "kind": "point"},
    {"key": "upgrade_academy", "label": "Апгрейд академии", "kind": "point"},
    {"key": "train_soldiers", "label": "Тренировка солдат", "kind": "point"},
]
TARGET_MAP = {item["key"]: item for item in TARGET_DEFINITIONS}
ACTION_KEYS = {
    "collect_food",
    "collect_wood",
    "collect_stone",
    "upgrade_farm",
    "upgrade_lumberyard",
    "upgrade_quarry",
    "build_house",
    "upgrade_academy",
    "train_soldiers",
}
ACTION_PAUSES = {
    "collect_food": 0.6,
    "collect_wood": 0.6,
    "collect_stone": 0.6,
    "upgrade_farm": 0.8,
    "upgrade_lumberyard": 0.8,
    "upgrade_quarry": 0.8,
    "build_house": 0.8,
    "upgrade_academy": 0.8,
    "train_soldiers": 0.8,
}


def _default_profile(image_path: str = "") -> dict[str, Any]:
    return {
        "image_path": image_path,
        "image_size": {"width": 0, "height": 0},
        "targets": {},
    }


def load_screen_profile(profile_path: Path) -> dict[str, Any]:
    if not profile_path.exists():
        return _default_profile()
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return _default_profile()
    targets = payload.get("targets") if isinstance(payload.get("targets"), dict) else {}
    image_size = payload.get("image_size") if isinstance(payload.get("image_size"), dict) else {"width": 0, "height": 0}
    return {
        "image_path": str(payload.get("image_path") or ""),
        "image_size": {
            "width": int(image_size.get("width") or 0),
            "height": int(image_size.get("height") or 0),
        },
        "targets": targets,
    }


def save_screen_profile(profile_path: Path, payload: dict[str, Any]) -> None:
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def export_action_map(profile_path: Path, action_map_path: Path) -> dict[str, Any]:
    profile = load_screen_profile(profile_path)
    if action_map_path.exists():
        payload = json.loads(action_map_path.read_text(encoding="utf-8"))
        action_map: dict[str, Any] = payload if isinstance(payload, dict) else {}
    else:
        action_map = {}
    targets = profile.get("targets") or {}
    for action_key in ACTION_KEYS:
        target = targets.get(action_key)
        if not isinstance(target, dict) or target.get("type") != "point":
            continue
        action_map[action_key] = {
            "type": "click",
            "x": int(target.get("x") or 0),
            "y": int(target.get("y") or 0),
            "pause_after": ACTION_PAUSES.get(action_key, 0.8),
        }
    action_map.setdefault("wait", {"type": "press", "key": "space", "pause_after": 0.3})
    action_map_path.parent.mkdir(parents=True, exist_ok=True)
    action_map_path.write_text(json.dumps(action_map, ensure_ascii=False, indent=2), encoding="utf-8")
    return action_map


class ScreenCalibrationUi:
    def __init__(
        self,
        parent=None,
        profile_path: Path = SCREEN_PROFILE_PATH,
        action_map_path: Path = LIVE_ACTION_MAP_PATH,
        initial_image_path: str = "",
    ) -> None:
        self._owns_root = parent is None
        self.window = Tk() if parent is None else Toplevel(parent)
        self.window.title("Empire ML Bot - Калибровка")
        self.window.geometry("1320x900")
        self.window.minsize(980, 700)

        self.profile_path = profile_path
        self.action_map_path = action_map_path
        self.profile = load_screen_profile(profile_path)
        if initial_image_path and not self.profile.get("image_path"):
            self.profile["image_path"] = initial_image_path

        self.image_path_var = StringVar(value=str(self.profile.get("image_path") or ""))
        self.profile_path_var = StringVar(value=str(self.profile_path))
        self.action_map_path_var = StringVar(value=str(self.action_map_path))
        self.target_var = StringVar(value=TARGET_DEFINITIONS[0]["key"])
        self.status_var = StringVar(value="Загрузи скриншот и отметь элементы мышкой.")

        self.photo_image = None
        self.image_id: int | None = None
        self.image_width = 0
        self.image_height = 0
        self.drag_start: tuple[int, int] | None = None
        self.temp_shape_id: int | None = None

        self._build_layout()
        self._load_image_if_possible()
        self._refresh_target_rows()
        self._select_tree_target(self.target_var.get())
        self.window.protocol("WM_DELETE_WINDOW", self.close)

    def _build_layout(self) -> None:
        root_frame = ttk.Frame(self.window, padding=10)
        root_frame.pack(fill=BOTH, expand=True)

        paned = ttk.Panedwindow(root_frame, orient=HORIZONTAL)
        paned.pack(fill=BOTH, expand=True)

        controls_frame = ttk.Frame(paned, padding=(0, 0, 10, 0))
        canvas_frame = ttk.Frame(paned)
        paned.add(controls_frame, weight=0)
        paned.add(canvas_frame, weight=1)

        file_box = ttk.LabelFrame(controls_frame, text="Файлы", padding=10)
        file_box.pack(fill=X)
        self._add_path_row(file_box, 0, "Скриншот", self.image_path_var, self.pick_image)
        self._add_path_row(file_box, 1, "Профиль", self.profile_path_var, self.pick_profile)
        self._add_path_row(file_box, 2, "Action map", self.action_map_path_var, self.pick_action_map)

        actions_box = ttk.LabelFrame(controls_frame, text="Действия", padding=10)
        actions_box.pack(fill=X, pady=(10, 0))
        ttk.Button(actions_box, text="Открыть скриншот", command=self.load_image_from_picker).pack(fill=X)
        ttk.Button(actions_box, text="Сохранить профиль", command=self.save_profile).pack(fill=X, pady=(6, 0))
        ttk.Button(actions_box, text="Экспортировать action map", command=self.export_action_map_file).pack(fill=X, pady=(6, 0))
        ttk.Button(actions_box, text="Очистить текущую цель", command=self.clear_current_target).pack(fill=X, pady=(6, 0))

        target_box = ttk.LabelFrame(controls_frame, text="Цели разметки", padding=10)
        target_box.pack(fill=BOTH, expand=True, pady=(10, 0))
        self.target_tree = ttk.Treeview(target_box, columns=("kind", "status"), show="tree headings", height=18)
        self.target_tree.heading("#0", text="Элемент")
        self.target_tree.heading("kind", text="Тип")
        self.target_tree.heading("status", text="Статус")
        self.target_tree.column("#0", width=180, stretch=True)
        self.target_tree.column("kind", width=70, stretch=False, anchor="center")
        self.target_tree.column("status", width=80, stretch=False, anchor="center")
        self.target_tree.pack(side=LEFT, fill=BOTH, expand=True)
        tree_scroll = ttk.Scrollbar(target_box, orient=VERTICAL, command=self.target_tree.yview)
        tree_scroll.pack(side=RIGHT, fill=Y)
        self.target_tree.configure(yscrollcommand=tree_scroll.set)
        self.target_tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        nav_box = ttk.Frame(controls_frame)
        nav_box.pack(fill=X, pady=(10, 0))
        ttk.Button(nav_box, text="Назад", command=self.select_previous_target).pack(side=LEFT, fill=X, expand=True)
        ttk.Button(nav_box, text="Вперёд", command=self.select_next_target).pack(side=LEFT, fill=X, expand=True, padx=(6, 0))

        status_box = ttk.LabelFrame(controls_frame, text="Статус", padding=10)
        status_box.pack(fill=X, pady=(10, 0))
        ttk.Label(status_box, textvariable=self.status_var, wraplength=280, justify=LEFT).pack(fill=X)

        hint_box = ttk.LabelFrame(controls_frame, text="Как отмечать", padding=10)
        hint_box.pack(fill=X, pady=(10, 0))
        ttk.Label(
            hint_box,
            text="Для point: кликни по нужной точке. Для region: зажми мышь и протяни прямоугольник.",
            wraplength=280,
            justify=LEFT,
        ).pack(fill=X)

        canvas_holder = ttk.LabelFrame(canvas_frame, text="Скриншот", padding=6)
        canvas_holder.pack(fill=BOTH, expand=True)
        self.canvas = Canvas(canvas_holder, background="#1e1e1e", highlightthickness=0)
        self.canvas.pack(side=LEFT, fill=BOTH, expand=True)
        y_scroll = ttk.Scrollbar(canvas_holder, orient=VERTICAL, command=self.canvas.yview)
        y_scroll.pack(side=RIGHT, fill=Y)
        x_scroll = ttk.Scrollbar(canvas_frame, orient=HORIZONTAL, command=self.canvas.xview)
        x_scroll.pack(fill=X)
        self.canvas.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)

    def _add_path_row(self, parent: ttk.Frame, row: int, label: str, variable: StringVar, command) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
        ttk.Entry(parent, textvariable=variable, width=32).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(parent, text="...", width=4, command=command).grid(row=row, column=2, sticky="e", padx=(6, 0), pady=4)
        parent.grid_columnconfigure(1, weight=1)

    def pick_image(self) -> None:
        path = filedialog.askopenfilename(
            title="Выбери скриншот",
            filetypes=(("Images", "*.png *.gif *.ppm *.pgm"), ("All", "*.*")),
        )
        if path:
            self.image_path_var.set(path)

    def pick_profile(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Профиль калибровки",
            defaultextension=".json",
            initialfile=Path(self.profile_path_var.get() or SCREEN_PROFILE_PATH).name,
            filetypes=(("JSON", "*.json"), ("All", "*.*")),
        )
        if path:
            self.profile_path_var.set(path)
            self.profile_path = Path(path)
            self.profile = load_screen_profile(self.profile_path)
            if self.profile.get("image_path"):
                self.image_path_var.set(str(self.profile.get("image_path") or ""))
                self._load_image_if_possible()
            self._refresh_target_rows()

    def pick_action_map(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Action map",
            defaultextension=".json",
            initialfile=Path(self.action_map_path_var.get() or LIVE_ACTION_MAP_PATH).name,
            filetypes=(("JSON", "*.json"), ("All", "*.*")),
        )
        if path:
            self.action_map_path_var.set(path)
            self.action_map_path = Path(path)

    def load_image_from_picker(self) -> None:
        if not self.image_path_var.get().strip():
            self.pick_image()
        self._load_image_if_possible()

    def _load_image_if_possible(self) -> None:
        path_value = self.image_path_var.get().strip()
        if not path_value:
            self.status_var.set("Выбери скриншот для калибровки.")
            return
        image_path = Path(path_value)
        if not image_path.exists():
            self.status_var.set(f"Скриншот не найден: {image_path}")
            return
        self.photo_image = None
        self.photo_image = __import__("tkinter").PhotoImage(file=str(image_path))
        self.image_width = int(self.photo_image.width())
        self.image_height = int(self.photo_image.height())
        self.canvas.delete("all")
        self.image_id = self.canvas.create_image(0, 0, anchor="nw", image=self.photo_image)
        self.canvas.configure(scrollregion=(0, 0, self.image_width, self.image_height))
        self.status_var.set(f"Скриншот загружен: {image_path.name} ({self.image_width}x{self.image_height})")
        self._render_overlay()

    def _refresh_target_rows(self) -> None:
        selected = self.target_var.get()
        for item_id in self.target_tree.get_children():
            self.target_tree.delete(item_id)
        targets = self.profile.get("targets") if isinstance(self.profile.get("targets"), dict) else {}
        for item in TARGET_DEFINITIONS:
            saved = item["key"] in targets
            self.target_tree.insert(
                "",
                "end",
                iid=item["key"],
                text=item["label"],
                values=(item["kind"], "готово" if saved else ""),
            )
        if selected in TARGET_MAP:
            self._select_tree_target(selected)

    def _select_tree_target(self, key: str) -> None:
        if key not in TARGET_MAP:
            return
        self.target_var.set(key)
        self.target_tree.selection_set(key)
        self.target_tree.focus(key)
        self.target_tree.see(key)
        self._update_status_for_target()

    def on_tree_select(self, _event=None) -> None:
        selection = self.target_tree.selection()
        if not selection:
            return
        self.target_var.set(selection[0])
        self._update_status_for_target()

    def _update_status_for_target(self) -> None:
        target = TARGET_MAP[self.target_var.get()]
        self.status_var.set(f"Текущая цель: {target['label']} ({target['kind']}).")

    def select_next_target(self) -> None:
        index = next((i for i, item in enumerate(TARGET_DEFINITIONS) if item["key"] == self.target_var.get()), 0)
        next_index = min(len(TARGET_DEFINITIONS) - 1, index + 1)
        self._select_tree_target(TARGET_DEFINITIONS[next_index]["key"])

    def select_previous_target(self) -> None:
        index = next((i for i, item in enumerate(TARGET_DEFINITIONS) if item["key"] == self.target_var.get()), 0)
        previous_index = max(0, index - 1)
        self._select_tree_target(TARGET_DEFINITIONS[previous_index]["key"])

    def _canvas_point(self, event) -> tuple[int, int]:
        x = int(max(0, min(self.image_width, self.canvas.canvasx(event.x))))
        y = int(max(0, min(self.image_height, self.canvas.canvasy(event.y))))
        return x, y

    def on_canvas_press(self, event) -> None:
        if not self.photo_image:
            return
        self.drag_start = self._canvas_point(event)
        target = TARGET_MAP[self.target_var.get()]
        if target["kind"] == "region":
            if self.temp_shape_id is not None:
                self.canvas.delete(self.temp_shape_id)
            x, y = self.drag_start
            self.temp_shape_id = self.canvas.create_rectangle(x, y, x, y, outline="#00ff99", width=2, dash=(6, 4), tags=("temp",))

    def on_canvas_drag(self, event) -> None:
        if not self.photo_image or not self.drag_start:
            return
        target = TARGET_MAP[self.target_var.get()]
        if target["kind"] != "region" or self.temp_shape_id is None:
            return
        x1, y1 = self.drag_start
        x2, y2 = self._canvas_point(event)
        self.canvas.coords(self.temp_shape_id, x1, y1, x2, y2)

    def on_canvas_release(self, event) -> None:
        if not self.photo_image or not self.drag_start:
            return
        target = TARGET_MAP[self.target_var.get()]
        x, y = self._canvas_point(event)
        if target["kind"] == "point":
            self._save_target(self.target_var.get(), {"type": "point", "x": x, "y": y})
        else:
            x1, y1 = self.drag_start
            left = min(x1, x)
            right = max(x1, x)
            top = min(y1, y)
            bottom = max(y1, y)
            if right - left < 2 or bottom - top < 2:
                self.status_var.set("Для region протяни прямоугольник чуть больше.")
            else:
                self._save_target(
                    self.target_var.get(),
                    {"type": "region", "x1": left, "y1": top, "x2": right, "y2": bottom},
                )
        self.drag_start = None
        if self.temp_shape_id is not None:
            self.canvas.delete(self.temp_shape_id)
            self.temp_shape_id = None
        self._render_overlay()

    def _save_target(self, key: str, data: dict[str, Any]) -> None:
        targets = self.profile.setdefault("targets", {})
        targets[key] = data
        self._refresh_target_rows()
        label = TARGET_MAP[key]["label"]
        if data.get("type") == "point":
            self.status_var.set(f"Сохранена точка для {label}: ({data['x']}, {data['y']})")
        else:
            self.status_var.set(
                f"Сохранена область для {label}: ({data['x1']}, {data['y1']}) - ({data['x2']}, {data['y2']})"
            )
        self.select_next_target()

    def clear_current_target(self) -> None:
        key = self.target_var.get()
        targets = self.profile.setdefault("targets", {})
        if key in targets:
            del targets[key]
            self._refresh_target_rows()
            self._render_overlay()
            self.status_var.set(f"Очищена разметка: {TARGET_MAP[key]['label']}")

    def _render_overlay(self) -> None:
        self.canvas.delete("overlay")
        targets = self.profile.get("targets") if isinstance(self.profile.get("targets"), dict) else {}
        for key, item in targets.items():
            target_def = TARGET_MAP.get(key)
            if not target_def or not isinstance(item, dict):
                continue
            if item.get("type") == "point":
                x = int(item.get("x") or 0)
                y = int(item.get("y") or 0)
                color = "#ffcc00" if key in ACTION_KEYS else "#66ccff"
                self.canvas.create_oval(x - 6, y - 6, x + 6, y + 6, outline=color, width=2, tags=("overlay",))
                self.canvas.create_line(x - 12, y, x + 12, y, fill=color, width=2, tags=("overlay",))
                self.canvas.create_line(x, y - 12, x, y + 12, fill=color, width=2, tags=("overlay",))
                self.canvas.create_text(x + 12, y - 12, text=target_def["label"], anchor="nw", fill=color, tags=("overlay",))
            elif item.get("type") == "region":
                x1 = int(item.get("x1") or 0)
                y1 = int(item.get("y1") or 0)
                x2 = int(item.get("x2") or 0)
                y2 = int(item.get("y2") or 0)
                color = "#00ff99"
                self.canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=2, tags=("overlay",))
                self.canvas.create_text(x1 + 6, y1 + 6, text=target_def["label"], anchor="nw", fill=color, tags=("overlay",))

    def save_profile(self) -> None:
        self.profile_path = Path(self.profile_path_var.get().strip() or SCREEN_PROFILE_PATH)
        self.action_map_path = Path(self.action_map_path_var.get().strip() or LIVE_ACTION_MAP_PATH)
        self.profile["image_path"] = self.image_path_var.get().strip()
        self.profile["image_size"] = {"width": self.image_width, "height": self.image_height}
        save_screen_profile(self.profile_path, self.profile)
        self.status_var.set(f"Профиль сохранён: {self.profile_path}")

    def export_action_map_file(self) -> None:
        self.save_profile()
        payload = export_action_map(self.profile_path, Path(self.action_map_path_var.get().strip() or LIVE_ACTION_MAP_PATH))
        self.status_var.set(f"Action map сохранён: {self.action_map_path_var.get().strip()} ({len(payload)} команд)")

    def close(self) -> None:
        self.window.destroy()

    def run(self) -> None:
        if self._owns_root:
            self.window.mainloop()


def launch_calibration_ui(
    parent=None,
    profile_path: Path = SCREEN_PROFILE_PATH,
    action_map_path: Path = LIVE_ACTION_MAP_PATH,
    initial_image_path: str = "",
) -> ScreenCalibrationUi:
    ui = ScreenCalibrationUi(
        parent=parent,
        profile_path=profile_path,
        action_map_path=action_map_path,
        initial_image_path=initial_image_path,
    )
    ui.run()
    return ui
