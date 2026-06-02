---
name: stock-investment-committee
description: "Run a multi-role stock investment committee debate for a ticker, company, sector stock, crypto pair, commodity, or investment idea. Use this skill whenever the user asks to analyze an asset through multiple expert personas, simulate an investment committee, compare bullish and bearish views, run a debate between analysts/traders/professors/bankers/investors, produce buy/hold/sell opinions, output an HTML report, call configured role models, or update role weights from later outcomes. Mandatory execution gates: run preflight, actually call configured external role models, write Markdown/HTML reports when configured, and include execution proof instead of merely simulating those steps."
---

# Stock Investment Committee

Use this skill to turn a stock ticker or company into a structured multi-role investment committee debate. The goal is not to predict with certainty; it is to expose assumptions, force disagreement, track which perspectives have been useful over time, and produce a disciplined synthesis.

## Non-negotiable execution contract

This skill is not just a writing template. If the config requires external role models or HTML output, those actions must actually be executed and verified before giving the final report.

Before any final report:

1. Resolve the task layout with `scripts/resolve_output_dir.py`; use the returned `state_file`, `weights_file`, and task paths for every later step.
2. Initialize or read the cross-session state with `scripts/committee_state.py init --state <state_file> --output-weights <weights_file> --output-stance-snapshot <task_dir>/stance_snapshot.json` before creating role opinions. Use the persisted role weights and statuses in the framing and weighted vote.
3. Run `scripts/preflight.py` against the config and read its output.
4. If `external_roles` is non-empty, call every listed role with `scripts/run_role_model.py` and use the returned content in Round 1.
5. If an external role call fails, stop and report the failure; do not silently simulate that role unless the user explicitly approves fallback.
6. If the host supports real subagents, create separate subagents for the inherited committee roles where practical, save each raw subagent result under `agent_outputs/<role>.md`, and write `subagent_manifest.json`. If real subagents are unavailable or not used, state that explicitly in `subagent_manifest.json` and in the execution proof; do not imply subagents were created.
7. If `html_required` is true, ask the user to choose the output location before writing the report.
8. Save the machine-readable prediction record as `<task_dir>/prediction.json` before rendering the final report.
9. Immediately after `prediction.json` is written, run `scripts/committee_state.py record-prediction --state <state_file> --prediction <task_dir>/prediction.json --output-weights <weights_file> --output-stance-snapshot <task_dir>/stance_snapshot.json`. This is mandatory because role weights, neutral streaks, and bull/neutral/bear stance counts must persist across sessions even before the later outcome is known.
10. Save the Markdown and render the HTML; return both file paths.
11. Include an execution proof block with: state file path, weights file path, prediction JSON path, preflight JSON path, each external role output JSON path, subagent manifest path, subagent output paths or explicit fallback, Markdown path, HTML path, and any fallback approved by the user.

If any required action above cannot be completed, do not present the analysis as complete.

## Safety and scope

- State clearly that this is research and education, not personalized financial advice.
- Ask for missing basics before analyzing: market, ticker/company, investment horizon, risk tolerance, and whether current web/data access is available.
- If live data is unavailable, say the analysis is based on user-provided facts and general reasoning, and list the data that must be verified.
- Do not invent current prices, financials, news, analyst ratings, or filings. Use provided data, accessible tools, or explicitly label assumptions.
- Avoid claiming certainty. Use probabilistic language and scenario thinking.

## Inputs

Accept natural language, or a compact config block.

Minimum input:

```yaml
ticker: "AAPL"
market: "US"
horizon: "3 months"
risk_profile: "moderate"
```

Optional input:

```yaml
committee:
  rounds: 4
  output_style: "debate" # debate | minutes | matrix | full
  language: "zh-CN"
  data_mode: "use_available_tools" # use_available_tools | user_provided_only | no_live_data
model_defaults:
  base_url: "inherit"
  api_key: "inherit"
  model: "inherit"
roles:
  - id: fundamental_analyst
    model: "inherit"
    weight: 1.0
  - id: technical_analyst
    base_url: "https://example.invalid/v1"
    api_key: "sk-your-api-key-here"
    model: "some-model-name"
report:
  save_markdown: true
  save_html: true
  output_dir: "committee_reports"
weights:
  file: "committee_weights.json"
  learning_rate: 0.08
  min_weight: 0.40
  max_weight: 2.50
  neutral_penalty_after: 3
  neutral_penalty_rate: 0.05
```

### Model configuration rule

Treat `inherit` as: use the same model route as the host agent if the host supports subagents or external model calls. If the host cannot expose its model route, keep the role as an internal simulated persona and say so.

For portability across Claude Code, OpenCode, 龙虾, and similar tools:

- Keep the core process executable as plain Markdown instructions with no required external dependency.
- If the host supports real subagents, assign one role per subagent when practical and preserve each subagent's raw output separately under `agent_outputs/`.
- If the host does not support subagents, simulate the roles sequentially in one response while preserving disagreement, and record `subagents_used: false` in `subagent_manifest.json`.
- If using external APIs, allow keys to be read directly from the user-provided config file or from environment variables. Do not print API keys in reports, logs, or debate output.

### External model execution rule

If any role has a non-`inherit` `base_url`, non-`inherit` `api_key`, and non-`inherit` `model`, that role must be called as a real external model, not merely simulated. This is a hard gate, not an optional enhancement.

Run preflight first:

```bash
uv run python scripts/preflight.py --config references/config-example.json --task "<user task>" --output committee_reports/preflight.json
```

If `preflight.json` lists external roles, each listed role requires a corresponding `role_outputs/<role>.json` created by `run_role_model.py`. Do not write the final report until those files exist, or until the user explicitly approves fallback after seeing the error.

Gateway protocol rule:

- Model names beginning with `gpt` use the OpenAI protocol: `POST {base_url}/v1/chat/completions` with `Authorization: Bearer ...`.
- All non-GPT model names use the Anthropic protocol: `POST {base_url}/v1/messages` with `x-api-key` and `anthropic-version` headers.
- Do not infer protocol from provider brand; infer only from the model name rule above unless the script is explicitly changed later.

When scripts are available, run `scripts/run_role_model.py` before writing that role's opening statement:

```bash
uv run python scripts/run_role_model.py --config references/config-example.json --role technical_analyst --task "Analyze XAU/USD for 1 month. Entry 4478.499, currently profitable. Should the user hold?" --context-file shared_context.md --output role_outputs/technical_analyst.json --language zh-CN
```

Use the returned `content` as that role's independent view in Round 1, and cite in the framing that this role used the configured external model. If the external call fails, report the failure and ask whether to continue by simulating that role with the host model; do not silently pretend the external model was used.

Use `--dry-run` when the user only wants to validate routing without spending tokens:

```bash
uv run python scripts/run_role_model.py --config references/config-example.json --role technical_analyst --task "test" --output role_outputs/technical_analyst.json --dry-run
```

## Default committee

Use these roles unless the user customizes them. Keep the default weight at `1.0` unless a weights file is provided.

| Role ID | Name | Default stance pressure | What they emphasize |
|---|---|---:|---|
| fundamental_analyst | Equity fundamental analyst | balanced | revenue, margins, cash flow, valuation, comparables, financial statement quality |
| technical_analyst | Technical analyst | price-first | trend, volume, moving averages, support/resistance, momentum, risk levels |
| macro_strategist | Macro strategist | top-down | rates, inflation, FX, liquidity, policy, sector beta |
| risk_manager | Risk manager | skeptical | downside, liquidity, concentration, drawdown, position sizing, invalidation |
| short_seller | Short seller / forensic analyst | bearish | accounting quality, broken narratives, channel stuffing, leverage, governance |
| value_investor | Long-term value investor | patient | moat, owner earnings, management, intrinsic value, margin of safety |
| wall_street_trader | Senior Wall Street trader | tactical | flows, catalysts, positioning, volatility, stop levels, crowded trades |
| bank_executive | Bank executive | credit-cycle | financing access, debt maturity, covenant pressure, counterparty risk |
| finance_professor | Finance professor | neutral | asset pricing, factor exposure, cost of capital, empirical base rates |
| strategic_investor | Consortium / strategic investor | strategic | M&A value, asset scarcity, industrial synergy, control premium |
| sector_specialist | Sector specialist | industry-aware | competitive structure, regulation, supply chain, unit economics |
| retail_sentiment_observer | Retail sentiment observer | sentiment-aware | social narrative, hype, fear, reflexivity, crowded retail behavior |

## Default rounds

Default `rounds: 4`. Let the user override. Use fewer rounds for quick answers and more rounds for deep research.

### Round 0: Framing

Create a brief setup:

- ticker/company and market
- horizon
- risk profile
- data available vs missing
- committee roles and any non-default weights
- key question: buy, hold, sell, short, avoid, or watchlist

### Round 1: Independent opening statements

Each role gives:

- stance: bullish / neutral-bullish / neutral / neutral-bearish / bearish
- confidence: 0-100
- key evidence or assumptions
- one thing that would change their mind

Do not let roles agree too quickly. Each role should speak from its professional lens.

### Round 2: Direct challenges

The moderator identifies 3-6 contradictions, then pairs roles to challenge each other. Examples:

- fundamental analyst vs short seller on earnings quality
- technical analyst vs value investor on timing
- macro strategist vs sector specialist on top-down vs bottom-up drivers
- risk manager vs trader on position sizing

For each challenge, show:

- challenger claim
- target response
- whether the response weakened, held, or strengthened the target's view

### Round 3: Cross-examination and revisions

Ask each role to answer one hard question from an opposing role. Then allow stance/confidence revisions.

Track changes explicitly:

```text
technical_analyst: neutral-bearish 62 -> neutral 54 because price is weak but downside momentum is fading.
```

### Round 4: Vote and synthesis

Each role gives exactly one sentence of advice. Then produce:

- weighted vote table
- bull case
- bear case
- key disagreement
- required verification data
- final moderator view
- action framing by investor type: short-term trader, swing trader, long-term investor, risk-averse investor

### Extra rounds

If `rounds > 4`, add rotating deep dives:

5. financial statement quality and valuation sensitivity
6. technical levels and trading plan
7. macro/sector scenario tree
8. red-team fraud/governance/regulatory risks
9. position sizing and risk controls
10. final adversarial review: the strongest argument against the moderator's conclusion

## Weight mechanism

Weights represent how much historical trust to give each role's prediction for this user/workflow. They are not truth and should not silence minority views.

Persistent state is mandatory. The skill must maintain a cross-session `committee_state.json` at the selected output base directory, beside `committee_weights.json`. This state records every role's current weight, active/replacement status, consecutive neutral streak, cumulative bull/neutral/bear stance counts, cumulative up/flat/down direction counts, prediction count, outcome count, correct count, and incorrect count. A single report's `prediction.json` is not enough; it must be recorded into `committee_state.json` immediately after each report.

### Prediction record

At the end of every committee, create a machine-readable prediction block that can be saved by the user:

```json
{
  "ticker": "AAPL",
  "market": "US",
  "as_of": "2026-05-22",
  "horizon": "3 months",
  "benchmark": "SPY or relevant index",
  "prediction_metric": "relative_return_direction",
  "roles": {
    "fundamental_analyst": {"stance": "bullish", "expected_direction": "up", "confidence": 68, "weight": 1.0},
    "technical_analyst": {"stance": "neutral-bearish", "expected_direction": "down", "confidence": 61, "weight": 1.0}
  }
}
```

Use one of these metrics:

- `absolute_return_direction`: up / flat / down over the horizon
- `relative_return_direction`: outperform / inline / underperform versus benchmark
- `risk_event`: whether a specified risk did or did not happen

### Outcome record

When the user later provides actual movement, accept this format:

```json
{
  "ticker": "AAPL",
  "horizon_end": "2026-08-22",
  "metric": "relative_return_direction",
  "actual": "outperform"
}
```

Map predictions to correctness:

- bullish/up/outperform is correct if actual is up/outperform.
- bearish/down/underperform is correct if actual is down/underperform.
- neutral/flat/inline is correct if actual is flat/inline.
- If the role's prediction is too vague, exclude that role from the update and explain why.

### Update rule

Let `correct_roles` be roles whose prediction matched the outcome and `incorrect_roles` be roles whose prediction did not match.

- If every evaluated role is correct: do not change any weights.
- If every evaluated role is incorrect: do not change any weights.
- Otherwise:
  - correct role: `new_weight = min(max_weight, old_weight * (1 + learning_rate * confidence_factor))`
  - incorrect role: `new_weight = max(min_weight, old_weight * (1 - learning_rate * confidence_factor))`
  - `confidence_factor = clamp(confidence / 70, 0.5, 1.5)`
- Defaults: `learning_rate = 0.08`, `min_weight = 0.40`, `max_weight = 2.50`.
- Round weights to 3 decimals.

Neutral-streak penalty:

- Track each role's consecutive neutral/flat/inline predictions in `committee_state.json`, not only in the current report.
- Apply the neutral-streak penalty immediately when recording each prediction, even before the later market outcome is known.
- If a role stays neutral for `neutral_penalty_after = 3` consecutive recorded predictions, lower its persistent weight by `neutral_penalty_rate = 0.05` each update while the streak continues.
- Reset the streak to 0 when the role makes a directional up/outperform or down/underperform prediction.
- This penalty is separate from the correctness update. It discourages roles from staying permanently noncommittal while preserving neutral calls when they are occasional and useful.

This rule rewards differentiated insight. If everyone was right, there is no relative skill signal; if everyone was wrong, there is no useful basis to punish one role over another.

### Applying weights in future debates

- Read persistent role weights from `committee_state.json` / `committee_weights.json` before generating role opinions.
- Use weights to influence the final synthesis and weighted vote table.
- Do not let high-weight roles dominate the debate transcript. Low-weight roles still provide useful red-team pressure.
- Show both raw count and weighted count.
- If a role weight changed recently, mention it briefly in the framing.
- If a role's status is `replacement_candidate`, state that the role should be replaced before relying on it in future committees.

### Role replacement lifecycle

A role whose persistent weight falls to or below `kill_weight_below` is marked `replacement_candidate` in `committee_state.json`. Do not silently remove it. Future versions or user configuration can map that role to a new model/persona; until replacement is configured, keep the old role available for transparency but flag it as low-trust in the framing and execution proof.

## Mandatory persistent state script

Use `scripts/committee_state.py` for cross-session state. `scripts/update_weights.py` is retained only for legacy one-off weight updates; the normal workflow must use `committee_state.py` so weights, neutral streaks, stance counts, and replacement status remain durable.

Initialize/read state before analysis:

```bash
uv run python scripts/committee_state.py init --state <base_dir>/committee_state.json --output-weights <base_dir>/committee_weights.json --output-stance-snapshot <task_dir>/stance_snapshot.json
```

After writing `<task_dir>/prediction.json`, immediately persist the role stances and neutral streaks:

```bash
uv run python scripts/committee_state.py record-prediction --state <base_dir>/committee_state.json --prediction <task_dir>/prediction.json --output-weights <base_dir>/committee_weights.json --output-stance-snapshot <task_dir>/stance_snapshot.json
```

When the user later provides an actual outcome, update the same persistent state:

```bash
uv run python scripts/committee_state.py update-outcome --state <base_dir>/committee_state.json --prediction <task_dir>/prediction.json --outcome outcome.json --output-weights <base_dir>/committee_weights.json --output-stance-snapshot <task_dir>/stance_snapshot.json
```

If the user provides a previous HTML report instead of a prediction JSON, first extract the saved prediction record:

```bash
uv run python scripts/extract_prediction_from_html.py --html previous_report.html --markdown-output previous_report.md --prediction-output prediction.json
uv run python scripts/committee_state.py update-outcome --state <base_dir>/committee_state.json --prediction prediction.json --outcome outcome.json --output-weights <base_dir>/committee_weights.json --output-stance-snapshot <task_dir>/stance_snapshot.json
```

This lets the skill review its own prior HTML output during later performance review. If extraction fails, ask the user for the original prediction record or Markdown report.

If scripts are not available in the host tool, apply the same formula manually, but still write an equivalent persistent `committee_state.json`; otherwise the weight mechanism is incomplete.

## HTML report output

If the user asks for an HTML file, or config has `report.save_html: true`, HTML output is mandatory. Ask the user to choose where to save it before writing files. Offer exactly these location choices:

1. Current path: save under the current working directory, e.g. `./committee_reports/`.
2. Desktop: save under the user's Desktop, e.g. `~/Desktop/committee_reports/`.
3. Skill folder: save under this skill's `committee_reports/` folder.
4. Other: user provides a custom absolute path.

After the user chooses, create one task folder and put every artifact for that analysis inside it. Do not split artifacts between the selected location and the skill folder.

Use `scripts/resolve_output_dir.py` to create the task folder and record the layout. By default, it writes `output_layout.json` inside the resolved task folder and prints the same JSON:

```bash
uv run python scripts/resolve_output_dir.py --choice desktop --asset "BTC/USD" --date 2026-05-22
```

The selected base directory and resolved task folder must contain this structure:

```text
<base_dir>/
  committee_state.json
  committee_weights.json
  <task_dir>/
    output_layout.json
    prediction.json
    stance_snapshot.json
    preflight.json
    shared_context.md
    subagent_manifest.json
    role_outputs/
      technical_analyst.json
    agent_outputs/
      fundamental_analyst.md
      macro_strategist.md
      risk_manager.md
    report.md
    report.html
```

`agent_outputs/` contains raw outputs from real subagents when used. If subagents are unavailable or not used, keep the directory and write `subagent_manifest.json` with `subagents_used: false` plus the reason.

Then run preflight and external role calls using paths inside the same task folder:

```bash
uv run python scripts/preflight.py --config references/config-example.json --task "<user task>" --output <task_dir>/preflight.json
uv run python scripts/run_role_model.py --config references/config-example.json --role technical_analyst --task "<user task>" --context-file <task_dir>/shared_context.md --output <task_dir>/role_outputs/technical_analyst.json --language zh-CN
uv run python scripts/render_report_html.py --input <task_dir>/report.md --output <task_dir>/report.html --title "Stock Investment Committee Report"
```

Return both the Markdown and HTML file paths to the user. The HTML embeds the source Markdown in a hidden script block so future weight reviews can extract the original prediction record from the HTML. The HTML should contain the same final report, tables, debate transcript, weighted vote, risk note, and prediction record. Do not include API keys in the report.

Final responses must include this execution proof block:

```markdown
## Execution proof
- Persistent state: <base_dir>/committee_state.json
- Weights view: <base_dir>/committee_weights.json
- Prediction record: <task_dir>/prediction.json
- Preflight: <task_dir>/preflight.json
- External role outputs: <role>=<task_dir>/role_outputs/<role>.json, or `none configured`
- Subagent manifest: <task_dir>/subagent_manifest.json
- Subagent outputs: <role>=<task_dir>/agent_outputs/<role>.md, or `subagents not used: <reason>`
- Markdown report: <task_dir>/report.md
- HTML report: <task_dir>/report.html
- Fallbacks: none / user-approved details
```

If the HTML report path is missing, the task is not complete.

## Output formats

Choose the style requested by the user; default to `full` for serious analysis.

### Full report template

```markdown
# 多角色投委会：{ticker/company}

## 0. 前提与限制

## 1. 角色初始观点
| 角色 | 权重 | 立场 | 置信度 | 核心理由 | 改变观点的条件 |

## 2. 关键争议点

## 3. 交叉辩论
### 争议一：...
- A 质疑：...
- B 回应：...
- 主持人判断：回应削弱/维持/增强了原观点，因为...

## 4. 观点修正
| 角色 | 初始观点 | 修正后观点 | 原因 |

## 5. 最终一句话建议
| 角色 | 一句话建议 |

## 6. 加权投票
| 方向 | 原始票数 | 加权票数 | 代表角色 |

## 7. 主持人综合意见
- 综合立场：...
- 更适合：...
- 不适合：...
- 触发买入/加仓条件：...
- 触发减仓/回避条件：...

## 8. 必须继续验证的数据

## 9. 可保存的预测记录
```json
{...}
```
```

### Debate transcript style

Use this when the user wants to see argument and personality:

```markdown
主持人：...
股权分析师：...
空头研究员（打断）：我不同意，问题在于...
风险经理：我支持空头的一半观点，但不同意...
技术分析师：你们都忽略了价格已经...
```

Keep it sharp but professional. Do not make roles theatrical to the point of lowering analytical quality.

## Moderator synthesis rules

When synthesizing:

1. Separate time horizons. A stock can be long-term attractive and short-term unattractive.
2. Separate company quality from stock price attractiveness.
3. Separate evidence from assumption.
4. Highlight the strongest opposing argument to the final conclusion.
5. Convert the conclusion into conditional actions, not absolute commands.
6. Include a risk note that this is not personalized financial advice.

## Quick-start examples

User: `用投委会模式分析一下 NVDA，周期 6 个月，激进风险偏好，轮数 5。`

Use 5 rounds, include role debate, and produce a prediction record.

User: `复盘上次对 600519 的判断，实际跑赢沪深300，更新角色权重。`

Ask for or locate the saved prediction record, apply the update rule, and return old/new weights.
