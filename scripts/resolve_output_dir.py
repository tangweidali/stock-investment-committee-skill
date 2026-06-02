#!/usr/bin/env python3
"""Resolve a single task output directory for all committee artifacts."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9一-鿿]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "committee_report"


def desktop_dir() -> Path:
    return Path.home() / "Desktop" / "committee_reports"


def current_dir() -> Path:
    return Path.cwd() / "committee_reports"


def skill_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "committee_reports"


def base_dir_for_choice(choice: str, other_path: str | None) -> Path:
    normalized = choice.strip().lower()
    if normalized in {"current", "current_path", "当前路径", "1"}:
        return current_dir()
    if normalized in {"desktop", "桌面", "2"}:
        return desktop_dir()
    if normalized in {"skill", "skill_folder", "skill文件夹", "3"}:
        return skill_dir()
    if normalized in {"other", "其它", "其他", "4"}:
        if not other_path:
            raise SystemExit("--other-path is required when choice is other")
        return Path(other_path).expanduser()
    raise SystemExit(f"Unknown output location choice: {choice}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve committee output directory.")
    parser.add_argument("--choice", required=True, help="current, desktop, skill, or other")
    parser.add_argument("--other-path", help="Custom base path when choice=other")
    parser.add_argument("--asset", required=True, help="Asset/ticker name, e.g. BTC/USD")
    parser.add_argument("--date", default=date.today().isoformat(), help="Report date, default today")
    parser.add_argument("--output", help="JSON output path. Defaults to <task_dir>/output_layout.json")
    args = parser.parse_args()

    base = base_dir_for_choice(args.choice, args.other_path)
    task_slug = f"{slugify(args.asset)}_{args.date}"
    task_dir = base / task_slug
    role_outputs_dir = task_dir / "role_outputs"
    agent_outputs_dir = task_dir / "agent_outputs"
    output_layout = Path(args.output).expanduser() if args.output else task_dir / "output_layout.json"
    task_dir.mkdir(parents=True, exist_ok=True)
    role_outputs_dir.mkdir(parents=True, exist_ok=True)
    agent_outputs_dir.mkdir(parents=True, exist_ok=True)
    output_layout.parent.mkdir(parents=True, exist_ok=True)

    result = {
        "base_dir": str(base),
        "task_dir": str(task_dir),
        "output_layout": str(output_layout),
        "state_file": str(base / "committee_state.json"),
        "weights_file": str(base / "committee_weights.json"),
        "prediction_record": str(task_dir / "prediction.json"),
        "stance_snapshot": str(task_dir / "stance_snapshot.json"),
        "role_outputs_dir": str(role_outputs_dir),
        "agent_outputs_dir": str(agent_outputs_dir),
        "subagent_manifest": str(task_dir / "subagent_manifest.json"),
        "preflight": str(task_dir / "preflight.json"),
        "shared_context": str(task_dir / "shared_context.md"),
        "markdown_report": str(task_dir / "report.md"),
        "html_report": str(task_dir / "report.html"),
    }
    output_layout.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
