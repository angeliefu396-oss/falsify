# -*- coding: utf-8 -*-
"""单元测试：Brier 数学、卡片校验、校准报告护栏。"""
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("falsify_cli", ROOT / "scripts" / "falsify.py")
falsify = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(falsify)


def card(**kw):
    base = {
        "id": "FC-T1", "question": "2026-12-31 前是否上线？", "deadline": "2026-12-31",
        "created": "2026-10-01", "p_user": 0.6, "p_owner": "user", "base_rate": None,
        "status": "open", "outcome": None, "updates": [],
    }
    base.update(kw)
    return base


class BrierTest(unittest.TestCase):
    def test_known_values(self):
        self.assertAlmostEqual(falsify.brier(0.5, 0), 0.25)
        self.assertAlmostEqual(falsify.brier(0.5, 1), 0.25)
        self.assertAlmostEqual(falsify.brier(0.9, 1), 0.01)
        self.assertAlmostEqual(falsify.brier(0.7, 0), 0.49)
        self.assertAlmostEqual(falsify.brier(0.0, 0), 0.0)
        self.assertAlmostEqual(falsify.brier(1.0, 0), 1.0)

    def test_final_p_uses_last_update(self):
        c = card(updates=[{"old": 0.6, "new": 0.7}, {"old": 0.7, "new": 0.75}])
        self.assertEqual(falsify.final_p(c), 0.75)
        self.assertEqual(falsify.final_p(card()), 0.6)


class ValidateTest(unittest.TestCase):
    def test_clean_card_passes(self):
        self.assertEqual(falsify.validate(card()), [])

    def test_ai_owned_probability_rejected(self):
        errs = falsify.validate(card(p_owner="ai"))
        self.assertTrue(any("概率所有权" in e for e in errs))

    def test_non_question_rejected(self):
        errs = falsify.validate(card(question="未来会更好"))
        self.assertTrue(any("可判定" in e for e in errs))

    def test_bad_deadline_rejected(self):
        self.assertTrue(any("YYYY-MM-DD" in e for e in falsify.validate(card(deadline="2026/12/31"))))
        self.assertTrue(any("合法日期" in e for e in falsify.validate(card(deadline="2026-13-40"))))

    def test_outcome_on_open_card_rejected(self):
        errs = falsify.validate(card(outcome=1))
        self.assertTrue(any("禁止事后回填" in e for e in errs))

    def test_resolved_requires_outcome(self):
        errs = falsify.validate(card(status="resolved", outcome=None))
        self.assertTrue(any("必须是 0 或 1" in e for e in errs))

    def test_broken_update_chain_detected(self):
        errs = falsify.validate(card(updates=[{"old": 0.5, "new": 0.7}]))
        self.assertTrue(any("更新链断裂" in e for e in errs))

    def test_resolved_before_created_detected(self):
        errs = falsify.validate(card(status="resolved", outcome=1, resolved_at="2026-09-01"))
        self.assertTrue(any("早于创建时间" in e for e in errs))


class ScoreTest(unittest.TestCase):
    def _cards(self):
        return [
            card(id="A", p_user=0.5, status="resolved", outcome=0, base_rate=0.5),
            card(id="B", p_user=0.9, status="resolved", outcome=1, base_rate=0.4,
                 updates=[{"old": 0.9, "new": 0.85}]),
            card(id="C", p_user=0.7, status="resolved", outcome=0, base_rate=0.3,
                 updates=[{"old": 0.7, "new": 0.6}]),
            card(id="D", p_user=0.25),
            card(id="E", p_user=0.5, status="void"),
        ]

    def test_means(self):
        s = falsify.score(self._cards())
        self.assertEqual(s["n_resolved"], 3)
        self.assertEqual(s["n_open"], 1)
        self.assertEqual(s["n_void"], 1)
        self.assertAlmostEqual(s["mean_brier_initial"], round((0.25 + 0.01 + 0.49) / 3, 4))
        self.assertAlmostEqual(s["mean_brier_final"], round((0.25 + 0.0225 + 0.36) / 3, 4))
        self.assertGreater(s["update_gain"], 0)

    def test_baseline_uses_same_card_set(self):
        s = falsify.score(self._cards())
        expected = (falsify.brier(0.5, 0) + falsify.brier(0.4, 1) + falsify.brier(0.3, 0)) / 3
        self.assertAlmostEqual(s["baseline_brier"], round(expected, 4))

    def test_small_sample_warnings(self):
        s = falsify.score(self._cards())
        self.assertTrue(any("N=3" in w for w in s["warnings"]))
        self.assertTrue(any("小样本" in w or "N=1" in w for w in s["warnings"]))
        self.assertTrue(all(c["small_sample"] for c in s["calibration"]))

    def test_baseline_absent_warns(self):
        s = falsify.score([card(id="Z", status="resolved", outcome=1, p_user=0.8)])
        self.assertIsNone(s["baseline_brier"])
        self.assertTrue(any("base_rate" in w for w in s["warnings"]))

    def test_empty_set_has_no_conclusion(self):
        s = falsify.score([card(id="Z", p_user=0.5)])
        self.assertEqual(s["n_resolved"], 0)
        self.assertIn("note", s)
        self.assertNotIn("mean_brier_final", s)


class SealTest(unittest.TestCase):
    def test_chain_detects_tamper(self):
        data = {"schema": 1, "cards": [], "ledger": []}
        falsify.seal(None, data, "forecast.new", "FC-1", {"p_user": 0.6, "deadline": "2026-12-31"})
        falsify.seal(None, data, "forecast.update", "FC-1", {"old": 0.6, "new": 0.7})
        self.assertEqual(falsify.verify_chain(data), [])
        data["ledger"][1]["payload"]["new"] = 0.99
        self.assertTrue(falsify.verify_chain(data))

    def test_replay_detects_card_edit(self):
        data = {"schema": 1, "cards": [card()], "ledger": []}
        falsify.seal(None, data, "forecast.new", "FC-T1", {"p_user": 0.6, "deadline": "2026-12-31"})
        self.assertEqual(falsify.replay_check(data), [])
        data["cards"][0]["p_user"] = 0.95
        self.assertTrue(any("初始概率与账本不符" in e for e in falsify.replay_check(data)))

    def test_replay_detects_ghost_card(self):
        data = {"schema": 1, "cards": [card(id="FC-X")], "ledger": []}
        self.assertTrue(any("不在账本" in e for e in falsify.replay_check(data)))


if __name__ == "__main__":
    unittest.main()
