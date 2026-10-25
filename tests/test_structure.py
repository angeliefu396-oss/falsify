# -*- coding: utf-8 -*-
"""结构与一致性测试：单源生成、双语一致、索引完整、载体齐全。

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
SKILL_EN = (ROOT / "SKILL.en.md").read_text(encoding="utf-8")
CORE = (ROOT / "kernel" / "core.md").read_text(encoding="utf-8")
CORE_EN = (ROOT / "kernel" / "core.en.md").read_text(encoding="utf-8")
REFS = sorted((ROOT / "references").glob("*.md"))
DIST = ROOT / "dist"


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


build = load("dcai_build", "scripts/build.py")
dcai = load("dcai_cli", "scripts/dcai.py")

DESC = re.compile(r"^description:\s*(.+)$", re.M)


class FrontmatterTest(unittest.TestCase):
    def test_zh_has_frontmatter(self):
        self.assertTrue(SKILL.startswith("---\n"))
        head = SKILL.split("---", 2)[1]
        self.assertIn("name: dcai-unified-kernel", head)
        self.assertIn("license: MIT", head)

    def test_en_has_frontmatter(self):
        self.assertTrue(SKILL_EN.startswith("---\n"))
        head = SKILL_EN.split("---", 2)[1]
        self.assertIn("name: dcai-unified-kernel", head)
        self.assertIn("license: MIT", head)

    def test_descriptions_within_spec(self):
        for doc, name in ((SKILL, "SKILL.md"), (SKILL_EN, "SKILL.en.md")):
            head = doc.split("---", 2)[1]
            desc = DESC.search(head).group(1)
            self.assertLessEqual(len(desc), 1024, f"{name} description 超长")

    def test_zh_description_has_chinese_triggers(self):
        head = SKILL.split("---", 2)[1]
        for kw in ("中文触发", "严肃研究", "Brier"):
            self.assertIn(kw, head)


class SingleSourceTest(unittest.TestCase):
    def test_generated_files_in_sync(self):
        for path, content in build.targets().items():
            self.assertEqual(content, path.read_text(encoding="utf-8"), f"{path.name} 与真源不同步")

    def test_zh_kernel_injected(self):
        self.assertIn("BEGIN:KERNEL-ZH", SKILL)
        self.assertIn("END:KERNEL-ZH", SKILL)
        block = SKILL.split("<!-- END:KERNEL-ZH -->")[0].split("BEGIN:KERNEL-ZH")[1]
        self.assertIn("六条铁律", block)
        self.assertIn("每轮八步", block)

    def test_en_kernel_injected(self):
        self.assertIn("BEGIN:KERNEL-EN", SKILL_EN)
        self.assertIn("END:KERNEL-EN", SKILL_EN)
        block = SKILL_EN.split("<!-- END:KERNEL-EN -->")[0].split("BEGIN:KERNEL-EN")[1]
        self.assertIn("Six hard rules", block)
        self.assertIn("Eight steps, every turn", block)

    def test_kernel_covers_seven_types(self):
        for t in ("已核验事实", "证据", "用户报告", "用户偏好", "系统推断", "假设", "未知"):
            self.assertIn(t, CORE)

    def test_zh_kernel_has_brier_guard(self):
        self.assertIn("0.25", CORE)
        self.assertIn("不是通用随机基线", CORE)

    def test_en_kernel_has_brier_guard(self):
        self.assertIn("0.25", CORE_EN)
        self.assertIn("not a universal random baseline", CORE_EN)

    def test_kernel_marks_generated(self):
        self.assertIn("do not edit", SKILL)
        self.assertIn("do not edit", SKILL_EN)


class IndexTest(unittest.TestCase):
    def test_all_refs_listed_zh(self):
        for p in REFS:
            self.assertIn(p.name, SKILL, f"{p.name} 未在 SKILL.md 索引中出现")

    def test_all_refs_listed_en(self):
        for p in REFS:
            self.assertIn(p.name, SKILL_EN, f"{p.name} 未在 SKILL.en.md 索引中出现")

    def test_all_listed_refs_exist(self):
        for doc in (SKILL, SKILL_EN):
            for m in set(re.findall(r"references/([0-9a-z\-]+\.md)", doc)):
                self.assertTrue((ROOT / "references" / m).exists(), f"索引里的 {m} 不存在")

    def test_refs_are_utf8_headings(self):
        for p in REFS:
            text = p.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("# "), f"{p.name} 缺少 H1")
            self.assertNotIn("\t", text, f"{p.name} 含制表符")

    def test_ref_count(self):
        self.assertEqual(len(REFS), 19)

    def test_en_routes_to_same_files(self):
        for f in ("05-partner-audit", "06-risk", "07-research", "08-decision",
                  "09-execution", "10-system-build", "11-forecast"):
            self.assertIn(f"references/{f}.md", SKILL_EN)


class DistTest(unittest.TestCase):
    def test_single_file_contains_every_ref(self):
        single = (DIST / "dcai-single-file.md").read_text(encoding="utf-8")
        for p in REFS:
            first = p.read_text(encoding="utf-8").splitlines()[0]
            self.assertIn(first, single, f"{p.name} 的标题未进入单文件载体")
        self.assertIn("附录", single)

    def test_zh_always_on_is_kernel_only(self):
        always = (DIST / "kernel-always-on.md").read_text(encoding="utf-8")
        self.assertEqual(always, CORE)
        self.assertLess(len(always), 3000, "中文常驻内核过长，会挤占每轮上下文")

    def test_en_always_on_is_kernel_only(self):
        always = (DIST / "kernel-always-on.en.md").read_text(encoding="utf-8")
        self.assertEqual(always, CORE_EN)
        self.assertLess(len(always), 7000, "英文常驻内核过长（英文本身字符占用更高）")


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
        for name in ("README.md", "README.zh-CN.md", "GUIDE.md", "MANUAL.md", "MANUAL.en.md",
                     "LICENSE", "CHANGELOG.md", "CONTRIBUTING.md", "AGENTS.md",
                     "docs/architecture.md", "docs/portability.md", "docs/usage.md",
                     "docs/mcp.md", "docs/i18n.md", "docs/regression.md",
                     "docs/regression-results.md"):
            self.assertTrue((ROOT / name).exists(), f"缺少 {name}")

    def test_readme_links_resolve(self):
        for name in ("README.md", "README.zh-CN.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            for m in set(re.findall(r"\]\((?!https?:)([^)#]+)\)", text)):
                self.assertTrue((ROOT / m).exists(), f"{name} 指向不存在的 {m}")

    def test_scripts_are_ascii_where_required(self):
        # PowerShell 5.1 会把无 BOM 的 UTF-8 当 ANSI，ps1 里出现中文就会解析失败
        p = ROOT / "install" / "install.ps1"
        p.read_bytes().decode("ascii")
