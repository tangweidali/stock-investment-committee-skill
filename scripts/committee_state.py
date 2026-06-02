#!/usr/bin/env python3
"""Persist committee role state across sessions."""

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

STANCE_BUCKETS = ["bullish", "neutral_bullish", "neutral", "neutral_bearish", "bearish", "unknown"]
DIRECTION_BUCKETS = ["up", "flat", "down", "unknown"]

DIRECTION_MAP = {
    "bullish": "up",
    "neutral-bullish": "up",
    "neutral_bullish": "up",
    "up": "up",
    "flat-to-up": "up",
    "flat_to_up": "up",
    "up-if-support-holds": "up",
    "up_if_support_holds": "up",
    "up-if-80k-breaks": "up",
    "up_if_80k_breaks": "up",
    "outperform": "up",
    "buy": "up",
    "overweight": "up",
    "bearish": "down",
    "neutral-bearish": "down",
    "neutral_bearish": "down",
    "down": "down",
    "down-if-75k-breaks": "down",
    "down_if_75k_breaks": "down",
    "underperform": "down",
    "sell": "down",
    "short": "down",
    "underweight": "down",
    "neutral": "flat",
    "flat": "flat",
    "inline": "flat",
    "hold": "flat",
    "market-perform": "flat",
    "market_perform": "flat",
    "conditional-hold": "flat",
    "conditional_hold": "flat",
    "cautious-hold": "flat",
    "cautious_hold": "flat",
}

STANCE_MAP = {
    "bullish": "bullish",
    "buy": "bullish",
    "overweight": "bullish",
    "neutral-bullish": "neutral_bullish",
    "neutral_bullish": "neutral_bullish",
    "neutral": "neutral",
    "flat": "neutral",
    "inline": "neutral",
    "hold": "neutral",
    "conditional-hold": "neutral",
    "conditional_hold": "neutral",
    "cautious-hold": "neutral",
    "cautious_hold": "neutral",
    "neutral-bearish": "neutral_bearish",
    "neutral_bearish": "neutral_bearish",
    "bearish": "bearish",
    "sell": "bearish",
    "short": "bearish",
    "underweight": "bearish",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).strip().lower().replace("_", "-")


def normalize_direction(value: Any) -> str:
    text = normalize_text(value)
    if not text:
        return "unknown"
    return DIRECTION_MAP.get(text, text if text in {"up", "flat", "down"} else "unknown")


def normalize_stance(value: Any) -> str:
    text = normalize_text(value)
    if not text:
        return "unknown"
    return STANCE_MAP.get(text, "unknown")


def role_prediction(role_data: dict[str, Any]) -> str:
    return normalize_direction(
        role_data.get("expected_direction")
        or role_data.get("prediction")
        or role_data.get("stance")
        or role_data.get("advice")
    )


def role_stance(role_data: dict[str, Any]) -> str:
    return normalize_stance(role_data.get("stance") or role_data.get("advice") or role_data.get("prediction"))


def confidence_factor(confidence: Any) -> float:
    try:
        value = float(confidence)
    except (TypeError, ValueError):
        value = 70.0
    return max(0.5, min(1.5, value / 70.0))


def default_settings() -> dict[str, Any]:
    return {
        "learning_rate": 0.08,
        "min_weight": 0.40,
        "max_weight": 2.50,
        "neutral_penalty_after": 3,
        "neutral_penalty_rate": 0.05,
        "kill_weight_below": 0.40,
    }


def new_role_state(role_id: str) -> dict[str, Any]:
    return {
        "role": role_id,
        "status": "active",
        "weight": 1.0,
        "neutral_streak": 0,
        "stance_counts": {bucket: 0 for bucket in STANCE_BUCKETS},
        "direction_counts": {bucket: 0 for bucket in DIRECTION_BUCKETS},
        "prediction_count": 0,
        "outcome_count": 0,
        "correct_count": 0,
        "incorrect_count": 0,
        "last_prediction": None,
        "last_outcome": None,
        "replacement": None,
    }


def default_state() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "settings": default_settings(),
        "roles": {role: new_role_state(role) for role in DEFAULT_ROLES},
        "history": [],
    }


def ensure_state(raw: dict[str, Any] | None) -> dict[str, Any]:
    state = raw if isinstance(raw, dict) else default_state()
    state.setdefault("schema_version", 1)
    settings = default_settings()
    settings.update(state.get("settings", {}) if isinstance(state.get("settings"), dict) else {})
    state["settings"] = settings
    roles = state.get("roles") if isinstance(state.get("roles"), dict) else {}
    for role in DEFAULT_ROLES:
        current = roles.get(role)
        if not isinstance(current, dict):
            roles[role] = new_role_state(role)
            continue
        baseline = new_role_state(role)
        baseline.update(current)
        baseline["stance_counts"] = {**new_role_state(role)["stance_counts"], **current.get("stance_counts", {})}
        baseline["direction_counts"] = {**new_role_state(role)["direction_counts"], **current.get("direction_counts", {})}
        roles[role] = baseline
    state["roles"] = roles
    state.setdefault("history", [])
    return state


def load_state(path: Path) -> dict[str, Any]:
    return ensure_state(load_json(path, default_state()))


def mark_low_weight_roles(state: dict[str, Any]) -> list[dict[str, Any]]:
    threshold = float(state["settings"].get("kill_weight_below", state["settings"].get("min_weight", 0.4)))
    marked = []
    for role_id, role in state["roles"].items():
        if float(role.get("weight", 1.0)) <= threshold and role.get("status") == "active":
            role["status"] = "replacement_candidate"
            marked.append({"role": role_id, "weight": role.get("weight"), "threshold": threshold})
    return marked


def record_prediction(state: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    settings = state["settings"]
    neutral_penalty_after = int(settings["neutral_penalty_after"])
    neutral_penalty_rate = float(settings["neutral_penalty_rate"])
    min_weight = float(settings["min_weight"])
    roles = prediction.get("roles", {})
    if not isinstance(roles, dict) or not roles:
        raise ValueError("Prediction must contain roles.")

    changed_roles = []
    neutral_penalties = []
    for role_id, role_data in roles.items():
        if not isinstance(role_data, dict):
            continue
        role = state["roles"].setdefault(role_id, new_role_state(role_id))
        stance = role_stance(role_data)
        direction = role_prediction(role_data)
        role["stance_counts"][stance] = role["stance_counts"].get(stance, 0) + 1
        role["direction_counts"][direction] = role["direction_counts"].get(direction, 0) + 1
        role["prediction_count"] = int(role.get("prediction_count", 0)) + 1
        if direction == "flat":
            role["neutral_streak"] = int(role.get("neutral_streak", 0)) + 1
        elif direction in {"up", "down"}:
            role["neutral_streak"] = 0
        role["last_prediction"] = {
            "ticker": prediction.get("ticker"),
            "market": prediction.get("market"),
            "as_of": prediction.get("as_of"),
            "horizon": prediction.get("horizon"),
            "stance": stance,
            "direction": direction,
            "confidence": role_data.get("confidence"),
            "recorded_at": now_iso(),
        }
        old_weight = float(role.get("weight", 1.0))
        if role["neutral_streak"] >= neutral_penalty_after:
            new_weight = round(max(min_weight, old_weight * (1 - neutral_penalty_rate)), 3)
            role["weight"] = new_weight
            neutral_penalties.append({
                "role": role_id,
                "neutral_streak": role["neutral_streak"],
                "old_weight": old_weight,
                "new_weight": new_weight,
                "penalty_rate": neutral_penalty_rate,
            })
        changed_roles.append({
            "role": role_id,
            "stance": stance,
            "direction": direction,
            "neutral_streak": role["neutral_streak"],
            "weight": role["weight"],
        })

    replacement_candidates = mark_low_weight_roles(state)
    event = {
        "event": "prediction_recorded",
        "recorded_at": now_iso(),
        "ticker": prediction.get("ticker"),
        "market": prediction.get("market"),
        "horizon": prediction.get("horizon"),
        "roles": changed_roles,
        "neutral_penalties": neutral_penalties,
        "replacement_candidates": replacement_candidates,
    }
    state["history"].append(event)
    state["last_prediction_event"] = event
    return event


def update_outcome(state: dict[str, Any], prediction: dict[str, Any], outcome: dict[str, Any]) -> dict[str, Any]:
    settings = state["settings"]
    learning_rate = float(settings["learning_rate"])
    min_weight = float(settings["min_weight"])
    max_weight = float(settings["max_weight"])
    actual = normalize_direction(outcome.get("actual") or outcome.get("direction") or outcome.get("result"))
    if actual == "unknown":
        raise ValueError("Outcome must include actual direction: up/down/flat, outperform/inline/underperform, or equivalent.")

    evaluated = []
    roles = prediction.get("roles", {})
    for role_id, role_data in roles.items():
        if not isinstance(role_data, dict):
            continue
        predicted = role_prediction(role_data)
        if predicted == "unknown":
            continue
        role = state["roles"].setdefault(role_id, new_role_state(role_id))
        evaluated.append({
            "role": role_id,
            "predicted": predicted,
            "actual": actual,
            "correct": predicted == actual,
            "confidence": role_data.get("confidence", 70),
            "old_weight": float(role.get("weight", 1.0)),
        })

    if not evaluated:
        raise ValueError("No roles could be evaluated.")

    correct_count = sum(1 for item in evaluated if item["correct"])
    all_correct = correct_count == len(evaluated)
    all_wrong = correct_count == 0

    if not all_correct and not all_wrong:
        for item in evaluated:
            role = state["roles"][item["role"]]
            factor = confidence_factor(item["confidence"])
            old = item["old_weight"]
            if item["correct"]:
                role["weight"] = round(min(max_weight, old * (1 + learning_rate * factor)), 3)
                role["correct_count"] = int(role.get("correct_count", 0)) + 1
            else:
                role["weight"] = round(max(min_weight, old * (1 - learning_rate * factor)), 3)
                role["incorrect_count"] = int(role.get("incorrect_count", 0)) + 1
            item["new_weight"] = role["weight"]
    else:
        for item in evaluated:
            role = state["roles"][item["role"]]
            if item["correct"]:
                role["correct_count"] = int(role.get("correct_count", 0)) + 1
            else:
                role["incorrect_count"] = int(role.get("incorrect_count", 0)) + 1
            item["new_weight"] = role["weight"]

    for item in evaluated:
        role = state["roles"][item["role"]]
        role["outcome_count"] = int(role.get("outcome_count", 0)) + 1
        role["last_outcome"] = {
            "ticker": prediction.get("ticker") or outcome.get("ticker"),
            "market": prediction.get("market") or outcome.get("market"),
            "horizon": prediction.get("horizon") or outcome.get("horizon"),
            "actual": actual,
            "correct": item["correct"],
            "updated_at": now_iso(),
        }

    replacement_candidates = mark_low_weight_roles(state)
    event = {
        "event": "outcome_updated",
        "updated_at": now_iso(),
        "ticker": prediction.get("ticker") or outcome.get("ticker"),
        "market": prediction.get("market") or outcome.get("market"),
        "horizon": prediction.get("horizon") or outcome.get("horizon"),
        "metric": outcome.get("metric") or prediction.get("prediction_metric"),
        "actual": actual,
        "all_correct": all_correct,
        "all_wrong": all_wrong,
        "evaluated": evaluated,
        "replacement_candidates": replacement_candidates,
    }
    state["history"].append(event)
    state["last_outcome_event"] = event
    return event


def export_weights_view(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "settings": state["settings"],
        "roles": {role_id: role.get("weight", 1.0) for role_id, role in state["roles"].items()},
        "neutral_streaks": {role_id: role.get("neutral_streak", 0) for role_id, role in state["roles"].items()},
        "statuses": {role_id: role.get("status", "active") for role_id, role in state["roles"].items()},
        "last_prediction_event": state.get("last_prediction_event"),
        "last_outcome_event": state.get("last_outcome_event"),
    }


def export_stance_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "settings": state["settings"],
        "roles": {
            role_id: {
                "status": role.get("status", "active"),
                "weight": role.get("weight", 1.0),
                "neutral_streak": role.get("neutral_streak", 0),
                "stance_counts": role.get("stance_counts", {}),
                "direction_counts": role.get("direction_counts", {}),
                "prediction_count": role.get("prediction_count", 0),
                "outcome_count": role.get("outcome_count", 0),
                "correct_count": role.get("correct_count", 0),
                "incorrect_count": role.get("incorrect_count", 0),
                "last_prediction": role.get("last_prediction"),
                "last_outcome": role.get("last_outcome"),
                "replacement": role.get("replacement"),
            }
            for role_id, role in state["roles"].items()
        },
        "last_prediction_event": state.get("last_prediction_event"),
        "last_outcome_event": state.get("last_outcome_event"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Persist stock committee role state across sessions.")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create state file if missing.")
    init.add_argument("--state", required=True)
    init.add_argument("--output-weights")
    init.add_argument("--output-stance-snapshot")

    record = sub.add_parser("record-prediction", help="Record role stances immediately after a report.")
    record.add_argument("--state", required=True)
    record.add_argument("--prediction", required=True)
    record.add_argument("--output-weights")
    record.add_argument("--output-stance-snapshot")

    outcome = sub.add_parser("update-outcome", help="Update weights from a saved prediction and later outcome.")
    outcome.add_argument("--state", required=True)
    outcome.add_argument("--prediction", required=True)
    outcome.add_argument("--outcome", required=True)
    outcome.add_argument("--output-weights")
    outcome.add_argument("--output-stance-snapshot")

    args = parser.parse_args()
    state_path = Path(args.state)
    state = load_state(state_path)

    if args.command == "init":
        event = {"event": "state_initialized", "updated_at": now_iso()}
    elif args.command == "record-prediction":
        event = record_prediction(state, load_json(Path(args.prediction)))
    elif args.command == "update-outcome":
        event = update_outcome(state, load_json(Path(args.prediction)), load_json(Path(args.outcome)))
    else:
        raise SystemExit(f"Unknown command: {args.command}")

    write_json(state_path, state)
    output_weights = getattr(args, "output_weights", None)
    if output_weights:
        write_json(Path(output_weights), export_weights_view(state))
    output_stance_snapshot = getattr(args, "output_stance_snapshot", None)
    if output_stance_snapshot:
        write_json(Path(output_stance_snapshot), export_stance_snapshot(state))
    print(json.dumps(event, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
