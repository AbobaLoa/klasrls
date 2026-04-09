from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Any, Callable
from uuid import uuid4

from .adapters import BaseGameAdapter
from .dataset import append_logs_jsonl
from .mock_game import ALL_BUILDINGS, MockEmpireAdapter
from .paths import LIVE_ACTION_MAP_PATH, LIVE_COMMAND_LOG_PATH, LIVE_SESSION_LOG_PATH, LIVE_STATE_PATH, MODEL_PATH, ensure_data_dirs
from .schemas import Observation, StepLog
from .training import load_policy

StatusCallback = Callable[[str], None]
DEFAULT_ACTIONS = [
    "collect_food",
    "collect_wood",
    "collect_stone",
    "upgrade_farm",
    "upgrade_lumberyard",
    "upgrade_quarry",
    "build_house",
    "upgrade_academy",
    "train_soldiers",
    "wait",
]


@dataclass(slots=True)
class LiveRunConfig:
    model_path: Path = MODEL_PATH
    state_path: Path = LIVE_STATE_PATH
    action_map_path: Path = LIVE_ACTION_MAP_PATH
    command_log_path: Path = LIVE_COMMAND_LOG_PATH
    session_log_path: Path = LIVE_SESSION_LOG_PATH
    poll_interval_sec: float = 1.5
    max_steps: int = 50
    dry_run: bool = True
    game_window_title: str = "Goodgame Empire"


def _emit(status_callback: StatusCallback | None, message: str) -> None:
    if status_callback:
        status_callback(message)


def _append_command_log(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_observation(payload: dict[str, Any]) -> Observation:
    building_levels = payload.get("building_levels") if isinstance(payload.get("building_levels"), dict) else {}
    normalized_levels = {name: int(building_levels.get(name) or 0) for name in ALL_BUILDINGS}
    for name, value in building_levels.items():
        if name not in normalized_levels:
            normalized_levels[str(name)] = int(value or 0)
    return Observation(
        castle_name=str(payload.get("castle_name") or "Основной замок"),
        food=int(payload.get("food") or 0),
        wood=int(payload.get("wood") or 0),
        stone=int(payload.get("stone") or 0),
        public_order=int(payload.get("public_order") or 0),
        free_tiles=int(payload.get("free_tiles") or 0),
        building_levels=normalized_levels,
    )


def _estimate_reward(before: Observation, after: Observation) -> float:
    reward = 0.0
    reward += (after.food - before.food) * 0.01
    reward += (after.wood - before.wood) * 0.01
    reward += (after.stone - before.stone) * 0.01
    reward += (after.public_order - before.public_order) * 0.03
    reward += (after.free_tiles - before.free_tiles) * -0.05
    for name, level in after.building_levels.items():
        reward += max(0, level - int(before.building_levels.get(name) or 0)) * 5.0
    return round(reward, 4)


class LiveEmpireAdapter(BaseGameAdapter):
    def __init__(self, config: LiveRunConfig, status_callback: StatusCallback | None = None):
        self.config = config
        self.status_callback = status_callback
        self.step_counter = 0
        self._expert_helper = MockEmpireAdapter()

    def reset(self) -> Observation:
        self.step_counter = 0
        observation = self._read_observation()
        _emit(self.status_callback, f"Считано live-состояние: {observation.castle_name}")
        return observation

    def available_actions(self) -> list[str]:
        return list(DEFAULT_ACTIONS)

    def expert_action(self, observation: Observation) -> str:
        return self._expert_helper.expert_action(observation)

    def step(self, action: str) -> tuple[Observation, float, bool, dict[str, Any]]:
        self.step_counter += 1
        before = self._read_observation()
        execution_info = self._execute_action(action)
        time.sleep(max(0.0, self.config.poll_interval_sec))
        after = self._read_observation()
        reward = _estimate_reward(before, after)
        done = self.step_counter >= self.config.max_steps
        info = {
            "executed_action": action,
            "dry_run": self.config.dry_run,
            "window_title": self.config.game_window_title,
            **execution_info,
        }
        return after, reward, done, info

    def _read_observation(self) -> Observation:
        if not self.config.state_path.exists():
            raise FileNotFoundError(
                f"Не найден live state файл: {self.config.state_path}. Заполни его или подключи реальный reader."
            )
        payload = _load_json(self.config.state_path, {})
        if not isinstance(payload, dict):
            raise ValueError(f"Некорректный формат live state: {self.config.state_path}")
        return _normalize_observation(payload)

    def _execute_action(self, action: str) -> dict[str, Any]:
        action_map = _load_json(self.config.action_map_path, {})
        command = action_map.get(action) if isinstance(action_map, dict) else None
        command_payload = {
            "timestamp": time.time(),
            "action": action,
            "dry_run": self.config.dry_run,
            "window_title": self.config.game_window_title,
            "command": command or {},
        }
        _append_command_log(self.config.command_log_path, command_payload)

        if self.config.dry_run:
            _emit(self.status_callback, f"DRY-RUN: {action}")
            return {"status": "planned", "command_found": bool(command)}

        if not command:
            _emit(self.status_callback, f"Нет action map для действия: {action}")
            return {"status": "missing_mapping", "command_found": False}

        try:
            import pyautogui
        except Exception as exc:
            _emit(self.status_callback, f"PyAutoGUI недоступен: {exc}")
            return {"status": "pyautogui_unavailable", "command_found": True}

        command_type = str(command.get("type") or "click")
        pause_after = float(command.get("pause_after") or 0.5)
        if command_type == "click":
            pyautogui.click(x=int(command.get("x") or 0), y=int(command.get("y") or 0))
        elif command_type == "double_click":
            pyautogui.doubleClick(x=int(command.get("x") or 0), y=int(command.get("y") or 0))
        elif command_type == "hotkey":
            keys = command.get("keys") or []
            if not isinstance(keys, list) or not keys:
                return {"status": "invalid_hotkey", "command_found": True}
            pyautogui.hotkey(*[str(key) for key in keys])
        elif command_type == "press":
            pyautogui.press(str(command.get("key") or "space"))
        elif command_type == "write":
            pyautogui.write(str(command.get("text") or ""), interval=float(command.get("interval") or 0.02))
        else:
            return {"status": "unsupported_command_type", "command_found": True, "command_type": command_type}
        time.sleep(max(0.0, pause_after))
        _emit(self.status_callback, f"Выполнено действие: {action}")
        return {"status": "executed", "command_found": True, "command_type": command_type}


def run_live_bot(config: LiveRunConfig, status_callback: StatusCallback | None = None, stop_event: Event | None = None) -> dict[str, Any]:
    ensure_data_dirs()
    model = load_policy(config.model_path)
    adapter = LiveEmpireAdapter(config=config, status_callback=status_callback)
    episode_id = str(uuid4())
    observation = adapter.reset()
    step_logs: list[StepLog] = []

    _emit(status_callback, f"Live-бот запущен. Режим dry-run={config.dry_run}")
    for step_index in range(config.max_steps):
        if stop_event and stop_event.is_set():
            _emit(status_callback, "Получен сигнал остановки")
            break
        action = str(model.predict([observation.to_feature_dict()])[0])
        if action not in adapter.available_actions():
            action = "wait"
        _emit(status_callback, f"Шаг {step_index + 1}/{config.max_steps}: выбрано действие {action}")
        next_observation, reward, done, info = adapter.step(action)
        record = StepLog(
            episode_id=episode_id,
            step_index=step_index,
            mode="live",
            observation=observation,
            action=action,
            reward=reward,
            next_observation=next_observation,
            done=done,
            info=info,
        )
        step_logs.append(record)
        append_logs_jsonl(config.session_log_path, [record])
        observation = next_observation
        if done:
            break

    _emit(status_callback, f"Live-сессия завершена. Логов записано: {len(step_logs)}")
    return {
        "mode": "live",
        "steps_logged": len(step_logs),
        "dry_run": config.dry_run,
        "session_log_path": str(config.session_log_path),
        "command_log_path": str(config.command_log_path),
        "state_path": str(config.state_path),
    }
