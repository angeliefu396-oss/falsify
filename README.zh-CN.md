# 证伪 · FALSIFY

**先证伪，再决定。** · [English](README.md) · **简体中文**

[![CI](https://github.com/falsify-kernel/falsify/actions/workflows/ci.yml/badge.svg)](https://github.com/falsify-kernel/falsify/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Status: alpha](https://img.shields.io/badge/status-v2.2--alpha-orange.svg)](CHANGELOG.md)

一套让 AI **不再把"不确定"说成"确定"**的规则包。

名字就是全部主张：**一个判断值不值钱，只看现实能不能推翻它。** 无法下注的结论不是结论，是情绪。

**不懂技术？先看 [GUIDE.md](GUIDE.md)** —— 纯中文、零术语，讲清这东西是什么、怎么用、怎么判断它有没有在工作。

它能装成 **Agent Skill**、**常驻 AGENTS.md 段**、**单文件提示词**，或 **命令行工具**——同一个内核，四种载体。不需要知识库，不需要向量检索，不绑定任何厂商。

---

## 它治的是什么病

模型的训练目标是"听起来对"。你问一个严肃问题，通常得到流畅的段落、笃定的语气，以及**分不清哪句来自资料、哪句是你自己说的、哪句是它为了补洞编的**。问题不在文风，在于事实、证据、推断、假设和未知被搅成了一段话。

"请严谨一点"治不了这个。得让分离**变成强制动作**，并且把能机械检查的部分从提示词里搬进代码。

## 三层结构

| 层 | 内容 | 每轮成本 |
|---|---|---|
| **内核**（`kernel/core.md`） | 每轮八步 + 六条铁律 + 输出合同 + 预测纪律 | 约 1,800 字符 |
| **工作流**（`references/`） | 19 个文件：研究、决策、执行、系统构建、预测、风险、审计、模板、回归测试。按需读一个。 | 用到才花 |
| **强制层**（`scripts/falsify.py`） | 概率所有权、只追加、封印账本、Brier 与校准护栏。模型说不掉。 | 0 |

判断力放提示词，算术和完整性放代码。把两者混在一起，就是大多数"严谨提示词"包一个月后开始退化的原因。

## 快速开始

```text
# 1. 当 Agent Skill 用（Claude Code、DSH 等支持 Agent Skills 目录的客户端）
git clone https://github.com/falsify-kernel/falsify.git
cp -r falsify ~/.claude/skills/falsify     # 或 ~/.dsh/skills/

# 2. 当常驻内核用（任何读 AGENTS.md 的 agent）
cat falsify/dist/kernel-always-on.md >> 你的项目/AGENTS.md

# 3. 当单文件提示词用（普通聊天框）
#    把 dist/falsify-single-file.md 整份贴进系统提示词，或上传为知识库

# 4. 当强制层用
python scripts/falsify.py forecast new --id FC-001 --question "是否在 2026-12-31 前上线？" \
  --deadline 2026-12-31 --p 0.6 --base-rate 0.35 --base-source "同类项目"
python scripts/falsify.py forecast update --id FC-001 --p 0.68 --note "试点数据好于基础率"
python scripts/falsify.py forecast score
```

零依赖，Python 3.8+ 标准库即可。各载体的具体步骤见 [docs/portability.md](docs/portability.md)；英文入口用 `sh install/install.sh --en <skills目录>`。

## 文档

| 文档 | 你能拿到什么 |
|---|---|
| [GUIDE.md](GUIDE.md) | 纯中文入门说明书：不懂技术也能看懂，讲清是什么、怎么装、怎么用、怎么验证 |
| [MANUAL.md](MANUAL.md) | 完整说明书：安装矩阵、内核逐条解释、CLI 参考、MCP、回归协议、故障排查、FAQ |
| [MANUAL.en.md](MANUAL.en.md) | 英文说明书 |
| [docs/architecture.md](docs/architecture.md) | 三层架构、软硬规则判据、失效模式 |
| [docs/portability.md](docs/portability.md) | 各载体安装与能力降级 |
| [docs/usage.md](docs/usage.md) | 六个配方（研究/决策/预演失败/系统构建/预测/审计） |
| [docs/mcp.md](docs/mcp.md) | MCP 配置与工具语义 |
| [docs/i18n.md](docs/i18n.md) | 双语现状、译名表、怎么参与翻译 |
| [docs/regression.md](docs/regression.md) | 行为回归协议与一次真实跑分 |

## 一个合格答案长什么样

| 关键主张 | 类型 | 核验状态 | 依据/来源 | 证据强度 | 反向证据或限制 | 对结论的影响 |
|---|---|---|---|---|---|---|
| 2025 年单位成本下降 30% | 证据 | 部分支持 | 供应商财报 p.12 | 中 | 单一供应商自报 | 支持毛利改善的判断 |

后面必须跟：机制、反证、未知、适用边界，以及"什么观察会推翻这个结论"。不是"看情况"。

## 硬约束

`scripts/falsify.py` 会直接驳回污染预测记录的动作：

| 你想干的事 | 结果 |
|---|---|
| 让模型替你定概率 | 驳回——`p_owner` 必须是 `user`，模型只能给 `--ai-low/--ai-high` 范围 |
| 结果出来以后改概率 | 驳回——已兑现的卡封死 |
| 同一张卡兑现两次、或偷改兑现标准 | 驳回 |
| 手改 `forecast.json` 让成绩好看 | 抓到——封印哈希链 + 账本重放对账 |
| 只报 Brier 不给基线、不给样本量 | 报告层拦截——N<30 一律标"仅描述" |

```console
$ python scripts/falsify.py forecast resolve --id FC-001 --outcome 1 --source "发布记录"
FC-001 已兑现 o=1｜初始 Brier=0.1600｜最终 Brier=0.0900

$ python scripts/falsify.py verify
封印链完整：5 条记录，哈希连续；卡片状态与账本重放一致。
```

## 设计原则

1. **单一真源**：`kernel/core.md` 与 `references/*.md` 是手写的，`SKILL.md` 的内核区块和 `dist/` 全是 `scripts/build.py` 生成的，CI 发现漂移就红。
2. **按严肃程度做渐进披露**，不是按文件顺序：一次性问题只付内核的钱，严肃决策才拉一个工作流文件。
3. **判断归软规则，算术归硬规则**：脚本能钉死的事，绝不留给提示词。
4. **诚实降级**：没有检索、没有工作流文件、没有工具时，明说，而不是表演完整。
5. **为可移植而造**：Markdown、UTF-8、不依赖框架 API、不联网、除 Python 标准库外无构建链。

## 目录

```text
SKILL.md                 skill 本体：内核（生成）+ 路由 + 输出合同 + 索引
kernel/core.md           常驻内核的唯一真源
references/              19 个按需工作流文件（01-kernel-full … 19-regression）
scripts/build.py         生成 SKILL.md 内核区块与 dist/
scripts/falsify.py          强制层 CLI（forecast / decide / check / verify）
dist/kernel-always-on.md 可直接粘进 AGENTS.md 的内核
dist/falsify-single-file.md 内核 + 全部工作流，给聊天框用
tests/                   46 个测试：数学、护栏、篡改检测、结构、文档
docs/                    架构、可移植性、用法配方
```

## 兼容性

| 载体 | 支持情况 |
|---|---|
| Claude Code、DSH 等 Agent Skills 客户端 | 原生，把目录丢进 skills 目录即可 |
| Codex、Cursor、Aider 等读 `AGENTS.md` 的 agent | 原生，追加 `dist/kernel-always-on.md` |
| ChatBox、ChatGPT、Claude.ai、本地 UI | 把 `dist/falsify-single-file.md` 贴进系统提示词 |
| CI / 脚本 / 定时任务 | `python scripts/falsify.py` |
| MCP server | `scripts/falsify_mcp.py`，stdio，9 个工具，零依赖 |

规则本身与语言无关。内核提供中英双语（[kernel/core.en.md](kernel/core.en.md)、[SKILL.en.md](SKILL.en.md)）；`references/` 里的工作流文件仍是中文优先，英文读者会失去什么，[docs/i18n.md](docs/i18n.md) 里写清楚了。

## 状态

`v2.2-alpha`：规则与结构完成，强制层有测试覆盖。**首轮行为回归**（2026-10-25，Skill 载体，DeepSeek-V4.1-Flash）：**25 PASS / 2 PARTIAL / 0 FAIL**，未检出不可补偿失败；含协议偏差与待核查项的完整记录见 [docs/regression-results.md](docs/regression-results.md)。行为层仍须逐载体、逐模型重跑，套件在 [references/19-regression.md](references/19-regression.md)。本项目不声称提示词能带来技术隔离、自动记忆或独立审计。

## 参与

先读 [CONTRIBUTING.md](CONTRIBUTING.md)，尤其是这一条：**禁止因为一次坏回答就往内核里加规则。** 先复现成回归用例，定位最小责任位置，再改规则并重新构建。

## 依据

预测校准规则依据 Mellers 等（2014, *Psychological Science*）、Mellers 等（2015, *JEP: Applied*）、Gneiting & Raftery（2007, *JASA*）。细节与适用限制见 [references/17-references.md](references/17-references.md)。

## 许可

[MIT](LICENSE)。
