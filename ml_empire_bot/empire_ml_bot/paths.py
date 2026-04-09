from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
MODELS_DIR = DATA_DIR / "models"
GENERATED_DIR = DATA_DIR / "generated"
EXPORTS_DIR = DATA_DIR / "exports"
LIVE_DIR = DATA_DIR / "live"
SETTINGS_DIR = DATA_DIR / "settings"

RAW_LOG_PATH = RAW_DIR / "expert_sessions.jsonl"
MODEL_PATH = MODELS_DIR / "policy.joblib"
METRICS_PATH = MODELS_DIR / "metrics.json"
GENERATED_LOG_PATH = GENERATED_DIR / "model_sessions.jsonl"
EXPORT_PATH = EXPORTS_DIR / "calculator_feed.json"
LIVE_STATE_PATH = LIVE_DIR / "live_state.json"
SCREEN_PROFILE_PATH = LIVE_DIR / "screen_profile.json"
LIVE_ACTION_MAP_PATH = LIVE_DIR / "live_action_map.json"
LIVE_COMMAND_LOG_PATH = LIVE_DIR / "command_log.jsonl"
LIVE_SESSION_LOG_PATH = LIVE_DIR / "live_sessions.jsonl"
SCOUT_REPORT_PATH = LIVE_DIR / "auto_scout_report.json"
SCOUT_SCREENSHOTS_DIR = LIVE_DIR / "auto_scout_captures"
UI_SETTINGS_PATH = SETTINGS_DIR / "ui_settings.json"


def ensure_data_dirs() -> None:
    for path in (DATA_DIR, RAW_DIR, MODELS_DIR, GENERATED_DIR, EXPORTS_DIR, LIVE_DIR, SETTINGS_DIR):
        path.mkdir(parents=True, exist_ok=True)
