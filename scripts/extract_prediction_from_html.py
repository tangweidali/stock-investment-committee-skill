#!/usr/bin/env python3
"""Extract embedded Markdown and prediction JSON from a committee HTML report."""

from __future__ import annotations

import argparse
import base64
import html as html_lib
import json
import re
from pathlib import Path
from typing import Any


def read_html(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_embedded_markdown(html: str) -> str | None:
    match = re.search(r'<script id="stock-committee-source-markdown" type="application/json">(.*?)</script>', html, re.S)
    if not match:
        return None
    try:
        payload = json.loads(match.group(1))
        if payload.get("encoding") == "base64" and isinstance(payload.get("content"), str):
            return base64.b64decode(payload["content"]).decode("utf-8")
    except Exception:
        return None
    return None


def html_to_text(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.I)
    text = re.sub(r"</(h1|h2|h3|h4|p|li|tr|pre|blockquote)>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return html_lib.unescape(text)


def find_json_blocks(markdown_or_text: str) -> list[str]:
    fenced = re.findall(r"```json\s*([\s\S]*?)\s*```", markdown_or_text, flags=re.I)
    if fenced:
        return fenced
    candidates = []
    for match in re.finditer(r"\{", markdown_or_text):
        start = match.start()
        depth = 0
        in_string = False
        escape = False
        for index in range(start, len(markdown_or_text)):
            char = markdown_or_text[index]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
            else:
                if char == '"':
                    in_string = True
                elif char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        candidates.append(markdown_or_text[start : index + 1])
                        break
    return candidates


def select_prediction(blocks: list[str]) -> dict[str, Any] | None:
    for block in reversed(blocks):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and "roles" in data and ("ticker" in data or "market" in data):
            return data
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract prediction record from stock committee HTML report.")
    parser.add_argument("--html", required=True, help="Input HTML report path.")
    parser.add_argument("--markdown-output", help="Optional path to save extracted Markdown/text.")
    parser.add_argument("--prediction-output", required=True, help="Path to save extracted prediction JSON.")
    args = parser.parse_args()

    source_html = read_html(Path(args.html))
    markdown = extract_embedded_markdown(source_html) or html_to_text(source_html)
    blocks = find_json_blocks(markdown)
    prediction = select_prediction(blocks)
    if prediction is None:
        raise SystemExit("No prediction JSON block found in the HTML report.")

    if args.markdown_output:
        Path(args.markdown_output).write_text(markdown, encoding="utf-8")
    Path(args.prediction_output).write_text(json.dumps(prediction, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Prediction record extracted to {args.prediction_output}")


if __name__ == "__main__":
    main()
