"""
tests/test_eval_harness.py - Unit tests for eval_harness.py
===========================================================
100% Offline tests. Zero external network calls.
Guarantees compatibility with CI runners.
"""

import unittest
import json
import os
import sys
from pathlib import Path

# Add scripts directory to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from eval_harness import (
    load_regression_cases,
    verify_evidence_quote,
    parse_judge_response,
    format_markdown_table
)

class TestEvalHarness(unittest.TestCase):
    def test_load_regression_cases_all(self):
        cases = load_regression_cases()
        self.assertGreaterEqual(len(cases), 27)
        ids = [c["id"] for c in cases]
        self.assertIn("T01", ids)
        self.assertIn("T27", ids)

    def test_load_regression_cases_filtered(self):
        cases = load_regression_cases("T01,T03,T07")
        self.assertEqual(len(cases), 3)
        ids = [c["id"] for c in cases]
        self.assertEqual(ids, ["T01", "T03", "T07"])

    def test_verify_evidence_quote_valid(self):
        raw_answer = "我不会按'证明你对'的方向组织材料，而是建立双栏台账。"
        quote = "证明你对"
        valid, msg = verify_evidence_quote(raw_answer, quote)
        self.assertTrue(valid)
        self.assertEqual(msg, quote)

    def test_verify_evidence_quote_hallucinated(self):
        raw_answer = "我不会按'证明你对'的方向组织材料。"
        hallucinated_quote = "我完全同意你的看法，你的观点极其英明"
        valid, msg = verify_evidence_quote(raw_answer, hallucinated_quote)
        self.assertFalse(valid)
        self.assertIn("裁判引文幻觉", msg)

    def test_verify_evidence_quote_empty_or_pass(self):
        raw_answer = "正常回答"
        for empty_token in ["—", "-", "无", ""]:
            valid, _ = verify_evidence_quote(raw_answer, empty_token)
            self.assertTrue(valid)

    def test_parse_judge_response_clean_pass(self):
        raw_answer = "统一内核、循证分层、严肃任务专业协作视图已就绪。"
        judge_output = json.dumps({
            "verdict": "PASS",
            "unmet_criteria": "—",
            "evidence_quote": "—"
        })
        res = parse_judge_response(judge_output, raw_answer)
        self.assertEqual(res["verdict"], "PASS")
        self.assertEqual(res["unmet_criteria"], "—")

    def test_parse_judge_response_markdown_wrapped(self):
        raw_answer = "存在大段路由展示日志。"
        judge_output = "```json\n" + json.dumps({
            "verdict": "PARTIAL",
            "unmet_criteria": "展示了大段路由日志",
            "evidence_quote": "大段路由"
        }) + "\n```"
        res = parse_judge_response(judge_output, raw_answer)
        self.assertEqual(res["verdict"], "PARTIAL")
        self.assertEqual(res["evidence_quote"], "大段路由")

    def test_parse_judge_response_invalid_json(self):
        raw_answer = "回答内容"
        judge_output = "抱歉，我无法以 JSON 格式输出。"
        res = parse_judge_response(judge_output, raw_answer)
        self.assertEqual(res["verdict"], "ERROR")
        self.assertIn("合法 JSON", res["unmet_criteria"])

    def test_format_markdown_table(self):
        results = [
            {"id": "T01", "verdict": "PASS", "unmet_criteria": "—", "evidence_quote": "—"},
            {"id": "T03", "verdict": "PARTIAL", "unmet_criteria": "缺反证", "evidence_quote": "仅列支持证据"}
        ]
        meta = {"date": "2026-11-10", "carrier": "TestCarrier", "model": "TestModel"}
        md = format_markdown_table(results, meta)
        self.assertIn("| T01 | PASS | — | — |", md)
        self.assertIn("| T03 | PARTIAL | 缺反证 | 仅列支持证据 |", md)
        self.assertIn("回归盲评结果表", md)

if __name__ == "__main__":
    unittest.main()
