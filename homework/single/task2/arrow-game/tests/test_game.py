"""自动化测试：覆盖 T01 - T06 以及三层关卡的可解性。"""

from __future__ import annotations

import unittest

from arrow_game.core import GameStatus, LevelState, MoveOutcome
from arrow_game.levels import LEVELS


class PathRuleTests(unittest.TestCase):
    def setUp(self) -> None:
        spec = LEVELS[0]
        self.state = LevelState(spec.rows, spec.cols, spec.arrows, spec.max_misses)

    def test_t01_unblocked_arrow_flies_out(self) -> None:
        """T01：点击前方无阻挡的箭头，箭头消失。"""

        before = self.state.remaining_arrows
        result = self.state.attempt_remove(2, 4)  # 最右侧、朝右
        self.assertEqual(result.outcome, MoveOutcome.FLY)
        self.assertEqual(self.state.remaining_arrows, before - 1)

    def test_t02_blocked_arrow_consumes_miss(self) -> None:
        """T02：点击前方有阻挡的箭头，不消失且失误次数减 1。"""

        before = self.state.remaining_arrows
        result = self.state.attempt_remove(2, 0)  # 朝右，但右侧有箭头
        self.assertEqual(result.outcome, MoveOutcome.BLOCKED)
        self.assertIsNotNone(result.blocker)
        self.assertEqual(self.state.remaining_arrows, before)
        self.assertEqual(self.state.misses, 1)

    def test_t03_edge_outward_arrow_has_no_index_error(self) -> None:
        """T03：边缘朝外的箭头正常消失，不发生越界错误。"""

        result = self.state.attempt_remove(4, 4)  # 右下角，朝下
        self.assertEqual(result.outcome, MoveOutcome.FLY)
        self.assertIsNone(self.state.arrow_at(4, 4))

    def test_all_levels_are_solvable(self) -> None:
        """所有关卡都必须存在合理通关顺序。"""

        for spec in LEVELS:
            with self.subTest(level=spec.name):
                state = LevelState(spec.rows, spec.cols, spec.arrows, spec.max_misses)
                solution = state.solve()
                self.assertIsNotNone(solution)
                self.assertEqual(len(solution or ()), len(spec.arrows))
                for arrow in solution or ():
                    result = state.attempt_remove(arrow.row, arrow.col)
                    self.assertEqual(result.outcome, MoveOutcome.FLY)
                self.assertEqual(state.status, GameStatus.WON)

    def test_t04_clear_all_arrows_wins(self) -> None:
        """T04：按求解顺序清空全部箭头后进入通关状态。"""

        state = LevelState(LEVELS[0].rows, LEVELS[0].cols, LEVELS[0].arrows, LEVELS[0].max_misses)
        solution = state.solve() or ()
        for arrow in solution:
            state.attempt_remove(arrow.row, arrow.col)
        self.assertEqual(state.status, GameStatus.WON)
        self.assertEqual(state.remaining_arrows, 0)

    def test_t05_exhaust_misses_loses(self) -> None:
        """T05：失误次数耗尽后进入失败状态。"""

        state = LevelState(5, 5, LEVELS[0].arrows, max_misses=2)
        state.attempt_remove(2, 0)
        result = state.attempt_remove(2, 0)
        self.assertEqual(result.outcome, MoveOutcome.BLOCKED)
        self.assertEqual(state.status, GameStatus.LOST)
        self.assertEqual(state.remaining_misses, 0)

    def test_t06_reset_restores_layout_and_misses(self) -> None:
        """T06：重新开始后布局和失误次数恢复。"""

        original = self.state.snapshot()
        self.state.attempt_remove(2, 0)  # 产生一次失误
        self.state.attempt_remove(2, 4)  # 成功飞出一个箭头
        self.state.reset()
        self.assertEqual(self.state.snapshot(), original)
        self.assertEqual(self.state.misses, 0)
        self.assertEqual(self.state.status, GameStatus.PLAYING)

    def test_undo_restores_last_flying_arrow(self) -> None:
        """附加测试：撤销只恢复上一枚成功飞出的箭头。"""

        result = self.state.attempt_remove(2, 4)
        self.assertEqual(result.outcome, MoveOutcome.FLY)
        restored = self.state.undo()
        self.assertEqual(restored, result.arrow)
        self.assertIsNotNone(self.state.arrow_at(2, 4))
        self.assertEqual(self.state.misses, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
