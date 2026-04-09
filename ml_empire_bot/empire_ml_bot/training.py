from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from .dataset import build_training_rows, read_logs_jsonl


def train_policy(log_path: Path, model_path: Path, metrics_path: Path) -> dict[str, Any]:
    rows = read_logs_jsonl(log_path)
    if not rows:
        raise FileNotFoundError(f"Нет логов для обучения: {log_path}")

    features, labels = build_training_rows(rows)
    if len(features) < 10:
        raise ValueError("Недостаточно данных для обучения. Нужны хотя бы 10 шагов.")

    model = Pipeline(
        steps=[
            ("vectorizer", DictVectorizer(sparse=False)),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=220,
                    random_state=42,
                    class_weight="balanced_subsample",
                ),
            ),
        ]
    )

    x_train, x_test, y_train, y_test = train_test_split(
        features,
        labels,
        test_size=0.2,
        random_state=42,
        stratify=labels if len(set(labels)) > 1 else None,
    )
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    accuracy = float(accuracy_score(y_test, predictions))
    report = classification_report(y_test, predictions, output_dict=True, zero_division=0)

    model_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)

    metrics = {
        "rows": len(rows),
        "train_samples": len(x_train),
        "test_samples": len(x_test),
        "accuracy": accuracy,
        "labels": sorted(set(labels)),
        "report": report,
    }
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return metrics


def load_policy(model_path: Path):
    if not model_path.exists():
        raise FileNotFoundError(f"Модель не найдена: {model_path}")
    return joblib.load(model_path)
