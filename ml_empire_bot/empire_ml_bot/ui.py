from __future__ import annotations

import json
import queue
import threading
import traceback
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, VERTICAL, BooleanVar, StringVar, Text, Tk, filedialog, ttk

from .calibration import launch_calibration_ui
from .config import AppSettings, load_app_settings, save_app_settings
from .paths import LIVE_ACTION_MAP_PATH, METRICS_PATH, SCOUT_REPORT_PATH, SCREEN_PROFILE_PATH


class BotControlUi:
    def __init__(self) -> None:
        self.settings = load_app_settings()
        self.root = Tk()
        self.root.title("Empire ML Bot")
        self.root.geometry("860x620")
        self.root.minsize(760, 520)

        self.message_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.worker_thread: threading.Thread | None = None
        self.stop_event = threading.Event()

        self.run_mode_var = StringVar(value=self.settings.run_mode)
        self.collect_episodes_var = StringVar(value=str(self.settings.collect_episodes))
        self.simulate_episodes_var = StringVar(value=str(self.settings.simulate_episodes))
        self.steps_var = StringVar(value=str(self.settings.steps))
        self.poll_interval_var = StringVar(value=str(self.settings.poll_interval_sec))
        self.model_path_var = StringVar(value=self.settings.model_path)
        self.live_state_path_var = StringVar(value=self.settings.live_state_path)
        self.screen_profile_path_var = StringVar(value=self.settings.screen_profile_path)
        self.live_action_map_path_var = StringVar(value=self.settings.live_action_map_path)
        self.scout_report_path_var = StringVar(value=self.settings.scout_report_path)
        self.window_title_var = StringVar(value=self.settings.game_window_title)
        self.dry_run_var = BooleanVar(value=self.settings.dry_run)

        self._build_layout()
        self.root.after(150, self._drain_messages)

    def _build_layout(self) -> None:
        root_frame = ttk.Frame(self.root, padding=12)
        root_frame.pack(fill=BOTH, expand=True)

        config_frame = ttk.LabelFrame(root_frame, text="Настройки", padding=12)
        config_frame.pack(fill="x")

        self._add_row(config_frame, 0, "Режим", self._mode_box(config_frame))
        self._add_row(config_frame, 1, "Коллекция эпизодов", ttk.Entry(config_frame, textvariable=self.collect_episodes_var, width=18))
        self._add_row(config_frame, 2, "Симуляция эпизодов", ttk.Entry(config_frame, textvariable=self.simulate_episodes_var, width=18))
        self._add_row(config_frame, 3, "Шагов", ttk.Entry(config_frame, textvariable=self.steps_var, width=18))
        self._add_row(config_frame, 4, "Пауза live (сек)", ttk.Entry(config_frame, textvariable=self.poll_interval_var, width=18))
        self._add_row(config_frame, 5, "Модель", self._path_row(config_frame, self.model_path_var, (("Joblib", "*.joblib"), ("All", "*.*"))))
        self._add_row(config_frame, 6, "Live state JSON", self._path_row(config_frame, self.live_state_path_var, (("JSON", "*.json"), ("All", "*.*"))))
        self._add_row(config_frame, 7, "Screen profile JSON", self._path_row(config_frame, self.screen_profile_path_var, (("JSON", "*.json"), ("All", "*.*"))))
        self._add_row(config_frame, 8, "Action map JSON", self._path_row(config_frame, self.live_action_map_path_var, (("JSON", "*.json"), ("All", "*.*"))))
        self._add_row(config_frame, 9, "Scout report JSON", self._path_row(config_frame, self.scout_report_path_var, (("JSON", "*.json"), ("All", "*.*"))))
        self._add_row(config_frame, 10, "Окно игры", ttk.Entry(config_frame, textvariable=self.window_title_var, width=40))
        self._add_row(config_frame, 11, "Dry-run", ttk.Checkbutton(config_frame, variable=self.dry_run_var))

        controls = ttk.Frame(root_frame, padding=(0, 12, 0, 12))
        controls.pack(fill="x")
        self.start_button = ttk.Button(controls, text="Запустить", command=self.on_start)
        self.start_button.pack(side=LEFT)
        self.stop_button = ttk.Button(controls, text="Остановить", command=self.on_stop, state="disabled")
        self.stop_button.pack(side=LEFT, padx=(8, 0))
        ttk.Button(controls, text="Калибровка", command=self.open_calibration).pack(side=LEFT, padx=(8, 0))
        ttk.Button(controls, text="Открыть metrics", command=self.open_metrics).pack(side=RIGHT)

        log_frame = ttk.LabelFrame(root_frame, text="Статус", padding=8)
        log_frame.pack(fill=BOTH, expand=True)
        scrollbar = ttk.Scrollbar(log_frame, orient=VERTICAL)
        scrollbar.pack(side=RIGHT, fill="y")
        self.log_text = Text(log_frame, wrap="word", yscrollcommand=scrollbar.set, height=20)
        self.log_text.pack(fill=BOTH, expand=True)
        scrollbar.config(command=self.log_text.yview)
        self._log("UI готов. Можно запускать demo, live, scout или auto.")

    def _mode_box(self, parent: ttk.Frame) -> ttk.Combobox:
        combo = ttk.Combobox(parent, textvariable=self.run_mode_var, width=20, state="readonly")
        combo["values"] = ("live", "demo", "scout", "auto")
        return combo

    def _path_row(self, parent: ttk.Frame, variable: StringVar, filetypes: tuple[tuple[str, str], ...]) -> ttk.Frame:
        frame = ttk.Frame(parent)
        entry = ttk.Entry(frame, textvariable=variable, width=60)
        entry.pack(side=LEFT, fill="x", expand=True)
        ttk.Button(frame, text="...", width=4, command=lambda: self.pick_file(variable, filetypes)).pack(side=LEFT, padx=(6, 0))
        return frame

    def _add_row(self, parent: ttk.Frame, row: int, label: str, widget) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 10))
        widget.grid(row=row, column=1, sticky="ew", pady=4)
        parent.grid_columnconfigure(1, weight=1)

    def pick_file(self, variable: StringVar, filetypes: tuple[tuple[str, str], ...]) -> None:
        selected = filedialog.askopenfilename(title="Выбери файл", filetypes=filetypes)
        if selected:
            variable.set(selected)

    def open_metrics(self) -> None:
        if METRICS_PATH.exists():
            self._log(METRICS_PATH.read_text(encoding="utf-8"))
        else:
            self._log("Файл metrics ещё не создан.")

    def _collect_settings(self) -> AppSettings:
        return AppSettings(
            run_mode=self.run_mode_var.get().strip() or "live",
            collect_episodes=max(1, int(self.collect_episodes_var.get() or 120)),
            simulate_episodes=max(1, int(self.simulate_episodes_var.get() or 20)),
            steps=max(1, int(self.steps_var.get() or 50)),
            poll_interval_sec=max(0.0, float(self.poll_interval_var.get() or 1.5)),
            dry_run=bool(self.dry_run_var.get()),
            model_path=self.model_path_var.get().strip(),
            live_state_path=self.live_state_path_var.get().strip(),
            screen_profile_path=self.screen_profile_path_var.get().strip(),
            live_action_map_path=self.live_action_map_path_var.get().strip(),
            scout_report_path=self.scout_report_path_var.get().strip(),
            live_command_log_path=self.settings.live_command_log_path,
            live_session_log_path=self.settings.live_session_log_path,
            game_window_title=self.window_title_var.get().strip() or "Goodgame Empire",
        )

    def open_calibration(self) -> None:
        profile_path = Path(self.screen_profile_path_var.get().strip() or str(SCREEN_PROFILE_PATH))
        action_map_path = Path(self.live_action_map_path_var.get().strip() or str(LIVE_ACTION_MAP_PATH))
        scout_report_path = Path(self.scout_report_path_var.get().strip() or str(SCOUT_REPORT_PATH))
        self.settings.screen_profile_path = str(profile_path)
        self.settings.live_action_map_path = str(action_map_path)
        self.settings.scout_report_path = str(scout_report_path)
        save_app_settings(self.settings)
        launch_calibration_ui(parent=self.root, profile_path=profile_path, action_map_path=action_map_path)
        self._log(f"Открыта калибровка: {profile_path}")

    def on_start(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            self._log("Уже выполняется задача.")
            return
        try:
            self.settings = self._collect_settings()
        except Exception as exc:
            self._log(f"Ошибка в настройках: {exc}")
            return
        save_app_settings(self.settings)
        self.stop_event.clear()
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self._log(f"Запуск режима: {self.settings.run_mode}")
        self.worker_thread = threading.Thread(target=self._run_worker, daemon=True)
        self.worker_thread.start()

    def on_stop(self) -> None:
        self.stop_event.set()
        self._log("Запрошена остановка live-бота.")

    def _run_worker(self) -> None:
        try:
            if self.settings.run_mode == "demo":
                from .runner import run_demo_pipeline

                result = run_demo_pipeline(
                    collect_episodes=self.settings.collect_episodes,
                    simulate_episodes=self.settings.simulate_episodes,
                    steps_per_episode=self.settings.steps,
                )
            elif self.settings.run_mode == "scout":
                from .auto_scout import AutoScoutConfig, run_auto_scout

                config = AutoScoutConfig(
                    profile_path=Path(self.settings.screen_profile_path),
                    report_path=Path(self.settings.scout_report_path),
                    max_steps=self.settings.steps,
                    dry_run=self.settings.dry_run,
                    game_window_title=self.settings.game_window_title,
                )
                result = run_auto_scout(config=config, status_callback=self._emit_status, stop_event=self.stop_event)
            elif self.settings.run_mode == "auto":
                from .auto_scout import AutoPilotConfig, run_auto_pilot

                config = AutoPilotConfig(
                    profile_path=Path(self.settings.screen_profile_path),
                    report_path=Path(self.settings.scout_report_path),
                    max_steps=self.settings.steps,
                    dry_run=self.settings.dry_run,
                    game_window_title=self.settings.game_window_title,
                )
                result = run_auto_pilot(config=config, status_callback=self._emit_status, stop_event=self.stop_event)
            else:
                from .live_bot import LiveRunConfig, run_live_bot

                config = LiveRunConfig(
                    model_path=Path(self.settings.model_path),
                    state_path=Path(self.settings.live_state_path),
                    action_map_path=Path(self.settings.live_action_map_path),
                    command_log_path=Path(self.settings.live_command_log_path),
                    session_log_path=Path(self.settings.live_session_log_path),
                    poll_interval_sec=self.settings.poll_interval_sec,
                    max_steps=self.settings.steps,
                    dry_run=self.settings.dry_run,
                    game_window_title=self.settings.game_window_title,
                )
                result = run_live_bot(config=config, status_callback=self._emit_status, stop_event=self.stop_event)
            self.message_queue.put(("done", json.dumps(result, ensure_ascii=False, indent=2)))
        except Exception:
            self.message_queue.put(("error", traceback.format_exc()))

    def _emit_status(self, message: str) -> None:
        self.message_queue.put(("log", message))

    def _drain_messages(self) -> None:
        while True:
            try:
                message_type, payload = self.message_queue.get_nowait()
            except queue.Empty:
                break
            if message_type == "log":
                self._log(payload)
            elif message_type == "done":
                self._log(payload)
                self.start_button.config(state="normal")
                self.stop_button.config(state="disabled")
            elif message_type == "error":
                self._log(payload)
                self.start_button.config(state="normal")
                self.stop_button.config(state="disabled")
        self.root.after(150, self._drain_messages)

    def _log(self, message: str) -> None:
        self.log_text.insert(END, message.rstrip() + "\n")
        self.log_text.see(END)

    def run(self) -> None:
        self.root.mainloop()


def launch_ui() -> None:
    BotControlUi().run()
