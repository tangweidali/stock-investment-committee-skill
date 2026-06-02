<!--
╔══════════════════════════════════════════════════════════════════════╗
║  DreamSeed 种梦计划 — AI创造者大赛  官方 README 模板                ║
║                                                                      ║
║  使用说明：                                                          ║
║  1. 将本模板放在参赛仓库根目录 README.md 的顶部                       ║
║  2. 头图使用 DreamField 官方公开活动图片地址                         ║
║  3. 请保留 DREAMFIELD_README_HEADER_START / END 标识                 ║
║  4. 分割线以下供创作者自由编写项目内容                               ║
╚══════════════════════════════════════════════════════════════════════╝
-->

<!-- DREAMFIELD_README_HEADER_START -->

<p align="center">
  <a href="https://www.dreamfield.top">
    <img src="https://www.dreamfield.top/dream-field/contest-readme/assets/dreamseed-readme-banner.png" alt="DreamSeed 种梦计划参赛作品" width="100%" />
  </a>
</p>

<!-- DREAMFIELD_README_HEADER_END -->

# Stock Investment Committee Skill

一个多角色股票投资委员会辩论工具，用于将股票、代码、公司或任何投资想法转化为结构化的多方辩论。

## 功能特性

- **多角色辩论**：12个预置角色（基本面分析师、技术分析师、宏观策略师、风险经理、空头研究员、价值投资者、华尔街交易员、银行高管、金融学教授、战略投资者、行业专家、散户情绪观察者）
- **4轮深度辩论**：初始观点 → 关键争议点 → 交叉质询 → 最终投票与合成
- **权重学习机制**：根据历史预测准确率自动调整角色权重
- **中立惩罚**：连续中立预测的角色会受到权重惩罚
- **外部模型支持**：可配置每个角色使用不同的外部AI模型
- **Markdown/HTML报告**：生成结构化报告，包含执行证明
- **预测记录与复盘**：保存预测记录，支持后续更新权重

## 使用方法

### 基本使用

```bash
# 使用 uv 运行脚本
uv run python scripts/resolve_output_dir.py --choice desktop --asset "AAPL" --date 2026-06-02

# 初始化状态
uv run python scripts/committee_state.py init --state ./committee_state.json --output-weights ./committee_weights.json

# 运行预检
uv run python scripts/preflight.py --config references/config-example.json --task "分析 AAPL" --output preflight.json

# 调用外部角色模型
uv run python scripts/run_role_model.py --config references/config-example.json --role technical_analyst --task "分析 AAPL" --output role_outputs/technical_analyst.json

# 生成报告
uv run python scripts/render_report_html.py --input report.md --output report.html --title "投资委员会报告"
```

### 配置示例

```json
{
  "committee": {
    "rounds": 4,
    "output_style": "full",
    "language": "zh-CN",
    "data_mode": "use_available_tools"
  },
  "model_defaults": {
    "base_url": "inherit",
    "api_key": "inherit",
    "model": "inherit"
  },
  "roles": {
    "fundamental_analyst": {"weight": 1.0, "model": "inherit"},
    "technical_analyst": {"weight": 1.0, "model": "inherit"}
  },
  "report": {
    "save_markdown": true,
    "save_html": true,
    "output_dir": "committee_reports"
  }
}
```

## 角色说明

| 角色ID | 名称 | 立场倾向 | 核心关注点 |
|--------|------|----------|------------|
| fundamental_analyst | 股权基本面分析师 | 平衡 | 营收、利润率、现金流、估值、财务报表质量 |
| technical_analyst | 技术分析师 | 价格优先 | 趋势、成交量、均线、支撑/阻力、动量 |
| macro_strategist | 宏观策略师 | 自上而下 | 利率、通胀、汇率、流动性、政策、行业β |
| risk_manager | 风险经理 | 怀疑主义 | 下行风险、流动性、集中度、回撤、仓位管理 |
| short_seller | 空头/ forensic 分析师 | 看空 | 会计质量、失效叙事、渠道填充、杠杆、治理 |
| value_investor | 长期价值投资者 | 耐心 | 护城河、业主收益、管理层、内在价值、安全边际 |
| wall_street_trader | 高级华尔街交易员 | 战术性 | 资金流向、催化剂、定位、波动率、止损位 |
| bank_executive | 银行高管 | 信用周期 | 融资渠道、债务到期、契约压力、交易对手风险 |
| finance_professor | 金融学教授 | 中立 | 资产定价、因子暴露、资本成本、实证基准率 |
| strategic_investor | 战略投资者 | 战略 | 并购价值、资产稀缺性、产业协同、控制溢价 |
| sector_specialist | 行业专家 | 行业认知 | 竞争结构、监管、供应链、单位经济效益 |
| retail_sentiment_observer | 散户情绪观察者 | 情绪感知 | 社交叙事、炒作、恐惧、反射性、拥挤交易 |

## 权重机制

- **学习率**：0.08（正确预测时权重增加，错误时减少）
- **权重范围**：0.40 ~ 2.50
- **中立惩罚**：连续3次中立预测后，每次更新权重下降5%
- **替换候选**：权重低于最低阈值的角色标记为替换候选

## 目录结构

```
stock-investment-committee/
├── SKILL.md                    # 技能定义文件
├── README.md                   # 项目说明
├── .gitignore                  # Git忽略配置
├── committee_reports/          # 报告输出目录
│   └── <task_dir>/
│       ├── prediction.json
│       ├── report.md
│       ├── report.html
│       └── ...
├── evals/                      # 评估测试
│   └── evals.json
├── references/                 # 参考配��
│   └── config-example.json
└── scripts/                    # 工具脚本
    ├── committee_state.py
    ├── extract_prediction_from_html.py
    ├── preflight.py
    ├── render_report_html.py
    ├── resolve_output_dir.py
    ├── run_role_model.py
    └── update_weights.py
```

## 在 Claude Code 中使用

1. 将此 skill 复制到 Claude Code 的 skills 目录
2. 使用 `/stock-investment-committee` 命令调用
3. 提供分析标的（股票代码、公司名称、加密货币对等）
4. 指定市场、投资期限、风险偏好

示例输入：
```yaml
ticker: "NVDA"
market: "US"
horizon: "6 months"
risk_profile: "aggressive"
```

## 合规声明

本工具仅用于研究和教育目的，不构成个性化投资建议。投资有风险，入市需谨慎。

---

**DreamSeed 种梦计划参赛作品**