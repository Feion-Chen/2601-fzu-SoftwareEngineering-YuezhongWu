"""核心游戏逻辑：与图形界面完全分离，便于测试和自动求解。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Iterable


class Direction(str, Enum):
    """四种箭头方向。"""

    UP = "U"
    DOWN = "D"
    LEFT = "L"
    RIGHT = "R"


class GameStatus(str, Enum):
    PLAYING = "playing"
    WON = "won"
    LOST = "lost"


class MoveOutcome(str, Enum):
    FLY = "fly"
    BLOCKED = "blocked"
    EMPTY = "empty"


@dataclass(frozen=True, slots=True)
class Arrow:
    """棋盘上的一个箭头。坐标从 0 开始。"""

    row: int
    col: int
    direction: Direction

    def moved(self, rows: int, cols: int) -> "Arrow":
        """返回向当前方向移动一格后的箭头。"""

        dr, dc = DIRECTION_DELTAS[self.direction]
        return Arrow(self.row + dr, self.col + dc, self.direction)


DIRECTION_DELTAS: dict[Direction, tuple[int, int]] = {
    Direction.UP: (-1, 0),
    Direction.DOWN: (1, 0),
    Direction.LEFT: (0, -1),
    Direction.RIGHT: (0, 1),
}


@dataclass(frozen=True, slots=True)
class AttemptResult:
    """一次点击的结果。"""

    outcome: MoveOutcome
    arrow: Arrow | None = None
    blocker: Arrow | None = None
    status: GameStatus = GameStatus.PLAYING


class LevelState:
    """一个关卡的完整状态。

    设计原则：
    - 每格最多一个箭头；
    - 箭头只能沿着自己的方向前进；
    - 路径上出现任意箭头都视为阻挡；
    - 点击被阻挡的箭头会消耗一次失误机会。
    """

    def __init__(
        self,
        rows: int,
        cols: int,
        arrows: Iterable[Arrow],
        max_misses: int = 3,
    ) -> None:
        if rows <= 0 or cols <= 0:
            raise ValueError("棋盘尺寸必须为正数")
        if max_misses <= 0:
            raise ValueError("失误机会必须为正数")

        self.rows = rows
        self.cols = cols
        self.max_misses = max_misses
        self._initial_arrows = tuple(arrows)
        self._validate_arrows(self._initial_arrows)
        self._arrows: list[Arrow] = list(self._initial_arrows)
        self._misses = 0
        self._status = GameStatus.PLAYING
        self._history: list[Arrow] = []

    @staticmethod
    def _validate_arrows(arrows: tuple[Arrow, ...]) -> None:
        occupied: set[tuple[int, int]] = set()
        for arrow in arrows:
            cell = (arrow.row, arrow.col)
            if cell in occupied:
                raise ValueError(f"同一格不能放置多个箭头: {cell}")
            occupied.add(cell)

    @property
    def arrows(self) -> tuple[Arrow, ...]:
        return tuple(self._arrows)

    @property
    def misses(self) -> int:
        return self._misses

    @property
    def remaining_misses(self) -> int:
        return self.max_misses - self._misses

    @property
    def remaining_arrows(self) -> int:
        return len(self._arrows)

    @property
    def status(self) -> GameStatus:
        return self._status

    @property
    def history(self) -> tuple[Arrow, ...]:
        return tuple(self._history)

    def arrow_at(self, row: int, col: int) -> Arrow | None:
        return next((a for a in self._arrows if (a.row, a.col) == (row, col)), None)

    def blocker_for(self, arrow: Arrow) -> Arrow | None:
        """返回当前箭头前进方向上的第一个阻挡物。"""

        dr, dc = DIRECTION_DELTAS[arrow.direction]
        row, col = arrow.row + dr, arrow.col + dc
        occupied = {(a.row, a.col): a for a in self._arrows if a != arrow}
        while 0 <= row < self.rows and 0 <= col < self.cols:
            blocker = occupied.get((row, col))
            if blocker is not None:
                return blocker
            row += dr
            col += dc
        return None

    def attempt_remove(self, row: int, col: int) -> AttemptResult:
        """尝试点击一个格子，并返回本次操作的结果。"""

        if self._status != GameStatus.PLAYING:
            return AttemptResult(MoveOutcome.EMPTY, status=self._status)

        arrow = self.arrow_at(row, col)
        if arrow is None:
            return AttemptResult(MoveOutcome.EMPTY, status=self._status)

        blocker = self.blocker_for(arrow)
        if blocker is not None:
            self._misses += 1
            if self._misses >= self.max_misses:
                self._status = GameStatus.LOST
            return AttemptResult(
                MoveOutcome.BLOCKED,
                arrow=arrow,
                blocker=blocker,
                status=self._status,
            )

        self._arrows.remove(arrow)
        self._history.append(arrow)
        if not self._arrows:
            self._status = GameStatus.WON
        return AttemptResult(
            MoveOutcome.FLY,
            arrow=arrow,
            status=self._status,
        )

    def undo(self) -> Arrow | None:
        """撤销上一次成功飞出的箭头。"""

        if self._status != GameStatus.PLAYING or not self._history:
            return None
        arrow = self._history.pop()
        self._arrows.append(arrow)
        self._arrows.sort(key=lambda a: (a.row, a.col))
        return arrow

    def reset(self) -> None:
        """恢复到当前关卡的初始状态。"""

        self._arrows = list(self._initial_arrows)
        self._misses = 0
        self._status = GameStatus.PLAYING
        self._history.clear()

    def snapshot(self) -> tuple[Arrow, ...]:
        return tuple(sorted(self._arrows, key=lambda a: (a.row, a.col)))

    def solve(self) -> tuple[Arrow, ...] | None:
        """用回溯搜索找出任意一个通关顺序。

        关卡规模较小，搜索深度最多为箭头数量；使用状态记忆避免重复分支。
        """

        @lru_cache(maxsize=None)
        def search(remaining: tuple[Arrow, ...]) -> tuple[Arrow, ...] | None:
            if not remaining:
                return ()
            occupied = {(a.row, a.col): a for a in remaining}
            for arrow in remaining:
                if self._blocked_in(arrow, occupied):
                    continue
                next_remaining = tuple(a for a in remaining if a != arrow)
                suffix = search(next_remaining)
                if suffix is not None:
                    return (arrow,) + suffix
            return None

        return search(self.snapshot())

    def _blocked_in(
        self,
        arrow: Arrow,
        occupied: dict[tuple[int, int], Arrow],
    ) -> bool:
        """无副作用地判断箭头在给定棋盘状态下是否受阻。"""

        dr, dc = DIRECTION_DELTAS[arrow.direction]
        row, col = arrow.row + dr, arrow.col + dc
        while 0 <= row < self.rows and 0 <= col < self.cols:
            if (row, col) in occupied:
                return True
            row += dr
            col += dc
        return False


def toggle_direction(direction: Direction) -> Direction:
    """辅助函数：返回相反方向，供界面动画和测试使用。"""

    return {
        Direction.UP: Direction.DOWN,
        Direction.DOWN: Direction.UP,
        Direction.LEFT: Direction.RIGHT,
        Direction.RIGHT: Direction.LEFT,
    }[direction]
