#!/usr/bin/env python3
"""Render a stock committee Markdown report as a standalone HTML file."""

from __future__ import annotations

import argparse
import base64
import html
import re
from datetime import datetime
from pathlib import Path


def inline_markdown(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    return escaped


def render_table(lines: list[str]) -> str:
    rows = []
    for line in lines:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
            continue
        tag = "th" if not rows else "td"
        rows.append("<tr>" + "".join(f"<{tag}>{inline_markdown(cell)}</{tag}>" for cell in cells) + "</tr>")
    return "<table>" + "\n".join(rows) + "</table>"


def markdown_to_html(markdown: str) -> str:
    html_parts: list[str] = []
    lines = markdown.splitlines()
    i = 0
    in_code = False
    code_lines: list[str] = []
    code_lang = ""

    while i < len(lines):
        line = lines[i]

        if line.startswith("```"):
            if not in_code:
                in_code = True
                code_lang = line[3:].strip()
                code_lines = []
            else:
                language_class = f" class=\"language-{html.escape(code_lang)}\"" if code_lang else ""
                html_parts.append(f"<pre><code{language_class}>" + html.escape("\n".join(code_lines)) + "</code></pre>")
                in_code = False
                code_lang = ""
            i += 1
            continue

        if in_code:
            code_lines.append(line)
            i += 1
            continue

        if line.strip().startswith("|") and i + 1 < len(lines) and lines[i + 1].strip().startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            html_parts.append(render_table(table_lines))
            continue

        stripped = line.strip()
        if not stripped:
            html_parts.append("")
        elif stripped.startswith("# "):
            html_parts.append(f"<h1>{inline_markdown(stripped[2:].strip())}</h1>")
        elif stripped.startswith("## "):
            html_parts.append(f"<h2>{inline_markdown(stripped[3:].strip())}</h2>")
        elif stripped.startswith("### "):
            html_parts.append(f"<h3>{inline_markdown(stripped[4:].strip())}</h3>")
        elif stripped.startswith("#### "):
            html_parts.append(f"<h4>{inline_markdown(stripped[5:].strip())}</h4>")
        elif stripped.startswith("- "):
            items = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                items.append(f"<li>{inline_markdown(lines[i].strip()[2:].strip())}</li>")
                i += 1
            html_parts.append("<ul>" + "\n".join(items) + "</ul>")
            continue
        elif re.match(r"^\d+\.\s+", stripped):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i].strip()):
                item = re.sub(r"^\d+\.\s+", "", lines[i].strip())
                items.append(f"<li>{inline_markdown(item)}</li>")
                i += 1
            html_parts.append("<ol>" + "\n".join(items) + "</ol>")
            continue
        elif stripped.startswith("> "):
            html_parts.append(f"<blockquote>{inline_markdown(stripped[2:].strip())}</blockquote>")
        else:
            html_parts.append(f"<p>{inline_markdown(stripped)}</p>")
        i += 1

    return "\n".join(html_parts)


def build_html(title: str, body_html: str, source_markdown: str) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    source_b64 = base64.b64encode(source_markdown.encode("utf-8")).decode("ascii")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="stock-committee-source-format" content="markdown-base64">
  <title>{html.escape(title)}</title>
  <script id="stock-committee-source-markdown" type="application/json">{{"encoding":"base64","content":"{source_b64}"}}</script>
  <style>
    :root {{ color-scheme: light; --bg: #f6f7fb; --card: #ffffff; --text: #172033; --muted: #667085; --border: #d9dee8; --accent: #2454ff; }}
    body {{ margin: 0; background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif; line-height: 1.65; }}
    main {{ max-width: 1120px; margin: 32px auto; padding: 0 20px 48px; }}
    article {{ background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 32px; box-shadow: 0 8px 32px rgba(16, 24, 40, 0.08); }}
    h1 {{ font-size: 30px; margin: 0 0 20px; border-bottom: 2px solid var(--border); padding-bottom: 16px; }}
    h2 {{ margin-top: 34px; font-size: 23px; color: #111827; }}
    h3 {{ margin-top: 26px; font-size: 19px; color: #1f2937; }}
    h4 {{ margin-top: 20px; font-size: 16px; }}
    table {{ width: 100%; border-collapse: collapse; margin: 18px 0; overflow: hidden; border-radius: 10px; }}
    th, td {{ border: 1px solid var(--border); padding: 10px 12px; vertical-align: top; }}
    th {{ background: #eef2ff; text-align: left; }}
    tr:nth-child(even) td {{ background: #fafbff; }}
    code {{ background: #eef2f7; padding: 2px 5px; border-radius: 5px; }}
    pre {{ background: #101828; color: #e6edf3; padding: 16px; border-radius: 12px; overflow-x: auto; }}
    pre code {{ background: transparent; padding: 0; }}
    blockquote {{ margin: 18px 0; padding: 12px 16px; border-left: 4px solid var(--accent); background: #f1f5ff; color: #1d2939; }}
    .meta {{ color: var(--muted); font-size: 13px; margin-bottom: 20px; }}
    @media print {{ body {{ background: #fff; }} main {{ margin: 0; max-width: none; }} article {{ box-shadow: none; border: none; }} }}
  </style>
</head>
<body>
  <main>
    <article>
      <div class="meta">Generated by stock-investment-committee at {html.escape(generated_at)}</div>
      {body_html}
    </article>
  </main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Render committee Markdown report to standalone HTML.")
    parser.add_argument("--input", required=True, help="Input Markdown report path.")
    parser.add_argument("--output", required=True, help="Output HTML path.")
    parser.add_argument("--title", default="Stock Investment Committee Report", help="HTML title.")
    args = parser.parse_args()

    markdown = Path(args.input).read_text(encoding="utf-8")
    body = markdown_to_html(markdown)
    html_text = build_html(args.title, body, markdown)
    Path(args.output).write_text(html_text, encoding="utf-8")
    print(f"HTML report written to {args.output}")


if __name__ == "__main__":
    main()
