from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Any, Callable

from .calibration import load_screen_profile
from .paths import SCOUT_REPORT_PATH, SCOUT_SCREENSHOTS_DIR, SCREEN_PROFILE_PATH, ensure_data_dirs

StatusCallback = Callable[[str], None]


@dataclass(slots=True)
class AutoScoutConfig:
    profile_path: Path = SCREEN_PROFILE_PATH
    report_path: Path = SCOUT_REPORT_PATH
    screenshot_dir: Path = SCOUT_SCREENSHOTS_DIR
    max_steps: int = 30
    grid_step: int = 96
    settle_delay_sec: float = 1.2
    change_threshold: float = 4.0
    dry_run: bool = True
    game_window_title: str = "Goodgame Empire"


def _emit(status_callback: StatusCallback | None, message: str) -> None:
    if status_callback:
        status_callback(message)


def _screen_bounds(image) -> tuple[int, int]:
    return int(image.size[0]), int(image.size[1])


def _build_search_bounds(profile: dict[str, Any], screen_width: int, screen_height: int) -> tuple[int, int, int, int]:
    targets = profile.get("targets") if isinstance(profile.get("targets"), dict) else {}
    region_points: list[tuple[int, int]] = []
    for item in targets.values():
        if not isinstance(item, dict) or item.get("type") != "region":
            continue
        region_points.append((int(item.get("x1") or 0), int(item.get("y1") or 0)))
        region_points.append((int(item.get("x2") or 0), int(item.get("y2") or 0)))
    if region_points:
        xs = [point[0] for point in region_points]
        ys = [point[1] for point in region_points]
        left = max(0, min(xs) - 24)
        top = max(0, min(ys) - 24)
        right = min(screen_width, max(xs) + 24)
        bottom = min(screen_height, max(ys) + 24)
        if right - left >= 120 and bottom - top >= 120:
            return left, top, right, bottom
    margin_x = max(24, int(screen_width * 0.05))
    margin_y = max(24, int(screen_height * 0.05))
    return margin_x, margin_y, max(margin_x + 1, screen_width - margin_x), max(margin_y + 1, screen_height - margin_y)


def _generate_candidates(image, profile: dict[str, Any], grid_step: int, max_steps: int) -> list[dict[str, Any]]:
    from PIL import ImageStat

    width, height = _screen_bounds(image)
    left, top, right, bottom = _build_search_bounds(profile, width, height)
    step = max(24, int(grid_step))
    half = max(8, min(20, step // 4))
    candidates: list[dict[str, Any]] = []

    for y in range(top, bottom, step):
        for x in range(left, right, step):
            crop = image.crop((max(0, x - half), max(0, y - half), min(width, x + half), min(height, y + half))).convert("L")
            stat = ImageStat.Stat(crop)
            score = float(stat.var[0]) if stat.var else 0.0
            candidates.append({"x": x, "y": y, "visual_score": round(score, 4)})

    candidates.sort(key=lambda item: item["visual_score"], reverse=True)
    return candidates[: max(1, max_steps)]


def _image_change_score(before_image, after_image) -> float:
    from PIL import ImageChops, ImageStat

    diff = ImageChops.difference(before_image.convert("RGB"), after_image.convert("RGB"))
    stat = ImageStat.Stat(diff)
    if not stat.mean:
        return 0.0
    return round(sum(float(value) for value in stat.mean) / len(stat.mean), 4)


def _save_image(image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _load_runtime_dependencies():
    import pyautogui

    return pyautogui


def run_auto_scout(
    config: AutoScoutConfig,
    status_callback: StatusCallback | None = None,
    stop_event: Event | None = None,
) -> dict[str, Any]:
    ensure_data_dirs()
    pyautogui = _load_runtime_dependencies()
    profile = load_screen_profile(config.profile_path)
    baseline = pyautogui.screenshot()
    width, height = _screen_bounds(baseline)
    candidates = _generate_candidates(
        image=baseline,
        profile=profile,
        grid_step=config.grid_step,
        max_steps=config.max_steps,
    )
    report: dict[str, Any] = {
        "mode": "scout",
        "window_title": config.game_window_title,
        "dry_run": config.dry_run,
        "screen_size": {"width": width, "height": height},
        "search_bounds": {},
        "steps": [],
        "interactive_points": [],
    }
    left, top, right, bottom = _build_search_bounds(profile, width, height)
    report["search_bounds"] = {"left": left, "top": top, "right": right, "bottom": bottom}

    screenshot_dir = config.screenshot_dir
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    baseline_path = screenshot_dir / "scout_baseline.png"
    _save_image(baseline, baseline_path)
    _emit(status_callback, f"Auto-scout стартовал. Кандидатов: {len(candidates)}")

    for index, candidate in enumerate(candidates, start=1):
        if stop_event and stop_event.is_set():
            _emit(status_callback, "Auto-scout остановлен пользователем")
            break

        step_record: dict[str, Any] = {
            "index": index,
            "x": int(candidate["x"]),
            "y": int(candidate["y"]),
            "visual_score": float(candidate["visual_score"]),
            "dry_run": config.dry_run,
        }
        _emit(status_callback, f"Scout {index}/{len(candidates)}: ({step_record['x']}, {step_record['y']})")

        if config.dry_run:
            step_record["change_score"] = 0.0
            step_record["interactive"] = False
            step_record["status"] = "planned"
            report["steps"].append(step_record)
            continue

        before_image = pyautogui.screenshot()
        pyautogui.click(x=step_record["x"], y=step_record["y"])
        time.sleep(max(0.2, config.settle_delay_sec))
        after_image = pyautogui.screenshot()
        change_score = _image_change_score(before_image, after_image)
        interactive = change_score >= config.change_threshold
        step_record["change_score"] = change_score
        step_record["interactive"] = interactive
        step_record["status"] = "changed" if interactive else "no_change"

        before_path = screenshot_dir / f"scout_{index:03d}_before.png"
        after_path = screenshot_dir / f"scout_{index:03d}_after.png"
        _save_image(before_image, before_path)
        _save_image(after_image, after_path)
        step_record["before_image"] = str(before_path)
        step_record["after_image"] = str(after_path)

        if interactive:
            report["interactive_points"].append(
                {
                    "x": step_record["x"],
                    "y": step_record["y"],
                    "change_score": change_score,
                    "visual_score": step_record["visual_score"],
                }
            )
        report["steps"].append(step_record)

    config.report_path.parent.mkdir(parents=True, exist_ok=True)
    config.report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _emit(status_callback, f"Auto-scout завершён. Интерактивных точек: {len(report['interactive_points'])}")
    return {
        "mode": "scout",
        "dry_run": config.dry_run,
        "steps_logged": len(report["steps"]),
        "interactive_points": len(report["interactive_points"]),
        "report_path": str(config.report_path),
        "screenshot_dir": str(screenshot_dir),
    }
