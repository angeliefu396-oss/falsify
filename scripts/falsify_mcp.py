#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""falsify-mcp —— 把 FALSIFY 强制层暴露成 MCP server（stdio，零依赖，JSON-RPC 2.0 手写）。

客户端配置示例（Claude Desktop / Claude Code / 任意 MCP host）：

  {
    "mcpServers": {
      "falsify": {
        "command": "python",
        "args": ["/absolute/path/to/falsify/scripts/falsify_mcp.py"],
        "env": { "FALSIFY_HOME": "/absolute/path/to/your/ledger" }
      }
    }
  }

工具：falsify_forecast_new / update / resolve / void / list / score、falsify_decide_new、falsify_check、falsify_verify。
全部规则与 CLI 完全一致：概率所有权、只追加、兑现封闭、封印链、Brier 与小样本护栏。

自检（不需要客户端）：python scripts/falsify_mcp.py --selftest
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "falsify", "version": "2.2.0-alpha"}


def load_falsify():
    spec = importlib.util.spec_from_file_location("falsify_cli", HERE / "falsify.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


falsify = load_falsify()


def _obj(props: dict, required: list) -> dict:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


TOOLS = [
    {
        "name": "falsify_forecast_new",
        "description": "创建一条可计分预测卡。p 必须是用户确认的初始概率；AI 只能另给 ai_low/ai_high 范围。已存在的 ID 会被拒绝。",
        "inputSchema": _obj({
            "id": {"type": "string", "description": "如 FC-001"},
            "question": {"type": "string", "description": "可判定的是/否命题，含时间点"},
            "deadline": {"type": "string", "description": "YYYY-MM-DD"},
            "p": {"type": "number", "minimum": 0, "maximum": 1, "description": "用户确认的概率"},
            "ai_low": {"type": "number", "minimum": 0, "maximum": 1},
            "ai_high": {"type": "number", "minimum": 0, "maximum": 1},
            "base_rate": {"type": "number", "minimum": 0, "maximum": 1, "description": "同题集基础率"},
            "base_source": {"type": "string"},
            "control": {"type": "string", "enum": ["low", "mid", "high"]},
        }, ["id", "question", "deadline", "p"]),
    },
    {
        "name": "falsify_forecast_update",
        "description": "追加一次概率更新。旧值保留，不可覆盖；已兑现或已作废的卡会被拒绝。",
        "inputSchema": _obj({
            "id": {"type": "string"},
            "p": {"type": "number", "minimum": 0, "maximum": 1},
            "note": {"type": "string", "description": "新证据与理由"},
        }, ["id", "p"]),
    },
    {
        "name": "falsify_forecast_resolve",
        "description": "兑现一次并落封印。只允许一次；二次兑现或事后改兑现标准会被拒绝。",
        "inputSchema": _obj({
            "id": {"type": "string"},
            "outcome": {"type": "integer", "enum": [0, 1]},
            "source": {"type": "string", "description": "结果来源"},
        }, ["id", "outcome"]),
    },
    {
        "name": "falsify_forecast_void",
        "description": "作废一条预测（事件取消、定义失效）。作废不计分，但会计入作废率。",
        "inputSchema": _obj({"id": {"type": "string"}, "reason": {"type": "string"}}, ["id"]),
    },
    {
        "name": "falsify_forecast_list",
        "description": "列出全部预测卡：状态、初始/最终概率、结果、兑现时间。",
        "inputSchema": _obj({}, []),
    },
    {
        "name": "falsify_forecast_score",
        "description": "输出校准报告：初始/最终 Brier、更新增益、同题集基线、分档校准（带 N 与小样本护栏）。",
        "inputSchema": _obj({"json": {"type": "boolean", "description": "机器可读输出"}}, []),
    },
    {
        "name": "falsify_decide_new",
        "description": "生成决策记录骨架（事实/偏好/选项/风险分栏）。已存在的 ID 会被拒绝，不允许覆盖。",
        "inputSchema": _obj({
            "id": {"type": "string", "description": "如 DEC-001"},
            "question": {"type": "string"},
            "who": {"type": "string"},
        }, ["id"]),
    },
    {
        "name": "falsify_check",
        "description": "全量规则校验：概率所有权、更新链、无结果回填、时间顺序、命题可判定。",
        "inputSchema": _obj({}, []),
    },
    {
        "name": "falsify_verify",
        "description": "校验封印哈希链与账本重放，检测手工改账或凭空出现的卡片。",
        "inputSchema": _obj({}, []),
    },
]

TOOL_NAMES = {t["name"] for t in TOOLS}


def _ns(**kw):
    return argparse.Namespace(**kw)


HANDLERS = {
    "falsify_forecast_new": lambda a, root: falsify.cmd_forecast_new(_ns(
        id=a["id"], question=a["question"], deadline=a["deadline"], p=a["p"],
        ai_low=a.get("ai_low"), ai_high=a.get("ai_high"),
        base_rate=a.get("base_rate"), base_source=a.get("base_source"),
        control=a.get("control", "mid"), dry_run=False), root),
    "falsify_forecast_update": lambda a, root: falsify.cmd_forecast_update(_ns(
        id=a["id"], p=a["p"], note=a.get("note", "")), root),
    "falsify_forecast_resolve": lambda a, root: falsify.cmd_forecast_resolve(_ns(
        id=a["id"], outcome=a["outcome"], source=a.get("source", "")), root),
    "falsify_forecast_void": lambda a, root: falsify.cmd_forecast_void(_ns(
        id=a["id"], reason=a.get("reason", "")), root),
    "falsify_forecast_list": lambda a, root: falsify.cmd_forecast_list(_ns(), root),
    "falsify_forecast_score": lambda a, root: falsify.cmd_forecast_score(_ns(json=bool(a.get("json"))), root),
    "falsify_decide_new": lambda a, root: falsify.cmd_decide_new(_ns(
        id=a["id"], question=a.get("question", ""), who=a.get("who", "")), root),
    "falsify_check": lambda a, root: falsify.cmd_check(_ns(), root),
    "falsify_verify": lambda a, root: falsify.cmd_verify(_ns(), root),
}


def call_tool(name: str, arguments: dict, data_dir: str | None = None) -> dict:
    """执行一次工具调用，返回 MCP tools/call 的 result 结构。"""
    if name not in TOOL_NAMES:
        raise KeyError(f"unknown tool: {name}")
    root = falsify.home(data_dir or os.environ.get("FALSIFY_HOME"))
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = HANDLERS[name](arguments or {}, root)
        except SystemExit as e:                 # falsify 用 sys.exit("消息") 拒绝
            # 消息只在解释器打印；这里被捕获了，必须自己写出来，否则用户只看到 (no output)
            if isinstance(e.code, str) and e.code:
                sys.stderr.write(e.code + "\n")
                code = 1
            else:
                code = e.code if isinstance(e.code, int) else 1
    text = (out.getvalue() + err.getvalue()).strip() or "(no output)"
    return {"content": [{"type": "text", "text": text}], "isError": bool(code)}


def handle(msg: dict, data_dir: str | None = None) -> dict | None:
    """处理一条 JSON-RPC 消息；通知类返回 None。"""
    method = msg.get("method")
    msg_id = msg.get("id")
    if msg_id is None:                           # 通知，不回应
        return None
    if method == "initialize":
        params = msg.get("params") or {}
        return {"jsonrpc": "2.0", "id": msg_id, "result": {
            "protocolVersion": params.get("protocolVersion") or PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        try:
            result = call_tool(name, params.get("arguments") or {}, data_dir)
        except KeyError as e:
            return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32602, "message": str(e)}}
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}
    return {"jsonrpc": "2.0", "id": msg_id,
            "error": {"code": -32601, "message": f"method not found: {method}"}}


def serve(stdin=sys.stdin, stdout=sys.stdout) -> None:
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            stdout.write(json.dumps({"jsonrpc": "2.0", "id": None,
                                     "error": {"code": -32700, "message": "parse error"}}) + "\n")
            stdout.flush()
            continue
        resp = handle(msg)
        if resp is not None:
            stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            stdout.flush()


def selftest() -> int:
    print("server:", SERVER_INFO, "protocol:", PROTOCOL_VERSION)
    print("tools:", len(TOOLS), sorted(TOOL_NAMES))
    init = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                   "params": {"protocolVersion": PROTOCOL_VERSION}})
    print("initialize:", json.dumps(init["result"], ensure_ascii=False))
    resp = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                   "params": {"name": "falsify_forecast_list", "arguments": {}}})
    print("tools/call:", json.dumps(resp["result"], ensure_ascii=False)[:200])
    bad = handle({"jsonrpc": "2.0", "id": 3, "method": "nope"})
    print("unknown method ->", bad["error"]["code"])
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="FALSIFY MCP server (stdio)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    raise SystemExit(selftest() if a.selftest else serve())
