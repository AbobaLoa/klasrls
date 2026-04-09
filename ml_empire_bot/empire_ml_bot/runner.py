from __future__ import annotations

import json
from uuid import uuid4

from .dataset import aggregate_sessions, append_logs_jsonl, read_logs_jsonl, write_logs_jsonl
from .mock_game import MockEmpireAdapter
from .paths import EXPORT_PATH, GENERATED_LOG_PATH, METRICS_PATH, MODEL_PATH, RAW_LOG_PATH, ensure_data_dirs
from .schemas import StepLog
from .training import load_policy, train_policy


def collect_expert_sessions(episodes: int = 100, steps_per_episode: int = 50) -> dict[str, int]:
    ensure_data_dirs()
    adapter = MockEmpireAdapter(max_steps=steps_per_episode)
    logs: list[StepLog] = []

    for _ in range(episodes):
        episode_id = str(uuid4())
        observation = adapter.reset()
        for step_index in range(steps_per_episode):
            action = adapter.expert_action(observation)
            next_observation, reward, done, info = adapter.step(action)
            logs.append(
                StepLog(
                    episode_id=episode_id,
                    step_index=step_index,
                    mode="expert",
                    observation=observation,
                    action=action,
                    reward=reward,
                    next_observation=next_observation,
                    done=done,
                    info=info,
                )
            )
            observation = next_observation
            if done:
                break

    append_logs_jsonl(RAW_LOG_PATH, logs)
    return {"episodes": episodes, "steps_logged": len(logs)}


def simulate_with_model(episodes: int = 25, steps_per_episode: int = 50) -> dict[str, int]:
    ensure_data_dirs()
    model = load_policy(MODEL_PATH)
    adapter = MockEmpireAdapter(max_steps=steps_per_episode)
    logs: list[StepLog] = []

    for _ in range(episodes):
        episode_id = str(uuid4())
        observation = adapter.reset()
        for step_index in range(steps_per_episode):
            features = [observation.to_feature_dict()]
            action = str(model.predict(features)[0])
            if action not in adapter.available_actions():
                action = "wait"
            next_observation, reward, done, info = adapter.step(action)
            logs.append(
                StepLog(
                    episode_id=episode_id,
                    step_index=step_index,
                    mode="model",
                    observation=observation,
                    action=action,
                    reward=reward,
                    next_observation=next_observation,
                    done=done,
                    info=info,
                )
            )
            observation = next_observation
            if done:
                break

    write_logs_jsonl(GENERATED_LOG_PATH, logs)
    return {"episodes": episodes, "steps_logged": len(logs)}


def export_for_calculator() -> dict:
    ensure_data_dirs()
    rows = read_logs_jsonl(GENERATED_LOG_PATH)
    if not rows:
        rows = read_logs_jsonl(RAW_LOG_PATH)
    payload = aggregate_sessions(rows)
    EXPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def run_demo_pipeline(collect_episodes: int = 120, simulate_episodes: int = 20, steps_per_episode: int = 50) -> dict:
    ensure_data_dirs()
    collected = collect_expert_sessions(episodes=collect_episodes, steps_per_episode=steps_per_episode)
    metrics = train_policy(RAW_LOG_PATH, MODEL_PATH, METRICS_PATH)
    simulated = simulate_with_model(episodes=simulate_episodes, steps_per_episode=steps_per_episode)
    exported = export_for_calculator()
    return {
        "collected": collected,
        "metrics": metrics,
        "simulated": simulated,
        "exported_sessions": exported.get("session_count") or 0,
    }
