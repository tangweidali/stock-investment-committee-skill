#!/usr/bin/env python3
"""Update stock investment committee role weights from a prediction and outcome."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_ROLES = [
    "fundamental_analyst",
    "technical_analyst",
    "macro_strategist",
    "risk_manager",
    "short_seller",
    "value_investor",
    "wall_street_trader",
    "bank_executive",
    "finance_professor",
    "strategic_investor",
    "sector_specialist",
    "retail_sentiment_observer",
]

DIRECTION_MAP = {
    "bullish": "up",
    "neutral-bullish": "up",
    "up": "up",
    "outperform": "up",
    "buy": "up",
    "overweight": "up",
    "bearish": "down",
    "neutral-bearish": "down",
    "down": "down",
    "underperform": "down",
    "sell": "down",
    "short": "down",
    "underweight": "down",
    "neutral": "flat",
    "flat": "flat",
    "inline": "flat",
    "hold": "flat",
    "market-perform": "flat",
    "conditional-hold": "flat",
    "cautious-hold": "flat",
}


def load_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower().replace("_", "-")
    return DIRECTION_MAP.get(text, text if text in {"up", "down", "flat"} else None)


def confidence_factor(confidence: Any) -> float:
    try:
        value = float(confidence)
    except (TypeError, ValueError):
        value = 70.0
    return max(0.5, min(1.5, value / 70.0))


def initial_weights() -> dict[str, float]:
    return {role: 1.0 for role in DEFAULT_ROLES}


def initial_neutral_streaks() -> dict[str, int]:
    return {role: 0 for role in DEFAULT_ROLES}


def role_prediction(role_data: dict[str, Any]) -> str | None:
    return normalize(
        role_data.get("expected_direction")
        or role_data.get("prediction")
        or role_data.get("stance")
        or role_data.get("advice")
    )


def extract_numeric_roles(source: dict[str, Any]) -> dict[str, float]:
    return {k: float(v) for k, v in source.items() if isinstance(v, (int, float))}


def update_weights(weights: dict[str, Any], prediction: dict[str, Any], outcome: dict[str, Any]) -> dict[str, Any]:
    settings = weights.get("settings", {}) if isinstance(weights.get("settings"), dict) else {}
    learning_rate = float(settings.get("learning_rate", prediction.get("learning_rate", 0.08)))
    min_weight = float(settings.get("min_weight", prediction.get("min_weight", 0.40)))
    max_weight = float(settings.get("max_weight", prediction.get("max_weight", 2.50)))
    neutral_penalty_rate = float(settings.get("neutral_penalty_rate", prediction.get("neutral_penalty_rate", 0.05)))
    neutral_penalty_after = int(settings.get("neutral_penalty_after", prediction.get("neutral_penalty_after", 3)))

    current = initial_weights()
    raw_roles = weights.get("roles", weights)
    if isinstance(raw_roles, dict):
        current.update(extract_numeric_roles(raw_roles))

    neutral_streaks = initial_neutral_streaks()
    raw_streaks = weights.get("neutral_streaks", {})
    if isinstance(raw_streaks, dict):
        neutral_streaks.update({k: int(v) for k, v in raw_streaks.items() if isinstance(v, (int, float))})

    actual = normalize(outcome.get("actual") or outcome.get("direction") or outcome.get("result"))
    if actual is None:
        raise ValueError("Outcome must include actual direction: up/down/flat, outperform/inline/underperform, or equivalent.")

    roles = prediction.get("roles", {})
    evaluated: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    for role_id, role_data in roles.items():
        if not isinstance(role_data, dict):
            skipped.append({"role": role_id, "reason": "role prediction is not an object"})
            continue
        predicted = role_prediction(role_data)
        if predicted is None:
            skipped.append({"role": role_id, "reason": "prediction is missing or too vague"})
            continue
        evaluated.append(
            {
                "role": role_id,
                "predicted": predicted,
                "actual": actual,
                "correct": predicted == actual,
                "confidence": role_data.get("confidence", 70),
                "old_weight": current.get(role_id, 1.0),
                "old_neutral_streak": neutral_streaks.get(role_id, 0),
            }
        )

    if not evaluated:
        raise ValueError("No roles could be evaluated.")

    correct_count = sum(1 for item in evaluated if item["correct"])
    all_correct = correct_count == len(evaluated)
    all_wrong = correct_count == 0

    updated = dict(current)
    neutral_penalties: list[dict[str, Any]] = []

    if not all_correct and not all_wrong:
        for item in evaluated:
            factor = confidence_factor(item["confidence"])
            old = item["old_weight"]
            if item["correct"]:
                new = min(max_weight, old * (1 + learning_rate * factor))
            else:
                new = max(min_weight, old * (1 - learning_rate * factor))
            updated[item["role"]] = round(new, 3)

    for item in evaluated:
        role_id = item["role"]
        if item["predicted"] == "flat":
            neutral_streaks[role_id] = neutral_streaks.get(role_id, 0) + 1
        else:
            neutral_streaks[role_id] = 0

    for role_id, streak in neutral_streaks.items():
        if streak >= neutral_penalty_after and role_id in updated:
            old = updated[role_id]
            new = max(min_weight, old * (1 - neutral_penalty_rate))
            updated[role_id] = round(new, 3)
            neutral_penalties.append(
                {
                    "role": role_id,
                    "neutral_streak": streak,
                    "old_weight_after_accuracy_update": old,
                    "new_weight": updated[role_id],
                    "penalty_rate": neutral_penalty_rate,
                }
            )

    for item in evaluated:
        item["new_weight"] = updated.get(item["role"], item["old_weight"])
        item["new_neutral_streak"] = neutral_streaks.get(item["role"], 0)
        item["changed"] = item["new_weight"] != item["old_weight"]

    return {
        "settings": {
            "learning_rate": learning_rate,
            "min_weight": min_weight,
            "max_weight": max_weight,
            "neutral_penalty_after": neutral_penalty_after,
            "neutral_penalty_rate": neutral_penalty_rate,
        },
        "roles": updated,
        "neutral_streaks": neutral_streaks,
        "last_update": {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "ticker": prediction.get("ticker") or outcome.get("ticker"),
            "market": prediction.get("market") or outcome.get("market"),
            "horizon": prediction.get("horizon") or outcome.get("horizon"),
            "metric": outcome.get("metric") or prediction.get("prediction_metric"),
            "actual": actual,
            "all_correct": all_correct,
            "all_wrong": all_wrong,
            "evaluated": evaluated,
            "neutral_penalties": neutral_penalties,
            "skipped": skipped,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Update stock committee role weights.")
    parser.add_argument("--weights", required=True, help="Existing weights JSON file. Created with defaults if missing.")
    parser.add_argument("--prediction", required=True, help="Prediction record JSON file.")
    parser.add_argument("--outcome", required=True, help="Actual outcome JSON file.")
    parser.add_argument("--output", required=True, help="Output weights JSON file.")
    args = parser.parse_args()

    weights_path = Path(args.weights)
    prediction = load_json(Path(args.prediction))
    outcome = load_json(Path(args.outcome))
    weights = load_json(
        weights_path,
        {
            "roles": initial_weights(),
            "neutral_streaks": initial_neutral_streaks(),
            "settings": {
                "learning_rate": 0.08,
                "min_weight": 0.40,
                "max_weight": 2.50,
                "neutral_penalty_after": 3,
                "neutral_penalty_rate": 0.05,
            },
        },
    )

    result = update_weights(weights, prediction, outcome)
    output_path = Path(args.output)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = result["last_update"]
    print(f"Updated weights for {summary.get('ticker') or 'unknown ticker'}")
    if summary["all_correct"]:
        print("All evaluated roles were correct; accuracy weights unchanged.")
    elif summary["all_wrong"]:
        print("All evaluated roles were wrong; accuracy weights unchanged.")
    else:
        print("Accuracy weights changed for differentiated correct/incorrect roles.")
    if summary["neutral_penalties"]:
        print("Neutral-streak penalties applied.")
    print(json.dumps(summary["evaluated"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
