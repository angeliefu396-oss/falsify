# -*- coding: utf-8 -*-
"""MCP server 测试：协议层 + 工具层 + 与 CLI 一致的护栏。

全部进程内调用 handle()/call_tool()，不开子进程、不用管道。
"""
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import unittest
import uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mcp = load("dcai_mcp", "scripts/dcai_mcp.py")


class ProtocolTest(unittest.TestCase):
    def test_initialize(self):
        r = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2024-11-05"}})
        self.assertEqual(r["result"]["protocolVersion"], "2024-11-05")
        self.assertEqual(r["result"]["serverInfo"]["name"], "dcai")
        self.assertIn("tools", r["result"]["capabilities"])

    def test_protocol_version_negotiation(self):
        r = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2025-06-18"}})
        self.assertEqual(r["result"]["protocolVersion"], "2025-06-18")

    def test_notification_has_no_response(self):
        self.assertIsNone(mcp.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_tools_list(self):
        r = mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = r["result"]["tools"]
        self.assertEqual(len(tools), 9)
        names = [t["name"] for t in tools]
        self.assertEqual(len(names), len(set(names)))
        for t in tools:
            self.assertIn("inputSchema", t)
            self.assertEqual(t["inputSchema"]["type"], "object")
            for req in t["inputSchema"].get("required", []):
                self.assertIn(req, t["inputSchema"]["properties"])

    def test_unknown_method(self):
        r = mcp.handle({"jsonrpc": "2.0", "id": 3, "method": "resources/list"})
        self.assertEqual(r["error"]["code"], -32601)

    def test_unknown_tool(self):
        r = mcp.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                        "params": {"name": "dcai_nope", "arguments": {}}})
        self.assertEqual(r["error"]["code"], -32602)

    def test_stdio_loop(self):
        lines = "\n".join([
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
            "{ not json",
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
        ]) + "\n"
        out = io.StringIO()
        mcp.serve(stdin=io.StringIO(lines), stdout=out)
        replies = [json.loads(l) for l in out.getvalue().strip().splitlines()]
        self.assertEqual(len(replies), 3)                       # 通知不回应
        self.assertEqual(replies[1]["error"]["code"], -32700)    # 解析错误
        self.assertEqual(replies[2]["id"], 2)


class ToolFlowTest(unittest.TestCase):
    def setUp(self):
        base = ROOT / "tests" / "scratch"
        base.mkdir(parents=True, exist_ok=True)
        self.dir = base / f"mcp_{uuid.uuid4().hex[:8]}"
        os.makedirs(self.dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def call(self, name, **args):
        return mcp.call_tool(name, args, data_dir=str(self.dir))

    def test_forecast_lifecycle(self):
        r = self.call("dcai_forecast_new", id="FC-1", question="是否在 2026-12-31 前上线？",
                      deadline="2026-12-31", p=0.6, base_rate=0.35)
        self.assertFalse(r["isError"], r["content"][0]["text"])
        self.assertIn("已登记 FC-1", r["content"][0]["text"])

        r = self.call("dcai_forecast_update", id="FC-1", p=0.68, note="灰度数据")
        self.assertFalse(r["isError"])
        self.assertIn("0.60 → 0.68", r["content"][0]["text"])

        r = self.call("dcai_forecast_resolve", id="FC-1", outcome=1, source="后台")
        self.assertFalse(r["isError"])
        self.assertIn("初始 Brier=0.1600", r["content"][0]["text"])

        r = self.call("dcai_forecast_score")
        self.assertFalse(r["isError"])
        text = r["content"][0]["text"]
        self.assertIn("预测校准报告", text)
        self.assertIn("N=1", text)
        self.assertIn("0.25", text)          # 基线解释必须在场

        r = self.call("dcai_verify")
        self.assertFalse(r["isError"])

    def test_double_resolve_is_error(self):
        self.call("dcai_forecast_new", id="FC-2", question="是否发生？", deadline="2026-12-31", p=0.5)
        self.call("dcai_forecast_resolve", id="FC-2", outcome=0)
        r = self.call("dcai_forecast_resolve", id="FC-2", outcome=1)
        self.assertTrue(r["isError"])
        self.assertIn("二次改写", r["content"][0]["text"])

    def test_bad_input_is_error_not_crash(self):
        r = self.call("dcai_forecast_new", id="FC-3", question="这是一个陈述句", deadline="2026/12/31", p=0.5)
        self.assertTrue(r["isError"])
        self.assertIn("可判定", r["content"][0]["text"])

    def test_decide_scaffold(self):
        r = self.call("dcai_decide_new", id="DEC-1", question="要不要换方向")
        self.assertFalse(r["isError"])
        self.assertTrue((self.dir / "decisions" / "DEC-1.md").exists())
        r2 = self.call("dcai_decide_new", id="DEC-1")
        self.assertTrue(r2["isError"])

    def test_check_and_list(self):
        self.assertFalse(self.call("dcai_forecast_list")["isError"])
        self.assertFalse(self.call("dcai_check")["isError"])
        self.assertIn("通过校验", self.call("dcai_check")["content"][0]["text"])


class ConsistencyTest(unittest.TestCase):
    def test_tool_names_are_stable(self):
        expected = {"dcai_forecast_new", "dcai_forecast_update", "dcai_forecast_resolve",
                    "dcai_forecast_void", "dcai_forecast_list", "dcai_forecast_score",
                    "dcai_decide_new", "dcai_check", "dcai_verify"}
        self.assertEqual(mcp.TOOL_NAMES, expected)

    def test_handlers_cover_tools(self):
        self.assertEqual(set(mcp.HANDLERS), mcp.TOOL_NAMES)


if __name__ == "__main__":
    unittest.main()
