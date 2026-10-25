# MCP：把强制层接进你的客户端

`scripts/dcai_mcp.py` 是一个零依赖的 stdio MCP server（手写 JSON-RPC 2.0）。它不做推理，只做**拒绝**：概率所有权、只追加、兑现封闭、封印链、Brier 与小样本护栏。规则和 CLI 完全一致，因为工具直接调用同一批函数。

## 配置

Claude Desktop / Claude Code / 任意 MCP host：

```json
{
  "mcpServers": {
    "dcai": {
      "command": "python",
      "args": ["/absolute/path/to/dcai-unified-kernel/scripts/dcai_mcp.py"],
      "env": { "DCAI_HOME": "/absolute/path/to/your/ledger" }
    }
  }
}
```

Windows 上 `command` 可能要写 `py` 或完整的 `python.exe` 路径。`DCAI_HOME` 决定账本落盘位置，不设就是进程当前目录下的 `dcai/`。

自检（不需要客户端）：

```bash
python scripts/dcai_mcp.py --selftest
```

期望输出包含 `tools: 9 [...]`、`protocolVersion`、一次 `tools/call` 的返回，以及未知方法返回 `-32601`。

## 工具

| 工具 | 作用 | 关键约束 |
|---|---|---|
| `dcai_forecast_new` | 建预测卡 | `p` 是**用户**概率；`ai_low/ai_high` 是模型范围，分字段存 |
| `dcai_forecast_update` | 追加一次更新 | 旧值保留；已兑现/已作废的卡拒绝 |
| `dcai_forecast_resolve` | 兑现一次 | 只能一次，落封印；二次兑现拒绝 |
| `dcai_forecast_void` | 作废 | 不计分，但计入作废率 |
| `dcai_forecast_list` | 列表 | — |
| `dcai_forecast_score` | 校准报告 | 无基线会警告；N<30 标"仅描述" |
| `dcai_decide_new` | 决策记录骨架 | 已存在 ID 拒绝覆盖 |
| `dcai_check` | 规则校验 | 概率所有权 / 更新链 / 无结果回填 / 时间顺序 |
| `dcai_verify` | 封印链 + 账本重放 | 改卡片、改账本、凭空加卡都能指到具体位置 |

返回一律是 MCP 的 `{"content":[{"type":"text","text":...}],"isError":bool}`；拒绝是 `isError: true` 加一句人类可读的理由，不会抛协议错误。

## 给 agent 的用法提示

在系统提示或工具描述里加一句，效果最好：

> 记录任何预测前先调用 `dcai_forecast_new`；用户给出概率前，不要自己填 `p`。用户说"改一下"时调用 `dcai_forecast_update`，不要说"已更新"然后自己编数字。复盘时调用 `dcai_forecast_score`，并把警告原样转述给用户。

## 边界

- 只读/只写本地文件，不联网，不上报。
- 不做加密：账本是明文 JSON + 哈希链。哈希链能证明**被改过**，不能防读取。
- 不替代判断：它只保证预测记录不被污染，不保证预测内容有价值。
- 协议版本按客户端请求回显；只实现了 `initialize` / `ping` / `tools/list` / `tools/call`，没有 resources、prompts、sampling。
