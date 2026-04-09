from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .paths import LIVE_ACTION_MAP_PATH, LIVE_COMMAND_LOG_PATH, LIVE_SESSION_LOG_PATH, LIVE_STATE_PATH, MODEL_PATH, SCOUT_REPORT_PATH, SCREEN_PROFILE_PATH, UI_SETTINGS_PATH


@dataclass(slots=True)
class AppSettings:
    run_mode: str = "live"
    collect_episodes: int = 120
    simulate_episodes: int = 20
    steps: int = 50
    poll_interval_sec: float = 1.5
    dry_run: bool = True
    model_path: str = str(MODEL_PATH)
    live_state_path: str = str(LIVE_STATE_PATH)
    screen_profile_path: str = str(SCREEN_PROFILE_PATH)
    live_action_map_path: str = str(LIVE_ACTION_MAP_PATH)
    scout_report_path: str = str(SCOUT_REPORT_PATH)
    live_command_log_path: str = str(LIVE_COMMAND_LOG_PATH)
    live_session_log_path: str = str(LIVE_SESSION_LOG_PATH)
    game_window_title: str = "Goodgame Empire"

    def to_dict(self) -> dict:
        return asdict(self)


def load_app_settings(path: Path = UI_SETTINGS_PATH) -> AppSettings:
    if not path.exists():
        return AppSettings()
    data = json.loads(path.read_text(encoding="utf-8"))
    base = AppSettings()
    values = base.to_dict()
    values.update({key: value for key, value in data.items() if key in values})
    return AppSettings(**values)


def save_app_settings(settings: AppSettings, path: Path = UI_SETTINGS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
