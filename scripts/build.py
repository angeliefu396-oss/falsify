#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单源构建器：把 kernel/*.md 注入 SKILL*.md，并生成 dist/ 载体。

唯一真源：kernel/core.md、kernel/core.en.md、references/*.md。
生成物：SKILL.md 与 SKILL.en.md 的内核区块、dist/ 下所有文件。

用法:
  python scripts/build.py           重新生成
  python scripts/build.py --check   只校验是否与真源同步（CI 用，非 0 表示漂移）
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REF_DIR = ROOT / "references"
DIST = ROOT / "dist"

# (文档, 内核真源, 起始标记, 结束标记)
INJECTIONS = [
    (ROOT / "SKILL.md", ROOT / "kernel" / "core.md",
     "<!-- BEGIN:KERNEL-ZH (generated from kernel/core.md by scripts/build.py - do not edit) -->",
     "<!-- END:KERNEL-ZH -->"),
    (ROOT / "SKILL.en.md", ROOT / "kernel" / "core.en.md",
     "<!-- BEGIN:KERNEL-EN (generated from kernel/core.en.md by scripts/build.py - do not edit) -->",
     "<!-- END:KERNEL-EN -->"),
]


def read(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8")


def demote(md: str) -> str:
    """去掉 H1 与构建说明引用块，标题降一级，便于内联到 ## 之下。"""
    lines = md.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("## "))
    out = []
    for ln in lines[start:]:
        m = re.match(r"^(#{2,6})\s+(.*)$", ln)
        out.append("#" * (len(m.group(1)) + 1) + " " + m.group(2) if m else ln)
    return "\n".join(out).strip()


def render_injection(doc: str, core_path: pathlib.Path, begin: str, end: str) -> str:
    pattern = re.compile(re.escape(begin.split(" (")[0]) + r".*?" + re.escape(end), re.S)
    block = f"{begin}\n\n{demote(read(core_path))}\n\n{end}"
    if not pattern.search(doc):
        raise SystemExit(f"{doc.name} 缺少内核标记，无法生成")
    return pattern.sub(lambda _m: block, doc, count=1)


def all_refs() -> list[pathlib.Path]:
    return sorted(REF_DIR.glob("*.md"))


def render_single() -> str:
    parts = [
        "# 证伪内核 · v2.2-alpha（单文件载体 / single-file carrier）",
        "",
        "> 用法：整份贴进系统提示词，或上传为知识库。内核部分每轮有效；附录按需查阅。",
        "> Usage: paste into a system prompt or upload as a knowledge file. The kernel applies every turn; appendices are for reference.",
        "> 由 `scripts/build.py` 生成，请勿手改；要改规则请改 `kernel/core.md` 或 `references/`。",
        "",
        "---",
        "",
        read(ROOT / "kernel" / "core.md").strip(),
        "",
        "---",
        "",
        "# 附录：完整工作流 / Appendices",
        "",
    ]
    for i, p in enumerate(all_refs(), 1):
        parts += [f"## 附录 {i} · {p.name}", "", read(p).strip(), ""]
    return "\n".join(parts).rstrip() + "\n"


def targets() -> dict[pathlib.Path, str]:
    out: dict[pathlib.Path, str] = {}
    for doc, core, begin, end in INJECTIONS:
        current = read(doc)
        out[doc] = render_injection(current, core, begin, end)
    out[DIST / "kernel-always-on.md"] = read(ROOT / "kernel" / "core.md")
    out[DIST / "kernel-always-on.en.md"] = read(ROOT / "kernel" / "core.en.md")
    out[DIST / "falsify-single-file.md"] = render_single()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    plan = targets()
    if a.check:
        drift = []
        for path, content in plan.items():
            if not path.exists():
                drift.append(f"{path.relative_to(ROOT)} 缺失")
            elif read(path) != content:
                drift.append(f"{path.relative_to(ROOT)} 与真源不同步")
        if drift:
            print("生成物漂移：\n  " + "\n  ".join(drift), file=sys.stderr)
            print("修复：python scripts/build.py", file=sys.stderr)
            return 1
        print(f"生成物已同步（{len(plan)} 个文件）")
        return 0

    DIST.mkdir(parents=True, exist_ok=True)
    for path, content in plan.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"写入 {path.relative_to(ROOT)}  {len(content):>7} 字符")
    print(f"references: {len(all_refs())} 个")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
