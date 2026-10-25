# -*- coding: utf-8 -*-
"""结构与一致性测试：单源生成、索引完整、frontmatter 合规、载体齐全。

全部走进程内导入，不开子进程、不用管道 —— 在受限沙箱里同样可跑。
"""
import contextlib
import importlib.util
import io
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILL = (ROOT / "SKILL.md").read_text(encoding="utf-8")
CORE = (ROOT / "kernel" / "core.md").read_text(encoding="utf-8")
REFS = sorted((ROOT / "references").glob("*.md"))
DIST = ROOT / "dist"


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


build = load("dcai_build", "scripts/build.py")
dcai = load("dcai_cli", "scripts/dcai.py")


class FrontmatterTest(unittest.TestCase):
    def test_has_frontmatter(self):
        self.assertTrue(SKILL.startswith("---\n"))
        head = SKILL.split("---", 2)[1]
        self.assertIn("name: dcai-unified-kernel", head)
        self.assertIn("description:", head)

    def test_description_length(self):
        head = SKILL.split("---", 2)[1]
        desc = re.search(r"^description:\s*(.+)$", head, re.M).group(1)
        self.assertLessEqual(len(desc), 1024)

    def test_description_has_triggers(self):
        head = SKILL.split("---", 2)[1]
        for kw in ("中文触发", "严肃研究", "Brier"):
            self.assertIn(kw, head)


class SingleSourceTest(unittest.TestCase):
    def test_generated_files_in_sync(self):
        self.assertEqual(build.render_skill(SKILL), SKILL)
        self.assertEqual(build.render_always_on(), (DIST / "kernel-always-on.md").read_text(encoding="utf-8"))
        self.assertEqual(build.render_single_file(), (DIST / "dcai-single-file.md").read_text(encoding="utf-8"))

    def test_kernel_injected(self):
        self.assertIn("BEGIN:KERNEL", SKILL)
        self.assertIn("END:KERNEL", SKILL)
        block = SKILL.split("<!-- END:KERNEL -->")[0].split("BEGIN:KERNEL")[1]
        self.assertIn("六条铁律", block)
        self.assertIn("每轮八步", block)

    def test_kernel_covers_seven_types(self):
        for t in ("已核验事实", "证据", "用户报告", "用户偏好", "系统推断", "假设", "未知"):
            self.assertIn(t, CORE)

    def test_kernel_has_brier_guard(self):
        self.assertIn("0.25", CORE)
        self.assertIn("不是通用随机基线", CORE)

    def test_kernel_marks_generated(self):
        self.assertIn("do not edit", SKILL)


class IndexTest(unittest.TestCase):
    def test_all_refs_listed(self):
        for p in REFS:
            self.assertIn(p.name, SKILL, f"{p.name} 未在 SKILL.md 索引中出现")

    def test_all_listed_refs_exist(self):
        for m in set(re.findall(r"references/([0-9a-z\-]+\.md)", SKILL)):
            self.assertTrue((ROOT / "references" / m).exists(), f"索引里的 {m} 不存在")

    def test_refs_are_utf8_headings(self):
        for p in REFS:
            text = p.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("# "), f"{p.name} 缺少 H1")
            self.assertNotIn("\t", text, f"{p.name} 含制表符")

    def test_ref_count(self):
        self.assertEqual(len(REFS), 19)


class DistTest(unittest.TestCase):
    def test_single_file_contains_every_ref(self):
        single = (DIST / "dcai-single-file.md").read_text(encoding="utf-8")
        for p in REFS:
            first = p.read_text(encoding="utf-8").splitlines()[0]
            self.assertIn(first, single, f"{p.name} 的标题未进入单文件载体")
        self.assertIn("附录", single)

    def test_always_on_is_kernel_only(self):
        always = (DIST / "kernel-always-on.md").read_text(encoding="utf-8")
        self.assertEqual(always, CORE)
        self.assertLess(len(always), 3000, "常驻内核过长，会挤占每轮上下文")


class CliHelpTest(unittest.TestCase):
    def test_help_works(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), self.assertRaises(SystemExit) as ctx:
            dcai.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("forecast", buf.getvalue())
        self.assertIn("decide", buf.getvalue())


class DocTest(unittest.TestCase):
    def test_required_docs_exist(self):
        for name in ("README.md", "README.zh-CN.md", "LICENSE", "CHANGELOG.md",
                     "CONTRIBUTING.md", "AGENTS.md", "docs/architecture.md",
                     "docs/portability.md", "docs/usage.md"):
            self.assertTrue((ROOT / name).exists(), f"缺少 {name}")

    def test_readme_links_resolve(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for m in set(re.findall(r"\]\((?!https?:)([^)#]+)\)", readme)):
            self.assertTrue((ROOT / m).exists(), f"README 指向不存在的 {m}")
