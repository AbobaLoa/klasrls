from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import StepLog


def append_logs_jsonl(path: Path, logs: list[StepLog]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for item in logs:
            handle.write(json.dumps(item.to_dict(), ensure_ascii=False) + "\n")


def write_logs_jsonl(path: Path, logs: list[StepLog]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for item in logs:
            handle.write(json.dumps(item.to_dict(), ensure_ascii=False) + "\n")


def read_logs_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def build_training_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    features: list[dict[str, Any]] = []
    labels: list[str] = []
    for row in rows:
        observation = row.get("observation") or {}
        building_levels = observation.get("building_levels") or {}
        feature_row: dict[str, Any] = {
            "castle_name": observation.get("castle_name") or "main",
            "food": int(observation.get("food") or 0),
            "wood": int(observation.get("wood") or 0),
            "stone": int(observation.get("stone") or 0),
            "public_order": int(observation.get("public_order") or 0),
            "free_tiles": int(observation.get("free_tiles") or 0),
        }
        for name, level in sorted(building_levels.items()):
            feature_row[f"building_{name}"] = int(level or 0)
        action = str(row.get("action") or "wait").strip() or "wait"
        features.append(feature_row)
        labels.append(action)
    return features, labels


def aggregate_sessions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    sessions: dict[str, dict[str, Any]] = {}
    for row in rows:
        episode_id = str(row.get("episode_id") or "unknown")
        info = row.get("info") or {}
        observation = row.get("observation") or {}
        next_observation = row.get("next_observation") or {}
        session = sessions.setdefault(
            episode_id,
            {
                "episode_id": episode_id,
                "mode": row.get("mode") or "unknown",
                "steps": [],
                "resources": {"food": 0, "wood": 0, "stone": 0},
                "final_building_levels": {},
                "action_counts": {},
                "total_reward": 0.0,
            },
        )
        action = str(row.get("action") or "wait")
        session["steps"].append(
            {
                "step_index": int(row.get("step_index") or 0),
                "action": action,
                "reward": float(row.get("reward") or 0.0),
                "resources_after": {
                    "food": int(next_observation.get("food") or 0),
                    "wood": int(next_observation.get("wood") or 0),
                    "stone": int(next_observation.get("stone") or 0),
                },
                "upgraded_building": info.get("upgraded_building") or "",
                "resource_delta": info.get("resource_delta") or {},
            }
        )
        session["resources"] = {
            "food": int(next_observation.get("food") or observation.get("food") or 0),
            "wood": int(next_observation.get("wood") or observation.get("wood") or 0),
            "stone": int(next_observation.get("stone") or observation.get("stone") or 0),
        }
        session["final_building_levels"] = dict(next_observation.get("building_levels") or {})
        session["action_counts"][action] = int(session["action_counts"].get(action) or 0) + 1
        session["total_reward"] += float(row.get("reward") or 0.0)

    payload = {
        "session_count": len(sessions),
        "sessions": sorted(sessions.values(), key=lambda item: item["episode_id"]),
    }
    return payload
