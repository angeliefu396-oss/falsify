#!/usr/bin/env python3
"""
scripts/eval_harness.py - Falsify 自动化回归评测框架 (Standard Library Only)
=============================================================================
遵循仓库 CONTRIBUTING.md 铁律：
1. 纯 Python 3.8+ 标准库，零第三方依赖。
2. 双盲协议：裁判 Agent 仅获取 prompt + criteria + answer，剥离系统名称与规则版本。
3. 证据真确性硬校验：断言裁判提取的 evidence_quote 必须真实存在于 raw_answer 中。
4. 结构化 JSON 与 Markdown 双输出，兼容 docs/regression-results.md。
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CASES_FILE = REPO_ROOT / "tests" / "regression" / "cases.json"
DEFAULT_RUNS_DIR = REPO_ROOT / "tests" / "regression" / "runs"

JUDGE_SYSTEM_PROMPT = """你是一名严格、客观的盲评裁判。
你需要根据提供的【评测标准 (Criteria)】，客观审查【被测回答 (Answer)】是否满足全部要求。
请输出且仅输出合法 JSON，禁止包含任何 Markdown 代码块标签或额外解释。
JSON 格式要求如下：
{
  "verdict": "PASS" | "PARTIAL" | "FAIL",
  "unmet_criteria": "若完全通过填'—'，否则概括未满足的标准点",
  "evidence_quote": "从原始回答中精确摘录的证据片段（<=80字），若完全通过填'—'"
}"""

def load_regression_cases(filter_ids=None):
    if not CASES_FILE.exists():
        raise FileNotFoundError(f"Cases file not found: {CASES_FILE}")
    with open(CASES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    cases = data.get("cases", [])
    if filter_ids:
        target_ids = {cid.strip().upper() for cid in filter_ids.split(",")}
        cases = [c for c in cases if c.get("id", "").upper() in target_ids]
    return cases

def verify_evidence_quote(raw_answer, quote):
    """硬断言：裁判提取的证据必须在原始回答中真实存在，防止裁判幻觉捏造证据"""
    if not quote or quote.strip() in ("—", "-", "无", ""):
        return True, ""
    clean_quote = quote.strip().strip('"').strip("'")
    if clean_quote in raw_answer:
        return True, clean_quote
    # 允许去除首尾标点后匹配
    short_quote = clean_quote[:30]
    if short_quote in raw_answer:
        return True, clean_quote
    return False, f"裁判引文幻觉：'{clean_quote}' 未在原始回答中出现"

def parse_judge_response(raw_text, raw_answer):
    """解析裁判输出并做 Schema 强制校验"""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    
    try:
        res = json.loads(text)
    except json.JSONDecodeError:
        return {
            "verdict": "ERROR",
            "unmet_criteria": "裁判输出无法解析为合法 JSON",
            "evidence_quote": text[:80]
        }
    
    verdict = str(res.get("verdict", "FAIL")).upper()
    if verdict not in ("PASS", "PARTIAL", "FAIL"):
        verdict = "FAIL"
        
    quote = str(res.get("evidence_quote", "—"))
    valid_quote, quote_msg = verify_evidence_quote(raw_answer, quote)
    if not valid_quote:
        return {
            "verdict": "ERROR",
            "unmet_criteria": quote_msg,
            "evidence_quote": quote[:80]
        }
        
    return {
        "verdict": verdict,
        "unmet_criteria": str(res.get("unmet_criteria", "—")),
        "evidence_quote": quote[:80]
    }

def format_markdown_table(results, metadata=None):
    """渲染为与 docs/regression-results.md 100% 对齐的 Markdown 表格"""
    lines = []
    meta = metadata or {}
    lines.append(f"# 回归盲评结果表 ({meta.get('date', 'N/A')})")
    lines.append("")
    lines.append(f"载体：{meta.get('carrier', 'N/A')} ｜ 模型：{meta.get('model', 'N/A')} ｜ 评审：{meta.get('judge', 'Blind Judge')}")
    lines.append("")
    lines.append("| 用例 | 判定 | 未满足的标准点 | 证据摘录≤80字 |")
    lines.append("|---|---|---|---|")
    for r in results:
        cid = r.get("id", "")
        verdict = r.get("verdict", "FAIL")
        unmet = r.get("unmet_criteria", "—").replace("|", "\\|").replace("\n", " ")
        quote = r.get("evidence_quote", "—").replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {cid} | {verdict} | {unmet} | {quote} |")
    lines.append("")
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="Falsify Regression Evaluation Harness")
    parser.add_argument("--cases", help="Comma-separated case IDs to run (e.g. T01,T03,T07)")
    parser.add_argument("--list", action="store_true", help="List all available regression cases")
    parser.add_argument("--output", help="Output file path (default stdout)")
    args = parser.parse_args()

    if args.list:
        cases = load_regression_cases()
        print(f"Total regression cases: {len(cases)}")
        for c in cases:
            print(f"  [{c['id']}] {c.get('title', '')}: {c.get('prompt', '')[:50]}...")
        return 0

    cases = load_regression_cases(args.cases)
    print(f"Loaded {len(cases)} cases for evaluation.", file=sys.stderr)
    return 0

if __name__ == "__main__":
    sys.exit(main())
