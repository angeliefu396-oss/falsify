# -*- coding: utf-8 -*-
"""CLI 端到端测试：真实子进程 + 文件重定向（沙箱里也能跑，不依赖管道）。"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import unittest
import uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "dcai.py"


class Result:
    def __init__(self, code, out, err):
        self.returncode, self.stdout, self.stderr = code, out, err


class CLIBase(unittest.TestCase):
    """临时目录用普通 mkdir 建：mkdtemp 会写 0o700，在受限沙箱里会导致子进程写不进去。"""

    def setUp(self):
        self.scratch = ROOT / "tests" / "scratch"
        self.scratch.mkdir(parents=True, exist_ok=True)
        self.dir = str(self.scratch / f"run_{uuid.uuid4().hex[:10]}")
        os.makedirs(self.dir)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def run_cli(self, *args):
        out = pathlib.Path(self.dir) / "._out"
        err = pathlib.Path(self.dir) / "._err"
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        with open(out, "w", encoding="utf-8") as fo, open(err, "w", encoding="utf-8") as fe:
            p = subprocess.run([sys.executable, str(CLI), "--dir", self.dir, *args],
                               stdout=fo, stderr=fe, env=env, stdin=subprocess.DEVNULL)
        return Result(p.returncode, out.read_text(encoding="utf-8"), err.read_text(encoding="utf-8"))

    def new(self, cid="FC-1", p="0.6", question="2026-12-31 前是否上线？", deadline="2026-12-31"):
        return self.run_cli("forecast", "new", "--id", cid, "--question", question,
                            "--deadline", deadline, "--p", p)


class ForecastFlowTest(CLIBase):
    def test_full_flow(self):
        self.assertEqual(self.new().returncode, 0)
        self.assertEqual(self.run_cli("forecast", "update", "--id", "FC-1",
                                      "--p", "0.7", "--note", "证据").returncode, 0)
        r = self.run_cli("forecast", "resolve", "--id", "FC-1", "--outcome", "1", "--source", "公告")
        self.assertEqual(r.returncode, 0)
        self.assertIn("初始 Brier=0.1600", r.stdout)
        self.assertIn("最终 Brier=0.0900", r.stdout)
        self.assertEqual(self.run_cli("check").returncode, 0)
        self.assertEqual(self.run_cli("verify").returncode, 0)
        r = self.run_cli("forecast", "score")
        self.assertEqual(r.returncode, 0)
        self.assertIn("预测校准报告", r.stdout)
        self.assertIn("N=1", r.stdout)

    def test_double_resolve_rejected(self):
        self.new()
        self.run_cli("forecast", "resolve", "--id", "FC-1", "--outcome", "0")
        r = self.run_cli("forecast", "resolve", "--id", "FC-1", "--outcome", "1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("不允许二次改写", r.stderr)

    def test_update_after_resolve_rejected(self):
        self.new()
        self.run_cli("forecast", "resolve", "--id", "FC-1", "--outcome", "1")
        r = self.run_cli("forecast", "update", "--id", "FC-1", "--p", "0.9")
        self.assertEqual(r.returncode, 1)
        self.assertIn("禁止事后修改概率", r.stderr)

    def test_duplicate_id_rejected(self):
        self.new()
        r = self.new()
        self.assertEqual(r.returncode, 1)
        self.assertIn("已存在", r.stderr)

    def test_missing_card_rejected(self):
        r = self.run_cli("forecast", "resolve", "--id", "NOPE", "--outcome", "1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("找不到预测卡", r.stderr)

    def test_void_then_no_update(self):
        self.new()
        self.assertEqual(self.run_cli("forecast", "void", "--id", "FC-1", "--reason", "取消").returncode, 0)
        r = self.run_cli("forecast", "update", "--id", "FC-1", "--p", "0.8")
        self.assertEqual(r.returncode, 1)

    def test_bad_deadline_exits_nonzero(self):
        r = self.new(deadline="2026/12/31")
        self.assertEqual(r.returncode, 1)
        self.assertIn("YYYY-MM-DD", r.stderr)

    def test_list_and_json_score(self):
        self.new()
        self.assertIn("FC-1", self.run_cli("forecast", "list").stdout)
        r = self.run_cli("forecast", "score", "--json")
        self.assertEqual(json.loads(r.stdout)["n_open"], 1)


class TamperTest(CLIBase):
    def test_hand_edited_card_detected(self):
        self.new()
        p = pathlib.Path(self.dir) / "forecast.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        data["cards"][0]["p_user"] = 0.95
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        r = self.run_cli("verify")
        self.assertEqual(r.returncode, 1)
        self.assertIn("初始概率与账本不符", r.stderr)

    def test_hand_edited_ledger_detected(self):
        self.new()
        p = pathlib.Path(self.dir) / "forecast.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        data["ledger"][0]["payload"]["p_user"] = 0.99
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        r = self.run_cli("verify")
        self.assertEqual(r.returncode, 1)
        self.assertIn("哈希不匹配", r.stderr)


class DecideTest(CLIBase):
    def test_scaffold_created_once(self):
        r = self.run_cli("decide", "new", "--id", "DEC-1", "--question", "要不要换方向")
        self.assertEqual(r.returncode, 0)
        md = (pathlib.Path(self.dir) / "decisions" / "DEC-1.md").read_text(encoding="utf-8")
        self.assertIn("决策记录 DEC-1", md)
        self.assertIn("关键主张与证据", md)
        r2 = self.run_cli("decide", "new", "--id", "DEC-1")
        self.assertEqual(r2.returncode, 1)
        self.assertIn("不允许覆盖", r2.stderr)


if __name__ == "__main__":
    unittest.main()
