#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单源构建器：kernel/core.md → SKILL.md 内联区 + dist/ 单文件载体。

唯一真源是 kernel/core.md 与 references/*.md。SKILL.md 里的内核区块、
dist/kernel-always-on.md、dist/dcai-single-file.md 全部是生成物。

用法:
  python scripts/build.py           重新生成
  python scripts/build.py --check   只校验生成物是否与真源同步（CI 用，返回非 0 表示漂移）
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CORE = ROOT / "kernel" / "core.md"
SKILL = ROOT / "SKILL.md"
REF_DIR = ROOT / "references"
DIST = ROOT / "dist"

BEGIN = "<!-- BEGIN:KERNEL"
END = "<!-- END:KERNEL -->"


def read(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8")


def demote(md: str) -> str:
    """去掉 H1 与构建说明引用块，并把标题降一级，便于内联到 SKILL.md 的 ## 之下。"""
    lines = md.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("## "))
    body = lines[start:]
    out = []
    for ln in body:
        m = re.match(r"^(#{2,6})\s+(.*)$", ln)
        if m:
            out.append("#" * (len(m.group(1)) + 1) + " " + m.group(2))
        else:
            out.append(ln)
    return "\n".join(out).strip()


def kernel_block() -> str:
    return demote(read(CORE))


def render_skill(current: str) -> str:
    pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)
    block = f"{BEGIN} (generated from kernel/core.md — do not edit) -->\n\n{kernel_block()}\n\n{END}"
    if not pattern.search(current):
        raise SystemExit("SKILL.md 缺少内核标记，无法生成")
    return pattern.sub(lambda _m: block, current, count=1)


def all_refs() -> list[pathlib.Path]:
    return sorted(REF_DIR.glob("*.md"))


def render_always_on() -> str:
    return read(CORE)


def render_single_file() -> str:
    parts = [
        "# DCAI 统一内核 · v2.0-alpha（单文件载体）",
        "",
        "> 用法：整份贴进系统提示词，或上传为知识库。内核部分每轮有效；附录按需查阅。",
        "> 由 `scripts/build.py` 生成，请勿手改；要改规则请改 `kernel/core.md` 或 `references/`。",
        "",
        "---",
        "",
    ]
    parts.append(read(CORE).strip())
    parts.append("")
    parts.append("---")
    parts.append("")
    parts.append("# 附录：完整工作流")
    parts.append("")
    for i, p in enumerate(all_refs(), 1):
        parts.append(f"## 附录 {i} · {p.name}")
        parts.append("")
        parts.append(p.read_text(encoding="utf-8").strip())
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    targets = {
        SKILL: render_skill(read(SKILL)),
        DIST / "kernel-always-on.md": render_always_on(),
        DIST / "dcai-single-file.md": render_single_file(),
    }

    if a.check:
        drift = []
        for path, content in targets.items():
            if not path.exists():
                drift.append(f"{path.relative_to(ROOT)} 缺失")
            elif read(path) != content:
                drift.append(f"{path.relative_to(ROOT)} 与真源不同步")
        if drift:
            print("生成物漂移：\n  " + "\n  ".join(drift), file=sys.stderr)
            print("修复：python scripts/build.py", file=sys.stderr)
            return 1
        print(f"生成物已同步（{len(targets)} 个文件）")
        return 0

    DIST.mkdir(parents=True, exist_ok=True)
    for path, content in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"写入 {path.relative_to(ROOT)}  {len(content):>7} 字符")
    print(f"references: {len(all_refs())} 个")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
