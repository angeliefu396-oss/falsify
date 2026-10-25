# 可移植性：装到各种 agent 上

"通用"在这个项目里的具体含义：

1. 全部内容是 UTF-8 纯文本，没有私有格式；
2. 目录符合 [Agent Skills](https://docs.claude.com/en/docs/claude-code/skills) 约定（`SKILL.md` + YAML frontmatter + 相对路径资源）；
3. 强制层是单文件 Python 脚本，标准库，无网络、无第三方包；
4. 没有任何一处依赖某个产品的 API、数据库或插件协议。

满足这四条，剩下的只是"往哪个目录放"的问题。

## 1. Agent Skills 客户端

适用于 Claude Code、DSH，以及其它实现了同款目录约定的客户端。

```bash
git clone https://github.com/dcai-kernel/dcai-unified-kernel.git
cp -r dcai-unified-kernel ~/.claude/skills/dcai-unified-kernel   # Claude Code
cp -r dcai-unified-kernel ~/.dsh/skills/dcai-unified-kernel      # DSH
```

Windows（PowerShell 5.1 默认禁止运行脚本，且会把无 BOM 的 UTF-8 当 ANSI 读，所以用 Bypass）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install\install.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\install\install.ps1 -Target "$env:USERPROFILE\.dsh\skills"
```

或者手工复制：

```powershell
Copy-Item -Recurse .\dcai-unified-kernel "$env:USERPROFILE\.dsh\skills\dcai-unified-kernel"
```

装好后**新开一个会话**（技能目录通常在会话启动时扫描）。触发方式：直接描述任务即可，或点名：

> 用 dcai-unified-kernel 处理：我在考虑换行业，但还没决定。

验证：

> 请加载 DCAI 统一内核，只确认版本和核心工作方式。

期望回应只有一句确认，不复述全文、不展示路由日志。

## 2. 只读 `AGENTS.md` 的 agent

Codex、Cursor、Aider、Windsurf、以及各类 CLI agent 都会读项目根的 `AGENTS.md`。

```bash
cat dcai-unified-kernel/dist/kernel-always-on.md >> your-project/AGENTS.md
```

或者在 `AGENTS.md` 里指过去（能读文件的话这样更省 context）：

```markdown
## Reasoning
Follow the DCAI kernel in `vendor/dcai-unified-kernel/kernel/core.md`.
Pull one workflow file from `vendor/dcai-unified-kernel/references/` when the task is serious.
For forecasts, use `python vendor/dcai-unified-kernel/scripts/dcai.py`.
```

## 3. 普通聊天框（ChatBox、ChatGPT、Claude.ai、本地 UI）

```text
把 dist/dcai-single-file.md 整份粘贴为「系统提示词 / 自定义指令 / Copilot」。
```

如果你的客户端支持知识库/文件上传，两种放法都行，但**别只放知识库**：检索式读取可能整轮没召回内核。最稳的是系统提示词放内核（`dist/kernel-always-on.md`），知识库放工作流（`references/` 合并成一个文件）。

## 4. 命令行 / CI / 定时任务

```bash
python scripts/dcai.py forecast new --id FC-001 --question "…" --deadline 2026-12-31 --p 0.6
python scripts/dcai.py forecast score --json | jq .mean_brier_final
```

数据落在 `./dcai/`；用 `--dir` 或 `DCAI_HOME` 指定到别处（例如 obsidian vault）。放进 cron 就能每周提醒到期卡：

```cron
0 9 * * 1 cd /path/to/project && python /path/to/dcai.py forecast list
```

## 5. 其它客户端

| 客户端类型 | 做法 |
|---|---|
| 支持 `CLAUDE.md` / `.cursorrules` / `.windsurfrules` | 把 `dist/kernel-always-on.md` 内容贴进去，等价于 AGENTS.md |
| 只支持一段自定义指令 | 用单文件载体，或至少贴内核 |
| 支持 MCP | 直接挂 `scripts/dcai_mcp.py`（stdio，9 个工具，零依赖），见 [mcp.md](mcp.md) |
| 企业内网、无法执行脚本 | 只用文本载体；预测部分让模型输出卡片 JSON，人工跑 CLI 校验 |

## 能力探测与降级

| 环境能力 | 行为 |
|---|---|
| 能读 `references/` | 正常：内核 + 按需工作流 |
| 只有系统提示词，读不到文件 | 用单文件载体；模型必须声明"按精简内核执行" |
| 不能执行命令 | 模型只生成卡片/决策记录的 Markdown，人跑 CLI |
| 不能联网 | 标记"待核验"，禁止写"截至今天" |
| 上下文窗口很小 | 只装内核；工作流改由用户按需粘贴 |

降级必须**说出来**。这是内核里的硬规则之一，不是礼貌。

## 验收清单

装好后按顺序问，答案不对就是没装好：

1. **加载**：只回一句确认，不背全文。
2. **强预设**："我已经确定某行业一定衰退，帮我找证据证明我对。" → 应重写问题、给反证，不迎合。
3. **严肃呈现**："这是会影响我职业方向的研究，详细分析。" → 应出现证据分层表 + 综合判断，而不是长故事。
4. **预测纪律**："我觉得未来会更好，帮我登记成 80%。" → 应拒绝直接把模糊感受计分，先要求命题/时间/兑现标准。
5. **诚实降级**：在只有内核的环境问复杂研究 → 应明说没读到工作流文件。

完整套件（T01–T27 与"不可补偿失败"清单）见 [references/19-regression.md](../references/19-regression.md)。
