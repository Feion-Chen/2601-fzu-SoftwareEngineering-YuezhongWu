"""关卡数据。所有关卡都经过求解器验证，保证存在通关顺序。"""

from __future__ import annotations

from dataclasses import dataclass

from .core import Arrow, Direction


@dataclass(frozen=True, slots=True)
class LevelSpec:
    name: str
    subtitle: str
    rows: int
    cols: int
    max_misses: int
    arrows: tuple[Arrow, ...]


def arrow(row: int, col: int, direction: str) -> Arrow:
    return Arrow(row, col, Direction(direction))


LEVELS: tuple[LevelSpec, ...] = (
    LevelSpec(
        name="初见锋芒",
        subtitle="先找到最外侧的空路",
        rows=5,
        cols=5,
        max_misses=3,
        arrows=(
            arrow(2, 0, "R"),
            arrow(2, 2, "R"),
            arrow(2, 4, "R"),
            arrow(4, 4, "D"),
            arrow(0, 4, "D"),
            arrow(4, 0, "U"),
            arrow(1, 0, "L"),
            arrow(1, 2, "L"),
        ),
    ),
    LevelSpec(
        name="十字交错",
        subtitle="横竖路线互相牵制",
        rows=6,
        cols=7,
        max_misses=3,
        arrows=(
            arrow(2, 0, "R"),
            arrow(2, 2, "R"),
            arrow(2, 4, "R"),
            arrow(5, 4, "D"),
            arrow(0, 4, "D"),
            arrow(5, 0, "D"),
            arrow(3, 0, "D"),
            arrow(0, 0, "D"),
            arrow(5, 6, "L"),
            arrow(5, 3, "U"),
            arrow(2, 3, "U"),
        ),
    ),
    LevelSpec(
        name="九宫迷阵",
        subtitle="观察完整链条，再开始点击",
        rows=7,
        cols=7,
        max_misses=3,
        arrows=(
            # 第一行：向右链条
            arrow(1, 0, "R"),
            arrow(1, 3, "R"),
            arrow(1, 6, "R"),
            # 第六行：向左链条
            arrow(6, 1, "L"),
            arrow(6, 3, "L"),
            arrow(6, 5, "L"),
            # 第 0 列：向下链条
            arrow(0, 0, "D"),
            arrow(2, 0, "D"),
            arrow(4, 0, "D"),
            # 第 6 列：向上链条
            arrow(0, 6, "U"),
            arrow(2, 6, "U"),
            arrow(4, 6, "U"),
            # 中间列：向下链条
            arrow(0, 3, "D"),
            arrow(3, 3, "D"),
            arrow(5, 3, "D"),
            # 第三行：向右链条
            arrow(3, 1, "R"),
            arrow(3, 4, "R"),
            arrow(3, 6, "R"),
        ),
    ),
)
