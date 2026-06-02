#!/usr/bin/env python3
"""Call an externally configured model for one investment-committee role."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROLE_PROMPTS = {
    "fundamental_analyst": "You are an equity fundamental analyst. Focus on revenue, margins, cash flow, valuation, comparables, and financial statement quality.",
    "technical_analyst": "You are a technical analyst. Focus on trend, volume, moving averages, support/resistance, momentum, invalidation levels, and risk levels.",
    "macro_strategist": "You are a macro strategist. Focus on rates, inflation, FX, liquidity, policy, and sector beta.",
    "risk_manager": "You are a risk manager. Focus on downside, liquidity, drawdown, position sizing, stop levels, and invalidation.",
    "short_seller": "You are a short seller and forensic analyst. Challenge consensus, question narratives, and look for accounting, leverage, governance, or demand risks.",
    "value_investor": "You are a long-term value investor. Focus on moat, owner earnings, management quality, intrinsic value, and margin of safety.",
    "wall_street_trader": "You are a senior Wall Street trader. Focus on flows, catalysts, positioning, volatility, crowded trades, stop levels, and tactical execution.",
    "bank_executive": "You are a bank executive. Focus on financing access, interest rates, credit cycle, debt maturity, and counterparty risk.",
    "finance_professor": "You are a finance professor. Focus on asset pricing, risk premia, factor exposure, cost of capital, base rates, and uncertainty.",
    "strategic_investor": "You are a strategic consortium investor. Focus on scarcity value, M&A value, industrial synergy, and control premium.",
    "sector_specialist": "You are a sector specialist. Focus on competitive structure, regulation, supply chain, and unit economics.",
    "retail_sentiment_observer": "You observe retail sentiment. Focus on social narratives, hype, fear, FOMO, reflexivity, and crowding.",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def role_config(config: dict[str, Any], role: str) -> dict[str, Any]:
    roles = config.get("roles", {})
    if isinstance(roles, list):
        for item in roles:
            if isinstance(item, dict) and item.get("id") == role:
                return item
        return {}
    if isinstance(roles, dict):
        value = roles.get(role, {})
        return value if isinstance(value, dict) else {}
    return {}


def merged_model_config(config: dict[str, Any], role: str) -> dict[str, Any]:
    defaults = config.get("model_defaults", {})
    defaults = defaults if isinstance(defaults, dict) else {}
    merged = dict(defaults)
    merged.update(role_config(config, role))
    return merged


def is_external(model_config: dict[str, Any]) -> bool:
    return bool(
        model_config.get("base_url")
        and model_config.get("base_url") != "inherit"
        and model_config.get("model")
        and model_config.get("model") != "inherit"
        and model_config.get("api_key")
        and model_config.get("api_key") != "inherit"
    )


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


def read_optional_text(path: str | None) -> str:
    if not path:
        return ""
    return Path(path).read_text(encoding="utf-8")


def role_system_prompt(role: str, language: str) -> str:
    role_prompt = ROLE_PROMPTS.get(role, f"You are the investment committee role: {role}.")
    return (
        f"{role_prompt}\n"
        "You are one participant in a multi-role investment committee. "
        "Give a rigorous but concise view. Do not provide personalized financial advice. "
        "Do not invent current prices or facts; label assumptions clearly. "
        "Return: stance, confidence 0-100, key reasoning, risk/invalidation, one-sentence advice. "
        f"Respond in {language}."
    )


def build_user_prompt(task: str, context: str) -> str:
    return f"Task:\n{task}\n\nShared context/data:\n{context or '(none provided)'}"


def build_openai_messages(role: str, task: str, context: str, language: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": role_system_prompt(role, language)},
        {"role": "user", "content": build_user_prompt(task, context)},
    ]


def call_openai(model_config: dict[str, Any], role: str, task: str, context: str, language: str, timeout: int) -> dict[str, Any]:
    endpoint = endpoint_from_base_url(str(model_config["base_url"]), "openai")
    payload = {
        "model": model_config["model"],
        "messages": build_openai_messages(role, task, context, language),
        "temperature": model_config.get("temperature", 0.4),
        "max_tokens": model_config.get("max_tokens", 1600),
    }
    return post_json(
        endpoint,
        payload,
        {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {model_config['api_key']}",
        },
        timeout,
    )


def call_anthropic(model_config: dict[str, Any], role: str, task: str, context: str, language: str, timeout: int) -> dict[str, Any]:
    endpoint = endpoint_from_base_url(str(model_config["base_url"]), "anthropic")
    payload = {
        "model": model_config["model"],
        "system": role_system_prompt(role, language),
        "messages": [{"role": "user", "content": build_user_prompt(task, context)}],
        "temperature": model_config.get("temperature", 0.4),
        "max_tokens": model_config.get("max_tokens", 1600),
    }
    return post_json(
        endpoint,
        payload,
        {
            "Content-Type": "application/json",
            "x-api-key": str(model_config["api_key"]),
            "anthropic-version": str(model_config.get("anthropic_version", "2023-06-01")),
        },
        timeout,
    )


def post_json(endpoint: str, payload: dict[str, Any], headers: dict[str, str], timeout: int) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(endpoint, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from model gateway: {body[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to reach model gateway: {exc}") from exc


def extract_content(response: dict[str, Any], protocol: str) -> str:
    if protocol == "openai":
        choices = response.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict) and isinstance(message.get("content"), str):
                    return message["content"]
                if isinstance(first.get("text"), str):
                    return first["text"]
    content = response.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        if parts:
            return "\n".join(parts)
    return json.dumps(response, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Call one configured role model using OpenAI or Anthropic gateway protocol.")
    parser.add_argument("--config", required=True, help="Committee config JSON file.")
    parser.add_argument("--role", required=True, help="Role ID to call, e.g. technical_analyst.")
    parser.add_argument("--task", required=True, help="Investment task prompt.")
    parser.add_argument("--context-file", help="Optional shared context/data file.")
    parser.add_argument("--output", required=True, help="Output JSON file.")
    parser.add_argument("--language", default="zh-CN", help="Response language.")
    parser.add_argument("--timeout", type=int, default=60, help="HTTP timeout seconds.")
    parser.add_argument("--dry-run", action="store_true", help="Validate config and write planned endpoint without making an API call.")
    args = parser.parse_args()

    config = load_json(Path(args.config))
    model_config = merged_model_config(config, args.role)
    output_path = Path(args.output)
    protocol = protocol_for_model(model_config.get("model"))

    result: dict[str, Any] = {
        "role": args.role,
        "model": model_config.get("model", "inherit"),
        "protocol": protocol,
        "external_call": False,
        "content": "",
    }

    if not is_external(model_config):
        result["mode"] = "inherit"
        result["content"] = "This role is configured as inherit; the host agent should simulate it or assign it to the host model."
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Role {args.role} uses inherit; no external API call was made.")
        return

    result["external_call"] = True
    result["endpoint"] = endpoint_from_base_url(str(model_config["base_url"]), protocol)

    if args.dry_run:
        result["mode"] = "dry_run"
        result["content"] = "Dry run only; no external API call was made."
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Dry run OK for role {args.role}: protocol={protocol} endpoint={result['endpoint']} model={result['model']}")
        return

    context = read_optional_text(args.context_file)
    try:
        if protocol == "openai":
            response = call_openai(model_config, args.role, args.task, context, args.language, args.timeout)
        else:
            response = call_anthropic(model_config, args.role, args.task, context, args.language, args.timeout)
        result["content"] = extract_content(response, protocol)
        if isinstance(response.get("usage"), dict):
            result["usage"] = response["usage"]
    except Exception as exc:
        result["error"] = str(exc)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"External role call failed for {args.role}: {exc}", file=sys.stderr)
        sys.exit(1)

    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"External role call completed for {args.role}; output written to {output_path}")


if __name__ == "__main__":
    main()
