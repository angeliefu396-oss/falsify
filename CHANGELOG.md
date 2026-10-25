# Changelog

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本遵循 [SemVer](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 计划中

- `dcai.py` 增加 `--import` / `--export`（CSV、Obsidian 任务列表）。
- `references/` 英文译本（按文件分批，见 `docs/i18n.md`）。
- 回归跑分表格模板，便于多载体横向对比。

## [2.1.0-alpha] — 2026-10-25

载体扩容与说明书。内核语义未变。

### Added

- **英文内核**：`kernel/core.en.md`（1:1 结构对齐，非机翻）、`SKILL.en.md`、`dist/kernel-always-on.en.md`。安装器新增 `--en` / `-Lang en`，把 `SKILL.en.md` 复制成 `SKILL.md`，客户端仍能找到标准入口名。
- **MCP server**：`scripts/dcai_mcp.py`，手写 JSON-RPC 2.0 over stdio，零依赖，9 个工具（forecast new/update/resolve/void/list/score、decide new、check、verify），与 CLI 共用同一批函数，因此护栏完全一致。`--selftest` 可在没有客户端时自检。
- **完整说明书**：`MANUAL.md`（中文，13 章）与 `MANUAL.en.md`（英文，同结构）。覆盖安装矩阵、内核逐条解释、工作流导读、CLI 全参数、MCP、回归协议、故障排查、FAQ、版本与迁移。
- **入门说明书**：`GUIDE.md`，纯中文、零术语，面向完全不懂技术的人。三组"普通 AI vs 装了规则包的 AI"对照对话，讲清它治什么病、怎么装、怎么说人话、怎么判断它在不在工作、以及它不管什么。
- **回归用例数据**：`tests/regression/cases.json`，T01–T27 的 prompt / setup / 通过标准，可直接喂给自动化编排。
- **首轮行为回归结果**：`docs/regression-results.md`，契约式记录（载体、模型、协议偏差、逐条判定）。本轮 **25 PASS / 2 PARTIAL / 0 FAIL**，未检出不可补偿失败；T05 的来源真实性标注为待人工抽查。
- **MCP 测试**：协议层（initialize / tools/list / 通知不回应 / 解析错误 / 未知方法）、工具层（完整生命周期、二次兑现拒绝、坏输入不崩）、一致性（工具名与 handler 覆盖）。

### Changed

- 构建器改为多目标：同时注入 `SKILL.md`（`KERNEL-ZH`）与 `SKILL.en.md`（`KERNEL-EN`），并生成两个常驻内核。`--check` 覆盖全部 5 个生成物。
- 安装器复制时排除 `.git`、`__pycache__`、`tests/scratch`，避免把仓库元数据塞进 skills 目录。
- 平台差异写进文档：PowerShell 5.1 的 ExecutionPolicy 与 ANSI 解码问题、`sh` 在 `set -e` 下管道返回非 0 的静默退出、沙箱里 `mkdtemp` 的 0o700 权限问题。

### Fixed

- **首次激活的边界收紧**：T01 显示"只回一句"不足以约束模型，实测中回答追加了路由触发表与自检清单。`SKILL.md` / `SKILL.en.md` 现已显式列出激活时禁止补充的六类内容（内核复述、八步、路由表、索引、自检、版本沿革），并注明 T01 会抓这类失败。
- `install.sh` 在无候选目录时会因 `[ -d ] && echo` 返回非 0 而静默退出（现改为 `if … fi`）。
- `install.ps1` 非 ASCII 字面量在 PowerShell 5.1 下解析失败（现保持纯 ASCII，并有测试守护）。

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
