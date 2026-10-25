#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dcai — DCAI 统一内核的硬约束层。

把「概率所有权、只追加不覆盖、兑现不可改写、Brier 与校准解释」从提示词里搬进代码，
这样换任何模型、任何客户端，这几条都不会被模型记性稀释。

零依赖，Python 3.8+。数据默认放 ./dcai/（可用 --dir 或 DCAI_HOME 覆盖）。

  dcai.py forecast new --id FC-001 --question "…" --deadline 2026-12-31 --p 0.6
  dcai.py forecast update --id FC-001 --p 0.65 --note "新证据…"
  dcai.py forecast resolve --id FC-001 --outcome 1 --source "官方公告"
  dcai.py forecast void --id FC-001 --reason "事件取消"
  dcai.py forecast score [--json]
  dcai.py forecast list
  dcai.py decide new --id DEC-001 --question "…"
  dcai.py check        # 全量规则校验
  dcai.py verify       # 封印哈希链校验（查手改账）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import sys
from datetime import date, datetime, timezone
from pathlib import Path

SCHEMA = 1
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
QUESTION_HINT = ("是否", "吗", "？", "?", "会不会", "能不能", "有没有")


# ---------------------------------------------------------------- 存储
def home(arg: str | None) -> Path:
    p = Path(arg or os.environ.get("DCAI_HOME") or "dcai")
    p.mkdir(parents=True, exist_ok=True)
    (p / "decisions").mkdir(exist_ok=True)
    return p


def store_path(root: Path) -> Path:
    return root / "forecast.json"


def load(root: Path) -> dict:
    p = store_path(root)
    if not p.exists():
        return {"schema": SCHEMA, "cards": [], "ledger": []}
    data = json.loads(p.read_text(encoding="utf-8"))
    data.setdefault("cards", [])
    data.setdefault("ledger", [])
    return data


def save(root: Path, data: dict) -> None:
    p = store_path(root)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(p)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today() -> str:
    return date.today().isoformat()


# ---------------------------------------------------------------- 封印链
def digest(obj: object) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def seal(root: Path, data: dict, op: str, card_id: str, payload: dict) -> None:
    prev = data["ledger"][-1]["hash"] if data["ledger"] else "0" * 64
    entry = {"seq": len(data["ledger"]) + 1, "ts": now_iso(), "op": op, "id": card_id,
             "payload": payload, "prev": prev}
    entry["hash"] = digest(entry)
    data["ledger"].append(entry)


def verify_chain(data: dict) -> list[str]:
    errs = []
    prev = "0" * 64
    for i, e in enumerate(data["ledger"], 1):
        body = {k: e[k] for k in ("seq", "ts", "op", "id", "payload", "prev") if k in e}
        if e.get("prev") != prev:
            errs.append(f"链断裂：seq={i} 的 prev 与上一条哈希不一致")
        if digest(body) != e.get("hash"):
            errs.append(f"被改动：seq={i}（{e.get('op')} {e.get('id')}）哈希不匹配")
        if e.get("seq") != i:
            errs.append(f"序号异常：位置 {i} 的 seq={e.get('seq')}")
        prev = e.get("hash", "")
    return errs


def replay_check(data: dict) -> list[str]:
    """用账本重放状态，再和卡片实际内容对账——防止绕过 CLI 手改卡片。"""
    exp: dict[str, dict] = {}
    for e in data["ledger"]:
        op, cid, pl = e.get("op"), e.get("id"), e.get("payload") or {}
        if op == "forecast.new":
            exp[cid] = {"p_user": pl.get("p_user"), "deadline": pl.get("deadline"),
                        "n_updates": 0, "status": "open", "outcome": None}
        elif cid in exp and op == "forecast.update":
            exp[cid]["n_updates"] += 1
        elif cid in exp and op == "forecast.resolve":
            exp[cid]["status"] = "resolved"
            exp[cid]["outcome"] = pl.get("outcome")
        elif cid in exp and op == "forecast.void":
            exp[cid]["status"] = "void"

    errs = []
    by_id = {c["id"]: c for c in data["cards"]}
    for cid, e in exp.items():
        c = by_id.get(cid)
        if c is None:
            errs.append(f"{cid}: 账本里有、卡片里没有（被删除）")
            continue
        if c.get("p_user") != e["p_user"]:
            errs.append(f"{cid}: 初始概率与账本不符（账本 {e['p_user']}，卡片 {c.get('p_user')}）")
        if c.get("deadline") != e["deadline"]:
            errs.append(f"{cid}: 兑现时间与账本不符（账本 {e['deadline']}，卡片 {c.get('deadline')}）")
        if len(c.get("updates", [])) != e["n_updates"]:
            errs.append(f"{cid}: 更新次数与账本不符（账本 {e['n_updates']}，卡片 {len(c.get('updates', []))}）")
        if c.get("status") != e["status"]:
            errs.append(f"{cid}: 状态与账本不符（账本 {e['status']}，卡片 {c.get('status')}）")
        if c.get("outcome") != e["outcome"]:
            errs.append(f"{cid}: 结果与账本不符（账本 {e['outcome']}，卡片 {c.get('outcome')}）")
    for cid in by_id:
        if cid not in exp:
            errs.append(f"{cid}: 卡片不在账本里（凭空出现或被复制）")
    return errs


# ---------------------------------------------------------------- 规则
def final_p(card: dict) -> float:
    return card["updates"][-1]["new"] if card.get("updates") else card["p_user"]


def brier(p: float, o: int) -> float:
    return (p - o) ** 2


def validate(card: dict) -> list[str]:
    errs: list[str] = []
    cid = card.get("id", "?")
    p = card.get("p_user")
    if not isinstance(p, (int, float)) or isinstance(p, bool) or not 0 <= p <= 1:
        errs.append(f"{cid}: p_user 必须是 [0,1] 内的用户确认概率")
    if card.get("p_owner") != "user":
        errs.append(f"{cid}: 概率所有权不是用户（AI 只能给范围，不能替用户落数）")
    q = card.get("question") or ""
    if not any(h in q for h in QUESTION_HINT):
        errs.append(f"{cid}: 命题需写成可判定的是/否事件")
    dl = card.get("deadline") or ""
    if not ISO_DATE.match(dl):
        errs.append(f"{cid}: deadline 必须是 YYYY-MM-DD")
    else:
        try:
            date.fromisoformat(dl)
        except ValueError:
            errs.append(f"{cid}: deadline 不是合法日期")
    st = card.get("status", "open")
    if st not in ("open", "resolved", "void"):
        errs.append(f"{cid}: status 只能是 open/resolved/void")
    if st == "resolved" and card.get("outcome") not in (0, 1):
        errs.append(f"{cid}: 已兑现卡的 outcome 必须是 0 或 1")
    if st == "open" and card.get("outcome") is not None:
        errs.append(f"{cid}: 未兑现卡不得带 outcome（禁止事后回填）")
    if st == "void" and card.get("outcome") is not None:
        errs.append(f"{cid}: 作废卡不得带 outcome")
    last = p if isinstance(p, (int, float)) else None
    for u in card.get("updates", []):
        if last is not None and u.get("old") != last:
            errs.append(f"{cid}: 更新链断裂，old={u.get('old')} 但上一条是 {last}")
            break
        if not isinstance(u.get("new"), (int, float)) or not 0 <= u["new"] <= 1:
            errs.append(f"{cid}: 更新值必须在 [0,1]")
            break
        last = u["new"]
    c, r = card.get("created") or "", card.get("resolved_at") or ""
    if c and r and r < c:
        errs.append(f"{cid}: 兑现时间早于创建时间")
    br = card.get("base_rate")
    if br is not None and (not isinstance(br, (int, float)) or not 0 <= br <= 1):
        errs.append(f"{cid}: base_rate 必须在 [0,1]")
    return errs


def score(cards: list[dict]) -> dict:
    resolved = [c for c in cards if c.get("status") == "resolved"]
    void = [c for c in cards if c.get("status") == "void"]
    open_ = [c for c in cards if c.get("status", "open") == "open"]
    out: dict = {"n_resolved": len(resolved), "n_open": len(open_), "n_void": len(void)}
    if not resolved:
        out["note"] = "没有已兑现预测，任何校准结论都不成立。"
        return out

    rows = []
    for c in resolved:
        p0, pf, o = c["p_user"], final_p(c), c["outcome"]
        rows.append({"id": c["id"], "p0": p0, "pf": pf, "o": o,
                     "brier_initial": round(brier(p0, o), 4),
                     "brier_final": round(brier(pf, o), 4),
                     "updates": len(c.get("updates", []))})
    b0 = statistics.mean(r["brier_initial"] for r in rows)
    bf = statistics.mean(r["brier_final"] for r in rows)

    bins: dict[int, list[dict]] = {}
    for r in rows:
        bins.setdefault(min(int(r["pf"] * 10), 9), []).append(r)
    calib = [{"range": f"{k*10}-{k*10+10}%", "N": len(g),
              "mean_p": round(statistics.mean(x["pf"] for x in g), 3),
              "hit_rate": round(statistics.mean(x["o"] for x in g), 3),
              "gap": round(statistics.mean(x["o"] - x["pf"] for x in g), 3),
              "small_sample": len(g) < 10}
             for k, g in sorted(bins.items())]

    with_base = [c for c in resolved if isinstance(c.get("base_rate"), (int, float))]
    baseline = round(statistics.mean(brier(c["base_rate"], c["outcome"]) for c in with_base), 4) if with_base else None

    warnings = []
    if len(rows) < 30:
        warnings.append(f"总样本 N={len(rows)} < 30：只能描述，不能宣称「已校准 / 过度自信」。")
    for cb in calib:
        if cb["small_sample"]:
            warnings.append(f"分箱 {cb['range']} 只有 N={cb['N']}，命中率波动极大，不要单独解读。")
    if void:
        warnings.append(f"作废 {len(void)} 条，作废率 {len(void)/(len(resolved)+len(void)):.0%}，需单独报告。")
    if baseline is None:
        warnings.append("没有 base_rate：无法与同题集基线比较，不能只说「比随机好」。")

    out.update({
        "mean_brier_initial": round(b0, 4),
        "mean_brier_final": round(bf, 4),
        "update_gain": round(b0 - bf, 4),
        "baseline_brier": baseline,
        "rows": rows,
        "calibration": calib,
        "warnings": warnings,
        "note": ("0.25 只是「永远报 50%」的二元分数，不是通用随机基线；还要看校准、区分度、N、作废率与更新质量。"
                 "Brier 也不是唯一 KPI，预测分数不等于决策质量。"),
    })
    return out


# ---------------------------------------------------------------- 渲染
def render_score(s: dict) -> str:
    if not s.get("rows"):
        return f"（无已兑现预测）{s.get('note','')} 未兑现 {s.get('n_open',0)} 条，作废 {s.get('n_void',0)} 条。"
    L = [f"## 预测校准报告", "",
         f"- 已兑现 N={s['n_resolved']}｜未兑现 {s['n_open']}｜作废 {s['n_void']}",
         f"- 平均初始 Brier：**{s['mean_brier_initial']}**",
         f"- 平均最终 Brier：**{s['mean_brier_final']}**（更新增益 {s['update_gain']:+.4f}）"]
    if s["baseline_brier"] is not None:
        L.append(f"- 同题集基线 Brier：{s['baseline_brier']}")
    L += ["", "| 卡片 | 初始 p | 最终 p | 结果 | 初始 Brier | 最终 Brier | 更新次数 |", "|---|---:|---:|---:|---:|---:|---:|"]
    for r in s["rows"]:
        L.append(f"| {r['id']} | {r['p0']:.2f} | {r['pf']:.2f} | {r['o']} | {r['brier_initial']} | {r['brier_final']} | {r['updates']} |")
    L += ["", "| 概率档 | N | 平均预测 | 实际命中 | 差距 | 备注 |", "|---|---:|---:|---:|---:|---|"]
    for c in s["calibration"]:
        L.append(f"| {c['range']} | {c['N']} | {c['mean_p']} | {c['hit_rate']} | {c['gap']:+.3f} | {'小样本' if c['small_sample'] else ''} |")
    if s["warnings"]:
        L += ["", "### 警告", ""] + [f"- {w}" for w in s["warnings"]]
    L += ["", f"> {s['note']}"]
    return "\n".join(L)


# ---------------------------------------------------------------- 命令
def find(data: dict, cid: str) -> dict:
    for c in data["cards"]:
        if c["id"] == cid:
            return c
    sys.exit(f"找不到预测卡 {cid}")


def cmd_forecast_new(a, root: Path) -> int:
    data = load(root)
    if any(c["id"] == a.id for c in data["cards"]):
        sys.exit(f"{a.id} 已存在；更新概率请用 forecast update（只追加）")
    if not 0 <= a.p <= 1:
        sys.exit("--p 必须在 [0,1]")
    card = {
        "id": a.id, "question": a.question, "deadline": a.deadline,
        "created": today(), "p_user": a.p, "p_owner": "user",
        "p_ai_range": [a.ai_low, a.ai_high] if a.ai_low is not None and a.ai_high is not None else None,
        "base_rate": a.base_rate, "base_source": a.base_source or "",
        "control": a.control, "status": "open", "outcome": None,
        "resolved_at": "", "resolve_source": "", "void_reason": "",
        "updates": [],
    }
    if a.dry_run:
        print(json.dumps(card, ensure_ascii=False, indent=2))
        return 0
    errs = validate(card)
    if errs:
        print("\n".join(errs), file=sys.stderr)
        return 1
    data["cards"].append(card)
    seal(root, data, "forecast.new", a.id, {"p_user": a.p, "deadline": a.deadline})
    save(root, data)
    print(f"已登记 {a.id}：p={a.p}，兑现时间 {a.deadline}，兑现标准需写进 --question 之外的建议书或决策记录。")


def cmd_forecast_update(a, root: Path) -> int:
    data = load(root)
    card = find(data, a.id)
    if card["status"] == "resolved":
        sys.exit(f"{a.id} 已兑现：禁止事后修改概率（可另开一张新卡）")
    if card["status"] == "void":
        sys.exit(f"{a.id} 已作废：不能再更新")
    if not 0 <= a.p <= 1:
        sys.exit("--p 必须在 [0,1]")
    old = final_p(card)
    card.setdefault("updates", []).append({"ts": today(), "at": now_iso(), "old": old, "new": a.p, "note": a.note or ""})
    seal(root, data, "forecast.update", a.id, {"old": old, "new": a.p})
    save(root, data)
    print(f"{a.id}: {old:.2f} → {a.p:.2f}｜历史保留，不可覆盖")
    return 0


def cmd_forecast_resolve(a, root: Path) -> int:
    data = load(root)
    card = find(data, a.id)
    if card["status"] == "resolved":
        sys.exit(f"{a.id} 已兑现，不允许二次改写结果或兑现标准")
    if card["status"] == "void":
        sys.exit(f"{a.id} 已作废，不能兑现")
    if a.outcome not in (0, 1):
        sys.exit("--outcome 只能 0 或 1（作废请用 forecast void）")
    card["status"] = "resolved"
    card["outcome"] = a.outcome
    card["resolved_at"] = today()
    card["resolve_source"] = a.source or ""
    seal(root, data, "forecast.resolve", a.id, {"outcome": a.outcome})
    save(root, data)
    print(f"{a.id} 已兑现 o={a.outcome}｜初始 Brier={brier(card['p_user'], a.outcome):.4f}"
          f"｜最终 Brier={brier(final_p(card), a.outcome):.4f}")
    return 0


def cmd_forecast_void(a, root: Path) -> int:
    data = load(root)
    card = find(data, a.id)
    if card["status"] != "open":
        sys.exit(f"{a.id} 当前状态 {card['status']}，只能作废 open 的卡")
    card["status"] = "void"
    card["void_reason"] = a.reason or ""
    card["resolved_at"] = today()
    seal(root, data, "forecast.void", a.id, {"reason": a.reason or ""})
    save(root, data)
    print(f"{a.id} 已作废（不计分，但会出现在作废率里）")
    return 0


def cmd_forecast_score(a, root: Path) -> int:
    data = load(root)
    s = score(data["cards"])
    print(json.dumps(s, ensure_ascii=False, indent=2) if a.json else render_score(s))
    return 0


def cmd_forecast_list(a, root: Path) -> int:
    data = load(root)
    if not data["cards"]:
        print("没有预测卡")
        return 0
    print("| ID | 状态 | 初始 p | 最终 p | 结果 | 兑现时间 | 命题 |")
    print("|---|---|---:|---:|---:|---|---|")
    for c in data["cards"]:
        print(f"| {c['id']} | {c['status']} | {c['p_user']:.2f} | {final_p(c):.2f} | "
              f"{'' if c.get('outcome') is None else c['outcome']} | {c['deadline']} | {c['question']} |")
    return 0


TEMPLATE = """# 决策记录 {id}

- 创建：{created}　决策者：{who}　状态：D0 未定义 / D1 选项未成形 / D2 证据中 / D3 暂定 / D4 已决定 / D5 重新开放
- 决策问题：{question}
- 必须决定的日期：
- 是否必须现在决定：

## 目标与偏好
- 我真正想改善的结果：
- 不可接受的结果：
- 我当前倾向及原因：
- 外部压力或利益相关者：
- 愿意承担 / 不愿承担的代价：

## 选项
- A：　B：　C：
- 维持现状：
- 延迟：
- 小规模可逆试验：
- 混合 / 退出方案：

## 关键主张与证据
| 编号 | 主张 | 类型（事实/证据/用户报告/偏好/推断/假设/未知） | 核验状态 | 依据与来源 | 强度 | 反向证据或限制 | 错了会怎样 |
|---|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |

## 选项比较
| 选项 | 预期收益 | 代价 | 成功前提 | 证据与未知 | 可逆性/退出 | 最坏可信结果 | 能力匹配 | 偏好匹配 |
|---|---|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |  |

## 当前判断
- 最终选择或暂定方向：
- 推荐强度：信息呈现 / 弱建议 / 条件建议 / 较强建议
- 核心依据：
- 最薄弱环节：
- 什么事实或偏好变化会改变选择：
- 不作为基线：
- 允许的执行权限：仅研究 / 获取信息 / 可逆试验 / 分阶段 / 完整执行

## 风险与复查
- 主要风险与机制：
- 缓冲与退出：
- 成功指标 / 失败指标：
- 推翻条件：
- 首次复查日期：
- 需要转成预测卡的关键假设：
"""


def cmd_decide_new(a, root: Path) -> int:
    path = root / "decisions" / f"{a.id}.md"
    if path.exists():
        sys.exit(f"{path} 已存在；决策记录不允许覆盖，请换 ID")
    body = TEMPLATE.format(id=a.id, created=today(), who=a.who or "", question=a.question or "")
    path.write_text(body, encoding="utf-8")
    data = load(root)
    seal(root, data, "decide.new", a.id, {"question": a.question or ""})
    save(root, data)
    print(f"已生成 {path}")
    print("下一步：先填「目标与偏好」和「关键主张与证据」，再谈选项；不要把偏好混进证据栏。")
    return 0


def cmd_check(a, root: Path) -> int:
    data = load(root)
    errs = [e for c in data["cards"] for e in validate(c)]
    if errs:
        print("\n".join(errs), file=sys.stderr)
        print(f"\n{len(errs)} 处不合规，共 {len(data['cards'])} 张卡", file=sys.stderr)
        return 1
    print(f"{len(data['cards'])} 张卡全部通过校验（概率所有权 / 更新链 / 无结果回填 / 时间顺序 / 命题可判定）")
    return 0


def cmd_verify(a, root: Path) -> int:
    data = load(root)
    errs = verify_chain(data) + replay_check(data)
    if errs:
        print("\n".join(errs), file=sys.stderr)
        print("校验失败：账本或卡片被手工改动过。", file=sys.stderr)
        return 1
    print(f"封印链完整：{len(data['ledger'])} 条记录，哈希连续；卡片状态与账本重放一致。")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dcai", description="DCAI 内核硬约束层：预测卡 / 决策记录 / 校准评分")
    ap.add_argument("--dir", help="数据目录（默认 ./dcai 或 $DCAI_HOME）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("forecast", help="预测卡操作").add_subparsers(dest="sub", required=True)

    p = f.add_parser("new", help="建卡")
    p.add_argument("--id", required=True)
    p.add_argument("--question", required=True)
    p.add_argument("--deadline", required=True, help="YYYY-MM-DD")
    p.add_argument("--p", type=float, required=True, help="用户确认的初始概率")
    p.add_argument("--ai-low", type=float)
    p.add_argument("--ai-high", type=float)
    p.add_argument("--base-rate", type=float)
    p.add_argument("--base-source")
    p.add_argument("--control", choices=["low", "mid", "high"], default="mid")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_forecast_new)

    p = f.add_parser("update", help="追加更新（只增不改）")
    p.add_argument("--id", required=True)
    p.add_argument("--p", type=float, required=True)
    p.add_argument("--note", default="")
    p.set_defaults(fn=cmd_forecast_update)

    p = f.add_parser("resolve", help="兑现（一次）")
    p.add_argument("--id", required=True)
    p.add_argument("--outcome", type=int, required=True, choices=[0, 1])
    p.add_argument("--source", default="")
    p.set_defaults(fn=cmd_forecast_resolve)

    p = f.add_parser("void", help="作废（不计分）")
    p.add_argument("--id", required=True)
    p.add_argument("--reason", default="")
    p.set_defaults(fn=cmd_forecast_void)

    p = f.add_parser("score", help="校准报告")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_forecast_score)

    p = f.add_parser("list", help="列出所有卡")
    p.set_defaults(fn=cmd_forecast_list)

    d = sub.add_parser("decide", help="决策记录").add_subparsers(dest="sub", required=True)
    p = d.add_parser("new", help="生成决策记录骨架")
    p.add_argument("--id", required=True)
    p.add_argument("--question", default="")
    p.add_argument("--who", default="")
    p.set_defaults(fn=cmd_decide_new)

    sub.add_parser("check", help="全量规则校验").set_defaults(fn=cmd_check)
    sub.add_parser("verify", help="封印链校验").set_defaults(fn=cmd_verify)

    a = ap.parse_args(argv)
    root = home(a.dir)
    return a.fn(a, root)


if __name__ == "__main__":
    raise SystemExit(main())
