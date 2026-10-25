# 参与贡献

## 先理解结构

| 路径 | 性质 | 能不能手改 |
|---|---|---|
| `kernel/core.md`、`kernel/core.en.md` | **真源**：中英常驻内核 | 能（两版要同步改） |
| `references/*.md` | **真源**：完整工作流（当前中文） | 能 |
| `SKILL.md` / `SKILL.en.md` 的内核区块 | 生成物 | **不能** |
| `dist/*` | 生成物 | **不能** |
| `tests/*` | 防腐层 | 能，但不许为了变绿放宽断言 |
| `tests/regression/cases.json` | 行为回归用例 | 能，改动要在 PR 里说明原因 |

改完真源：

```bash
python scripts/build.py
python -m unittest discover -s tests
python scripts/build.py --check     # CI 同款检查
```

## 修改规则的五步

1. **复现**。写下原始输入、模型与载体、完整回答、你判定它错在哪。一次坏回答只是线索，不是结论。
2. **定位**。这是内核缺了一条、工作流缺了一步、还是模型能力问题？先排除"需求本身矛盾"和"用户指令冲突"。
3. **立用例**。在 `references/19-regression.md` 加一条 T 编号，写清发送内容与通过标准。没有可复现用例的规则修改不予合并。
4. **改最小位置**。优先改工作流，其次改内核。内核每加一行，所有用户的每轮成本都涨。
5. **验证**。跑测试 + 至少在一个真实载体上人工跑一遍新旧用例，把结果写进 PR。

## 禁止清单

- **禁止单例补丁**：因为一次回答不顺眼就往内核加十条规则。
- **禁止放宽断言**让 CI 变绿。
- **禁止手改生成物**（CI 会红）。
- **禁止声称已加载但没读的文件**——这条对文档同样适用：不要写"已测试"而没测试。
- **禁止把 Brier 0.25 说成通用基线**，也禁止在小样本上给"已校准/过度自信"的结论。
- **禁止举一个成功案例就说规则有效**：要么给同题集对照，要么标注为轶事。

## 内核膨胀红线

`dist/kernel-always-on.md` 超过 3,000 字符会让 `test_structure.py` 失败。这是刻意的：内核变长会稀释注意力，规则应下沉到具体工作流。要加内容，先问"它只在某类任务里需要吗"——是就写进 `references/`。

## 新增一个工作流

1. 新建 `references/NN-name.md`，首行 `# ` 标题。
2. 在 `SKILL.md` 路由表与参考索引里各加一行。
3. 更新 `tests/test_structure.py` 里 `test_ref_count` 的期望数字。
4. `python scripts/build.py` 重新生成单文件载体。
5. CI 绿了再提 PR。

## 测试

```bash
python -m unittest discover -s tests -v
```

四类：`test_unit.py` 数学与校验、`test_cli.py` 真实子进程护栏与篡改检测、`test_mcp.py` 协议层与工具层、`test_structure.py` 单源一致性、双语一致性与文档完整性。

改动 `scripts/falsify_mcp.py` 时注意：它必须调用 `falsify.py` 的同一批函数，不能自带一份规则实现——否则 CLI 和 MCP 会分叉。工具名与 handler 的对应关系有测试守着（`ConsistencyTest`）。

改内核/工作流还要跑行为回归：至少首轮 7 条（T01、T03、T07、T09、T13、T19、T21），协议见 [docs/regression.md](docs/regression.md)。

在受限沙箱（写不进新建目录、不能开管道）里跑测试的注意事项已经在 `test_cli.py` 里处理：用普通 `mkdir` 建测试目录、用文件重定向代替 `capture_output`。改测试时别退回去用 `mkdtemp` 或 `PIPE`。

## 脚本约定

- `install/install.ps1` 只写 ASCII：Windows PowerShell 5.1 会把无 BOM 的 UTF-8 当 ANSI 解码，中文字面量会直接把脚本解析坏。要加提示文字就用英文。
- `install/install.sh` 用 POSIX `sh` 语法，且在 `set -eu` 下不要用 `[ 条件 ] && 命令` 结尾——条件为假会让整条管道返回非 0，脚本会静默退出。用 `if ... fi`。
- `scripts/*.py` 只用标准库，保持 3.8 兼容（别用 `match`、`X | Y` 运行时类型、`tomllib`）。
- 测试里不要用 `mkdtemp`（0o700 权限在受限沙箱里会让子进程写不进去）和 `capture_output`（沙箱禁管道）。用普通 `mkdir` + 文件重定向。

## 版本与发布

- 新增工作流 / 新增 CLI 子命令 → **minor**
- 内核语义变更（会改变已有回答的行为）→ **major**
- 文案、示例、文档修正 → **patch**
- 未通过真实载体回归前，版本号必须带 `-alpha` 或 `-rc` 后缀，不得标 `stable`。

发布步骤：更新 `CHANGELOG.md` → `python scripts/build.py` → 跑测试 → 打 tag → 在 README 的 Status 段落更新状态。

## 提交信息

```text
<type>(<scope>): <summary>

type: feat | fix | docs | test | chore | refactor
scope: kernel | references | cli | build | docs | tests
```

例：`feat(cli): reject outcome edits after resolve`

## 行为准则

就事论事。评审针对规则和证据，不针对人。你自己提交的规则，也要接受被同一条规则审。
