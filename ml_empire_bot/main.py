from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_ml_bot.paths import LIVE_ACTION_MAP_PATH, LIVE_COMMAND_LOG_PATH, LIVE_SESSION_LOG_PATH, LIVE_STATE_PATH, METRICS_PATH, MODEL_PATH, RAW_LOG_PATH, SCOUT_REPORT_PATH, SCREEN_PROFILE_PATH


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Empire ML bot MVP")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser("collect", help="Собрать экспертные сессии")
    collect_parser.add_argument("--episodes", type=int, default=100)
    collect_parser.add_argument("--steps", type=int, default=50)

    train_parser = subparsers.add_parser("train", help="Обучить модель по логам")
    train_parser.add_argument("--log-path", type=str, default=str(RAW_LOG_PATH))
    train_parser.add_argument("--model-path", type=str, default=str(MODEL_PATH))
    train_parser.add_argument("--metrics-path", type=str, default=str(METRICS_PATH))

    simulate_parser = subparsers.add_parser("simulate", help="Запустить симуляцию обученной моделью")
    simulate_parser.add_argument("--episodes", type=int, default=25)
    simulate_parser.add_argument("--steps", type=int, default=50)

    live_parser = subparsers.add_parser("live", help="Запустить live-бота")
    live_parser.add_argument("--steps", type=int, default=50)
    live_parser.add_argument("--poll-interval", type=float, default=1.5)
    live_parser.add_argument("--model-path", type=str, default=str(MODEL_PATH))
    live_parser.add_argument("--state-path", type=str, default=str(LIVE_STATE_PATH))
    live_parser.add_argument("--action-map-path", type=str, default=str(LIVE_ACTION_MAP_PATH))
    live_parser.add_argument("--command-log-path", type=str, default=str(LIVE_COMMAND_LOG_PATH))
    live_parser.add_argument("--session-log-path", type=str, default=str(LIVE_SESSION_LOG_PATH))
    live_parser.add_argument("--window-title", type=str, default="Goodgame Empire")
    live_parser.add_argument("--real-run", action="store_true")

    calibrate_parser = subparsers.add_parser("calibrate", help="Открыть UI калибровки экрана")
    calibrate_parser.add_argument("--profile-path", type=str, default=str(SCREEN_PROFILE_PATH))
    calibrate_parser.add_argument("--action-map-path", type=str, default=str(LIVE_ACTION_MAP_PATH))
    calibrate_parser.add_argument("--image-path", type=str, default="")

    scout_parser = subparsers.add_parser("scout", help="Автоматически искать интерактивные точки на экране")
    scout_parser.add_argument("--steps", type=int, default=30)
    scout_parser.add_argument("--profile-path", type=str, default=str(SCREEN_PROFILE_PATH))
    scout_parser.add_argument("--report-path", type=str, default=str(SCOUT_REPORT_PATH))
    scout_parser.add_argument("--grid-step", type=int, default=96)
    scout_parser.add_argument("--settle-delay", type=float, default=1.2)
    scout_parser.add_argument("--change-threshold", type=float, default=4.0)
    scout_parser.add_argument("--window-title", type=str, default="Goodgame Empire")
    scout_parser.add_argument("--real-run", action="store_true")

    auto_parser = subparsers.add_parser("auto", help="Автономный режим: сам кликает и обучается интерактивным точкам")
    auto_parser.add_argument("--steps", type=int, default=60)
    auto_parser.add_argument("--profile-path", type=str, default=str(SCREEN_PROFILE_PATH))
    auto_parser.add_argument("--report-path", type=str, default=str(SCOUT_REPORT_PATH))
    auto_parser.add_argument("--grid-step", type=int, default=96)
    auto_parser.add_argument("--settle-delay", type=float, default=1.2)
    auto_parser.add_argument("--change-threshold", type=float, default=4.0)
    auto_parser.add_argument("--window-title", type=str, default="Goodgame Empire")
    auto_parser.add_argument("--real-run", action="store_true")

    subparsers.add_parser("ui", help="Открыть desktop UI")

    subparsers.add_parser("export", help="Собрать экспорт для калькулятора")

    demo_parser = subparsers.add_parser("demo", help="Прогнать весь pipeline")
    demo_parser.add_argument("--collect-episodes", type=int, default=120)
    demo_parser.add_argument("--simulate-episodes", type=int, default=20)
    demo_parser.add_argument("--steps", type=int, default=50)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "collect":
        from empire_ml_bot.runner import collect_expert_sessions

        result = collect_expert_sessions(episodes=args.episodes, steps_per_episode=args.steps)
    elif args.command == "train":
        from empire_ml_bot.training import train_policy

        result = train_policy(Path(args.log_path), Path(args.model_path), Path(args.metrics_path))
    elif args.command == "simulate":
        from empire_ml_bot.runner import simulate_with_model

        result = simulate_with_model(episodes=args.episodes, steps_per_episode=args.steps)
    elif args.command == "live":
        from empire_ml_bot.live_bot import LiveRunConfig, run_live_bot

        result = run_live_bot(
            LiveRunConfig(
                model_path=Path(args.model_path),
                state_path=Path(args.state_path),
                action_map_path=Path(args.action_map_path),
                command_log_path=Path(args.command_log_path),
                session_log_path=Path(args.session_log_path),
                poll_interval_sec=args.poll_interval,
                max_steps=args.steps,
                dry_run=not bool(args.real_run),
                game_window_title=args.window_title,
            )
        )
    elif args.command == "ui":
        from empire_ml_bot.ui import launch_ui

        launch_ui()
        return
    elif args.command == "calibrate":
        from empire_ml_bot.calibration import launch_calibration_ui

        launch_calibration_ui(
            profile_path=Path(args.profile_path),
            action_map_path=Path(args.action_map_path),
            initial_image_path=args.image_path,
        )
        return
    elif args.command == "scout":
        from empire_ml_bot.auto_scout import AutoScoutConfig, run_auto_scout

        result = run_auto_scout(
            AutoScoutConfig(
                profile_path=Path(args.profile_path),
                report_path=Path(args.report_path),
                max_steps=args.steps,
                grid_step=args.grid_step,
                settle_delay_sec=args.settle_delay,
                change_threshold=args.change_threshold,
                dry_run=not bool(args.real_run),
                game_window_title=args.window_title,
            )
        )
    elif args.command == "auto":
        from empire_ml_bot.auto_scout import AutoPilotConfig, run_auto_pilot

        result = run_auto_pilot(
            AutoPilotConfig(
                profile_path=Path(args.profile_path),
                report_path=Path(args.report_path),
                max_steps=args.steps,
                grid_step=args.grid_step,
                settle_delay_sec=args.settle_delay,
                change_threshold=args.change_threshold,
                dry_run=not bool(args.real_run),
                game_window_title=args.window_title,
            )
        )
    elif args.command == "export":
        from empire_ml_bot.runner import export_for_calculator

        result = export_for_calculator()
    elif args.command == "demo":
        from empire_ml_bot.runner import run_demo_pipeline

        result = run_demo_pipeline(
            collect_episodes=args.collect_episodes,
            simulate_episodes=args.simulate_episodes,
            steps_per_episode=args.steps,
        )
    else:
        parser.error("Неизвестная команда")
        return

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
