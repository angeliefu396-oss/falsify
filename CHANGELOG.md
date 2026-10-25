# Changelog

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本遵循 [SemVer](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 计划中

- 英文内核译本（`kernel/core.en.md` + `dist/` 双语单文件）。
- MCP server 包装（`scripts/dcai_mcp.py`），把 `forecast` / `decide` 暴露为工具。
- `dcai.py` 增加 `--import` / `--export`（CSV、Obsidian 任务列表）。
- 回归测试跑分表格模板，便于不同载体横向对比。

## [2.0.0-alpha] — 2026-10-25

首个可移植版本。相对原始 ChatBox Copilot + 知识库包的重构，不是文案润色。

### Added

- **三层架构**：常驻内核（`kernel/core.md`）、按需工作流（`references/`，19 个文件）、强制层（`scripts/dcai.py`）。
- **四载体**：Agent Skills（`SKILL.md`）、`AGENTS.md` 常驻段、单文件提示词（`dist/dcai-single-file.md`）、命令行。
- **单一真源构建**：`scripts/build.py` 把内核注入 `SKILL.md` 并生成 `dist/`；`--check` 供 CI 检测漂移。
- **强制层 CLI**：`forecast new/update/resolve/void/score/list`、`decide new`、`check`、`verify`。
  - 概率所有权校验（AI 只能给范围，不能落数）。
  - 只追加更新；已兑现卡封闭；禁止二次兑现与事后改兑现标准。
  - 封印哈希链 + 账本重放对账，检测手工改账。
  - Brier 初始/最终、更新增益、同题集基线、分档校准（带 N 与小样本护栏）。
- **测试**：46 个测试覆盖 Brier 数学、卡片校验、CLI 护栏、篡改检测、单源一致性、索引完整性、文档存在性。
- **CI**：GitHub Actions，Ubuntu + Windows × Python 3.9/3.12。
- **文档**：架构（三层与软硬边界判据）、可移植性（各载体安装与降级行为）、用法配方（六个高频场景）。

### Changed

- 知识库从"检索式分块"改为"锚点文件按需读取"，消除原版依赖向量召回、关键规则整轮缺席的风险。
- 内核从两份（系统提示词 + 知识库）收敛为一份真源，生成物由 CI 守卫，消除双份漂移。
- 回归测试记录字段改为载体无关（原版绑定 ChatBox 的 Copilot / 知识库选择项）。
- `01-kernel-full.md` 与 `05-partner-audit.md` 等文件沿用原编号语义，便于与原包对照。

### Fixed

- 原版将"自然交互"与"证据质量"并列为评分项，导致对文风过拟合；现明确表达层只负责可读性。
- 原版允许关键主张"隐式、自然表达"，对能力一般的模型等于省略；现严肃任务默认显式分层。
- 原版 Brier 0.25 有被当作通用随机基线的风险；现报告层与内核双重标注。

### Notes

- `v2.0-alpha` 表示规则与结构完成、强制层有测试，**行为效果仍需逐载体 + 逐模型回归**。不声称已冻结，不声称提示词能提供技术隔离或自动记忆。
- 预测校准规则依据 Mellers 等（2014, 2015）与 Gneiting & Raftery（2007）；适用限制见 `references/17-references.md`。
