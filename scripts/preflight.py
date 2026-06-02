#!/usr/bin/env python3
"""Preflight checks for stock-investment-committee execution."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def protocol_for_model(model: Any) -> str:
    text = str(model or "").strip().lower()
    return "openai" if text.startswith("gpt") else "anthropic"


def endpoint_from_base_url(base_url: str, protocol: str) -> str:
    base = base_url.rstrip("/")
    if protocol == "openai":
        if base.endswith("/chat/completions"):
            return base
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"
    if base.endswith("/messages"):
        return base
    if base.endswith("/v1"):
        return f"{base}/messages"
    return f"{base}/v1/messages"


def is_external(role_config: dict[str, Any]) -> bool:
    return bool(
        role_config.get("base_url")
        and role_config.get("base_url") != "inherit"
        and role_config.get("api_key")
        and role_config.get("api_key") != "inherit"
        and role_config.get("model")
        and role_config.get("model") != "inherit"
    )


def iter_roles(config: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    roles = config.get("roles", {})
    defaults = config.get("model_defaults", {}) if isinstance(config.get("model_defaults"), dict) else {}
    output: list[tuple[str, dict[str, Any]]] = []
    if isinstance(roles, dict):
        for role_id, value in roles.items():
            role_config = dict(defaults)
            if isinstance(value, dict):
                role_config.update(value)
            output.append((role_id, role_config))
    elif isinstance(roles, list):
        for item in roles:
            if isinstance(item, dict):
                role_config = dict(defaults)
                role_config.update(item)
                role_id = str(item.get("id") or item.get("role") or "unknown_role")
                output.append((role_id, role_config))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Report mandatory execution steps for stock-investment-committee.")
    parser.add_argument("--config", required=True, help="Committee config JSON path.")
    parser.add_argument("--output", required=True, help="Preflight JSON output path.")
    parser.add_argument("--task", default="", help="Task summary.")
    args = parser.parse_args()

    config = load_json(Path(args.config))
    external_roles = []
    inherited_roles = []
    for role_id, role_config in iter_roles(config):
        if is_external(role_config):
            protocol = protocol_for_model(role_config.get("model"))
            external_roles.append(
                {
                    "role": role_id,
                    "model": role_config.get("model"),
                    "protocol": protocol,
                    "endpoint": endpoint_from_base_url(str(role_config.get("base_url")), protocol),
                    "must_call_before_report": True,
                }
            )
        else:
            inherited_roles.append({"role": role_id, "model": role_config.get("model", "inherit")})

    report = config.get("report", {}) if isinstance(config.get("report"), dict) else {}
    result = {
        "task": args.task,
        "external_roles": external_roles,
        "inherited_roles": inherited_roles,
        "html_required": bool(report.get("save_html")),
        "ask_output_location": bool(report.get("ask_output_location", True)),
        "default_output_dir": report.get("output_dir", "committee_reports"),
        "hard_gates": {
            "must_run_external_role_calls": bool(external_roles),
            "must_write_markdown_and_html": bool(report.get("save_html")),
            "must_report_execution_proof": True,
        },
    }
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
