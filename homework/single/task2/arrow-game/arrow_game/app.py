"""Tkinter 图形界面。

界面全部绘制在 Canvas 上，不依赖第三方图形库。
"""

from __future__ import annotations

import math
import time
import tkinter as tk
from typing import Any

from .core import AttemptResult, Arrow, Direction, GameStatus, LevelState, MoveOutcome
from .levels import LEVELS


WIDTH = 1120
HEIGHT = 780

BG_TOP = "#F4F7FF"
BG_BOTTOM = "#E8F0F8"
INK = "#1A233B"
MUTED = "#6E7A94"
NAVY = "#17213A"
CARD = "#FFFFFF"
BOARD = "#21304F"
BOARD_CELL_A = "#283A5D"
BOARD_CELL_B = "#2A3D62"
GRID = "#405272"
GOLD = "#F7C948"
RED = "#EF626C"
GREEN = "#36B37E"
BLUE = "#5B8DEF"

DIR_COLORS = {
    Direction.UP: "#5B8DEF",
    Direction.DOWN: "#EF6A70",
    Direction.LEFT: "#F3A24A",
    Direction.RIGHT: "#38B2A3",
}

DIR_NAMES = {
    Direction.UP: "上",
    Direction.DOWN: "下",
    Direction.LEFT: "左",
    Direction.RIGHT: "右",
}


def blend(c1: str, c2: str, amount: float) -> str:
    """在两个十六进制颜色之间做线性插值。"""

    amount = max(0.0, min(1.0, amount))
    a = tuple(int(c1[i : i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(c2[i : i + 2], 16) for i in (1, 3, 5))
    c = tuple(round(x + (y - x) * amount) for x, y in zip(a, b))
    return "#{:02X}{:02X}{:02X}".format(*c)


class ArrowGameApp(tk.Tk):
    """游戏主窗口。"""

    def __init__(self) -> None:
        super().__init__()
        self.title("一箭又一箭 - Python 课程作业")
        self.geometry(f"{WIDTH}x{HEIGHT}")
        self.resizable(False, False)
        self.configure(bg=BG_TOP)

        self.canvas = tk.Canvas(
            self,
            width=WIDTH,
            height=HEIGHT,
            bg=BG_TOP,
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", lambda _event: self._set_cursor("arrow"))
        self.bind("<KeyPress-r>", lambda _event: self._restart_current())
        self.bind("<KeyPress-u>", lambda _event: self._undo())
        self.bind("<KeyPress-h>", lambda _event: self._hint())
        self.bind("<Escape>", lambda _event: self._go_menu())

        self.screen = "menu"
        self.level_index = 0
        self.state = self._new_state(0)
        self.level_started = time.monotonic()
        self.result: dict[str, Any] = {}
        self.animations: list[dict[str, Any]] = []
        self.blocked_effects: dict[tuple[int, int], float] = {}
        self.pending_transition: tuple[float, str] | None = None
        self.toast_text = ""
        self.toast_until = 0.0
        self.toast_color = INK
        self.hint_arrow: Arrow | None = None
        self.hint_until = 0.0
        self.hover_cell: tuple[int, int] | None = None
        self.total_clicks = 0
        self.buttons: dict[str, tuple[float, float, float, float]] = {}
        self._board_rect = (0.0, 0.0, 0.0, 0.0)
        self._cell_size = 0.0
        self._flying_arrows = 0

        self.after(30, self._tick)

    # ------------------------------------------------------------------
    # 状态与流程
    # ------------------------------------------------------------------
    def _new_state(self, level_index: int) -> LevelState:
        spec = LEVELS[level_index]
        return LevelState(spec.rows, spec.cols, spec.arrows, spec.max_misses)

    def _start_level(self, level_index: int) -> None:
        self.level_index = level_index
        self.state = self._new_state(level_index)
        self.level_started = time.monotonic()
        self.animations.clear()
        self.blocked_effects.clear()
        self.pending_transition = None
        self.hint_arrow = None
        self.hint_until = 0.0
        self.toast_text = ""
        self.total_clicks = 0
        self.screen = "game"
        self.focus_set()

    def _restart_current(self) -> None:
        if self.screen not in {"game", "complete", "failed"}:
            return
        self._start_level(self.level_index)

    def _next_level(self) -> None:
        if self.level_index + 1 < len(LEVELS):
            self._start_level(self.level_index + 1)
        else:
            self._go_menu()

    def _go_menu(self) -> None:
        self.screen = "menu"
        self.animations.clear()
        self.blocked_effects.clear()
        self.pending_transition = None
        self.hint_arrow = None

    def _finish_level(self) -> None:
        self.result = {
            "elapsed": max(0.0, time.monotonic() - self.level_started),
            "moves": len(self.state.history),
            "clicks": self.total_clicks,
            "misses": self.state.misses,
        }
        if self.state.status == GameStatus.WON:
            self.screen = "complete"
        elif self.state.status == GameStatus.LOST:
            self.screen = "failed"

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------
    def _on_click(self, event: tk.Event[Any]) -> None:
        button_name = self._button_at(event.x, event.y)
        if button_name:
            self._handle_button(button_name)
            return

        if self.screen != "game":
            return
        if self.pending_transition is not None or self.animations:
            return

        cell = self._cell_at(event.x, event.y)
        if cell is None:
            return

        self.total_clicks += 1
        result = self.state.attempt_remove(*cell)
        if result.outcome == MoveOutcome.EMPTY:
            self._show_toast("这里没有箭头", MUTED, 0.8)
            return
        if result.outcome == MoveOutcome.BLOCKED:
            self._handle_blocked(result, cell)
            return
        self._handle_fly(result.arrow)

    def _handle_blocked(self, result: AttemptResult, cell: tuple[int, int]) -> None:
        self.blocked_effects[cell] = time.monotonic() + 0.52
        self._show_toast("前方有阻挡，失误次数 -1", RED, 1.15)
        self.hint_arrow = None
        if result.status == GameStatus.LOST:
            self.pending_transition = (time.monotonic() + 0.68, "finish")
        else:
            self.bell()

    def _handle_fly(self, arrow: Arrow | None) -> None:
        if arrow is None:
            return
        start = self._cell_center(arrow.row, arrow.col)
        pad = 125.0
        bx, by, bw, bh = self._board_rect
        target = {
            Direction.UP: (start[0], by - pad),
            Direction.DOWN: (start[0], by + bh + pad),
            Direction.LEFT: (bx - pad, start[1]),
            Direction.RIGHT: (bx + bw + pad, start[1]),
        }[arrow.direction]
        now = time.monotonic()
        self.animations.append(
            {
                "arrow": arrow,
                "start": start,
                "end": target,
                "started": now,
                "duration": 0.42,
            }
        )
        self.hint_arrow = None
        if self.state.status == GameStatus.WON:
            self.pending_transition = (now + 0.62, "finish")

    def _handle_button(self, name: str) -> None:
        if name == "menu_start":
            self._start_level(0)
        elif name.startswith("menu_level_"):
            self._start_level(int(name.rsplit("_", 1)[1]))
        elif name == "menu_help":
            self._show_toast("点击能沿箭头方向飞出棋盘的箭头", BLUE, 2.0)
        elif name == "game_menu":
            self._go_menu()
        elif name == "game_restart":
            self._restart_current()
        elif name == "game_hint":
            self._hint()
        elif name == "game_undo":
            self._undo()
        elif name == "complete_next":
            self._next_level()
        elif name == "complete_replay":
            self._restart_current()
        elif name == "complete_menu":
            self._go_menu()
        elif name == "failed_retry":
            self._restart_current()
        elif name == "failed_menu":
            self._go_menu()

    def _hint(self) -> None:
        if self.screen != "game" or self.pending_transition is not None:
            return
        solution = self.state.solve()
        if not solution:
            self._show_toast("当前状态没有通关顺序", RED, 1.4)
            return
        self.hint_arrow = solution[0]
        self.hint_until = time.monotonic() + 2.6
        self._show_toast("金色高亮箭头当前可以飞出", GOLD, 1.5)

    def _undo(self) -> None:
        if self.screen != "game" or self.pending_transition is not None or self.animations:
            return
        arrow = self.state.undo()
        if arrow is None:
            self._show_toast("没有可以撤销的步骤", MUTED, 1.0)
            return
        self.hint_arrow = None
        self._show_toast("已撤销上一步", BLUE, 1.0)

    def _show_toast(self, text: str, color: str, duration: float) -> None:
        self.toast_text = text
        self.toast_color = color
        self.toast_until = time.monotonic() + duration

    def _set_cursor(self, cursor: str) -> None:
        if self.canvas.cget("cursor") != cursor:
            self.canvas.configure(cursor=cursor)

    def _on_motion(self, event: tk.Event[Any]) -> None:
        button = self._button_at(event.x, event.y)
        cell = self._cell_at(event.x, event.y) if self.screen == "game" else None
        self.hover_cell = cell
        self._set_cursor("hand2" if button or cell else "arrow")

    def _button_at(self, x: float, y: float) -> str | None:
        for name, (x1, y1, x2, y2) in self.buttons.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                return name
        return None

    def _cell_at(self, x: float, y: float) -> tuple[int, int] | None:
        bx, by, bw, bh = self._board_rect
        if not (bx <= x < bx + bw and by <= y < by + bh):
            return None
        col = int((x - bx) // self._cell_size)
        row = int((y - by) // self._cell_size)
        if 0 <= row < self.state.rows and 0 <= col < self.state.cols:
            return row, col
        return None

    # ------------------------------------------------------------------
    # 动画时钟
    # ------------------------------------------------------------------
    def _tick(self) -> None:
        now = time.monotonic()
        self.animations = [a for a in self.animations if now - a["started"] < a["duration"]]
        self.blocked_effects = {
            cell: until for cell, until in self.blocked_effects.items() if until > now
        }
        self._flying_arrows = len(self.animations)

        if self.hint_arrow is not None and now >= self.hint_until:
            self.hint_arrow = None

        if self.pending_transition is not None and now >= self.pending_transition[0]:
            self.pending_transition = None
            self._finish_level()

        self.render()
        self.after(30, self._tick)

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def render(self) -> None:
        self.buttons.clear()
        self._draw_background()
        if self.screen == "menu":
            self._draw_menu()
        elif self.screen == "game":
            self._draw_game()
        elif self.screen == "complete":
            self._draw_complete()
        elif self.screen == "failed":
            self._draw_failed()

    def _draw_background(self) -> None:
        c = self.canvas
        strips = 32
        for i in range(strips):
            color = blend(BG_TOP, BG_BOTTOM, i / (strips - 1))
            c.create_rectangle(
                0,
                HEIGHT * i / strips,
                WIDTH,
                HEIGHT * (i + 1) / strips + 1,
                fill=color,
                outline="",
            )
        c.create_oval(-190, -230, 360, 250, fill="#DCE8FF", outline="")
        c.create_oval(900, 560, 1210, 850, fill="#D9F1EC", outline="")
        c.create_oval(860, -140, 1040, 40, fill="#FFF0D4", outline="")

    def _rounded_rect(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        radius: float,
        **kwargs: Any,
    ) -> int:
        radius = min(radius, abs(x2 - x1) / 2, abs(y2 - y1) / 2)
        points = [
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        return self.canvas.create_polygon(points, smooth=True, splinesteps=28, **kwargs)

    def _button(
        self,
        name: str,
        text: str,
        x: float,
        y: float,
        w: float,
        h: float,
        fill: str = NAVY,
        fg: str = "#FFFFFF",
        disabled: bool = False,
        small: bool = False,
    ) -> None:
        if disabled:
            fill = "#C8CFDB"
            fg = "#7A8497"
        self._rounded_rect(x + 3, y + 5, x + w + 3, y + h + 5, 13, fill="#B7C1D4", outline="")
        self._rounded_rect(x, y, x + w, y + h, 13, fill=fill, outline="")
        self.canvas.create_text(
            x + w / 2,
            y + h / 2,
            text=text,
            fill=fg,
            font=("Microsoft YaHei UI", 13 if not small else 11, "bold"),
        )
        if not disabled:
            self.buttons[name] = (x, y, x + w, y + h)

    def _draw_menu(self) -> None:
        c = self.canvas
        c.create_text(
            WIDTH / 2,
            92,
            text="一 箭 又 一 箭",
            fill=NAVY,
            font=("Microsoft YaHei UI", 34, "bold"),
        )
        c.create_text(
            WIDTH / 2,
            143,
            text="观察路径 · 排好顺序 · 让所有箭头飞出棋盘",
            fill=MUTED,
            font=("Microsoft YaHei UI", 13),
        )

        # 标题旁装饰箭头
        self._draw_decoration_arrow(132, 93, Direction.RIGHT, "#38B2A3")
        self._draw_decoration_arrow(WIDTH - 132, 93, Direction.LEFT, "#F3A24A")

        self._rounded_rect(212, 202, WIDTH - 212, 442, 24, fill=CARD, outline="#D6DFEE", width=2)
        c.create_text(
            255,
            235,
            text="游戏规则",
            anchor="w",
            fill=INK,
            font=("Microsoft YaHei UI", 17, "bold"),
        )
        rules = (
            "1  点击任意箭头。若它到棋盘边界之间没有其他箭头，它就会飞出并消失。",
            "2  前方存在阻挡时，箭头会抖动变色，并消耗一次失误机会。",
            "3  清空全部箭头即可通关；失误机会耗尽则需要重新开始。",
        )
        for index, text in enumerate(rules):
            y = 278 + index * 43
            c.create_oval(256, y - 5, 266, y + 5, fill=GOLD, outline="")
            c.create_text(
                285,
                y,
                text=text,
                anchor="w",
                fill=INK,
                font=("Microsoft YaHei UI", 12),
            )

        self._button("menu_start", "开 始 游 戏", WIDTH / 2 - 130, 482, 260, 58, NAVY)
        c.create_text(
            WIDTH / 2,
            567,
            text="选择关卡（均可直接进入）",
            fill=MUTED,
            font=("Microsoft YaHei UI", 11),
        )
        total_w = len(LEVELS) * 142 + (len(LEVELS) - 1) * 18
        start_x = WIDTH / 2 - total_w / 2
        for index, level in enumerate(LEVELS):
            x = start_x + index * 160
            self._button(
                f"menu_level_{index}",
                f"{index + 1}  {level.name}",
                x,
                600,
                142,
                48,
                "#FFFFFF" if index else "#E8F0FF",
                NAVY,
                small=True,
            )
            c.create_text(
                x + 71,
                669,
                text=level.subtitle,
                fill=MUTED,
                font=("Microsoft YaHei UI", 9),
            )
        c.create_text(
            WIDTH / 2,
            736,
            text="操作：鼠标点击  ·  快捷键 H 提示 / U 撤销 / R 重开",
            fill="#8A94A9",
            font=("Microsoft YaHei UI", 10),
        )

    def _draw_decoration_arrow(
        self,
        cx: float,
        cy: float,
        direction: Direction,
        color: str,
    ) -> None:
        vectors = {
            Direction.UP: (0, -1),
            Direction.DOWN: (0, 1),
            Direction.LEFT: (-1, 0),
            Direction.RIGHT: (1, 0),
        }
        vx, vy = vectors[direction]
        self.canvas.create_line(
            cx - vx * 18,
            cy - vy * 18,
            cx + vx * 18,
            cy + vy * 18,
            fill=color,
            width=6,
            arrow=tk.LAST,
            arrowshape=(15, 17, 7),
            capstyle=tk.ROUND,
        )

    def _draw_topbar(self) -> None:
        c = self.canvas
        level = LEVELS[self.level_index]
        self._rounded_rect(34, 24, 482, 106, 20, fill=NAVY, outline="")
        c.create_text(
            58,
            47,
            text=f"第 {self.level_index + 1} 关",
            anchor="w",
            fill=GOLD,
            font=("Microsoft YaHei UI", 11, "bold"),
        )
        c.create_text(
            58,
            77,
            text=level.name,
            anchor="w",
            fill="#FFFFFF",
            font=("Microsoft YaHei UI", 20, "bold"),
        )
        c.create_text(
            270,
            76,
            text=level.subtitle,
            anchor="w",
            fill="#BFC9DD",
            font=("Microsoft YaHei UI", 10),
        )

        elapsed = max(0.0, time.monotonic() - self.level_started)
        c.create_text(
            700,
            45,
            text="用时",
            anchor="w",
            fill=MUTED,
            font=("Microsoft YaHei UI", 10),
        )
        c.create_text(
            700,
            76,
            text=f"{int(elapsed) // 60:02d}:{int(elapsed) % 60:02d}",
            anchor="w",
            fill=INK,
            font=("Consolas", 20, "bold"),
        )

        c.create_text(
            835,
            45,
            text="失误机会",
            anchor="w",
            fill=MUTED,
            font=("Microsoft YaHei UI", 10),
        )
        hearts = " ".join(
            "♥" if i < self.state.remaining_misses else "♡"
            for i in range(self.state.max_misses)
        )
        c.create_text(
            835,
            78,
            text=hearts,
            anchor="w",
            fill=RED,
            font=("Segoe UI Symbol", 23, "bold"),
        )
        self._button("game_menu", "首页", WIDTH - 120, 36, 84, 50, "#FFFFFF", NAVY)

    def _board_geometry(self) -> tuple[float, float, float, float]:
        rows, cols = self.state.rows, self.state.cols
        cell = min(77.0, (HEIGHT - 230) / rows)
        bw, bh = cols * cell, rows * cell
        bx = 38 + (700 - bw) / 2
        by = 142 + (590 - bh) / 2
        self._cell_size = cell
        self._board_rect = (bx, by, bw, bh)
        return bx, by, bw, bh

    def _cell_center(self, row: int, col: int) -> tuple[float, float]:
        bx, by, _bw, _bh = self._board_rect
        return bx + (col + 0.5) * self._cell_size, by + (row + 0.5) * self._cell_size

    def _draw_board(self) -> None:
        c = self.canvas
        bx, by, bw, bh = self._board_geometry()
        self._rounded_rect(bx + 7, by + 10, bx + bw + 7, by + bh + 10, 22, fill="#A8B3C9", outline="")
        self._rounded_rect(bx - 8, by - 8, bx + bw + 8, by + bh + 8, 22, fill=BOARD, outline="#10192C", width=2)

        for row in range(self.state.rows):
            for col in range(self.state.cols):
                x1 = bx + col * self._cell_size
                y1 = by + row * self._cell_size
                fill = BOARD_CELL_A if (row + col) % 2 == 0 else BOARD_CELL_B
                c.create_rectangle(
                    x1,
                    y1,
                    x1 + self._cell_size,
                    y1 + self._cell_size,
                    fill=fill,
                    outline=GRID,
                    width=1,
                )

        # 在棋盘边缘提示飞出方向。
        for col in range(self.state.cols):
            cx = bx + (col + 0.5) * self._cell_size
            c.create_text(cx, by - 19, text="↑", fill="#91A4C7", font=("Segoe UI Symbol", 12, "bold"))
            c.create_text(cx, by + bh + 19, text="↓", fill="#91A4C7", font=("Segoe UI Symbol", 12, "bold"))
        for row in range(self.state.rows):
            cy = by + (row + 0.5) * self._cell_size
            c.create_text(bx - 19, cy, text="←", fill="#91A4C7", font=("Segoe UI Symbol", 12, "bold"))
            c.create_text(bx + bw + 19, cy, text="→", fill="#91A4C7", font=("Segoe UI Symbol", 12, "bold"))

        now = time.monotonic()
        for arrow in self.state.arrows:
            x, y = self._cell_center(arrow.row, arrow.col)
            blocked = self.blocked_effects.get((arrow.row, arrow.col))
            dx = dy = 0.0
            if blocked is not None:
                remain = max(0.0, blocked - now)
                phase = (0.52 - remain) * 4.5
                dx = math.sin(phase * math.pi * 2) * 8 * min(1.0, remain / 0.18)
            if self.hover_cell == (arrow.row, arrow.col) and not self.animations:
                dy = -3
            if self.hint_arrow == arrow:
                pulse = 4 + 3 * (0.5 + 0.5 * math.sin(now * 8))
                self._rounded_rect(
                    x - self._cell_size / 2 + 5 - pulse,
                    y - self._cell_size / 2 + 5 - pulse,
                    x + self._cell_size / 2 - 5 + pulse,
                    y + self._cell_size / 2 - 5 + pulse,
                    14,
                    fill="",
                    outline=GOLD,
                    width=4,
                )
            color = RED if blocked is not None else DIR_COLORS[arrow.direction]
            self._draw_arrow_shape(x + dx, y + dy, self._cell_size * 0.74, arrow.direction, color)

    def _draw_arrow_shape(
        self,
        cx: float,
        cy: float,
        size: float,
        direction: Direction,
        color: str,
        shadow: bool = True,
    ) -> None:
        half = size / 2
        if shadow:
            self._rounded_rect(
                cx - half + 4,
                cy - half + 6,
                cx + half + 4,
                cy + half + 6,
                size * 0.22,
                fill="#10182B",
                outline="",
            )
        self._rounded_rect(
            cx - half,
            cy - half,
            cx + half,
            cy + half,
            size * 0.22,
            fill=color,
            outline=blend(color, "#FFFFFF", 0.27),
            width=2,
        )
        # 上方高光让箭头看起来更立体。
        self._rounded_rect(
            cx - half + 7,
            cy - half + 6,
            cx + half - 7,
            cy - half + max(10, size * 0.18),
            size * 0.12,
            fill=blend(color, "#FFFFFF", 0.18),
            outline="",
        )

        vectors = {
            Direction.UP: (0, -1),
            Direction.DOWN: (0, 1),
            Direction.LEFT: (-1, 0),
            Direction.RIGHT: (1, 0),
        }
        vx, vy = vectors[direction]
        length = size * 0.52
        start = (cx - vx * length * 0.36, cy - vy * length * 0.36)
        end = (cx + vx * length * 0.48, cy + vy * length * 0.48)
        self.canvas.create_line(
            *start,
            *end,
            fill="#FFFFFF",
            width=max(4, int(size * 0.085)),
            arrow=tk.LAST,
            arrowshape=(size * 0.18, size * 0.22, size * 0.09),
            capstyle=tk.ROUND,
            joinstyle=tk.ROUND,
        )

    def _draw_sidebar(self) -> None:
        c = self.canvas
        x, y, w, h = 760.0, 142.0, 320.0, 590.0
        self._rounded_rect(x + 5, y + 8, x + w + 5, y + h + 8, 22, fill="#B7C1D4", outline="")
        self._rounded_rect(x, y, x + w, y + h, 22, fill=CARD, outline="#D6DFEE", width=2)
        c.create_text(
            x + 24,
            y + 33,
            text="本关进度",
            anchor="w",
            fill=INK,
            font=("Microsoft YaHei UI", 18, "bold"),
        )
        c.create_text(
            x + 24,
            y + 68,
            text=f"剩余箭头  {self.state.remaining_arrows}",
            anchor="w",
            fill=MUTED,
            font=("Microsoft YaHei UI", 11),
        )
        progress = 1 - self.state.remaining_arrows / len(LEVELS[self.level_index].arrows)
        bar_x, bar_y, bar_w, bar_h = x + 24, y + 88, w - 48, 10
        self._rounded_rect(bar_x, bar_y, bar_x + bar_w, bar_y + bar_h, 5, fill="#E5EAF3", outline="")
        if progress > 0:
            self._rounded_rect(
                bar_x,
                bar_y,
                bar_x + max(10, bar_w * progress),
                bar_y + bar_h,
                5,
                fill=GREEN,
                outline="",
            )

        stats = (
            ("已飞出", str(len(self.state.history))),
            ("失误", f"{self.state.misses} / {self.state.max_misses}"),
            ("点击", str(self.total_clicks)),
        )
        for index, (label, value) in enumerate(stats):
            sx = x + 22 + index * 94
            sy = y + 124
            c.create_text(sx, sy, text=label, anchor="w", fill=MUTED, font=("Microsoft YaHei UI", 9))
            c.create_text(sx, sy + 28, text=value, anchor="w", fill=INK, font=("Microsoft YaHei UI", 17, "bold"))

        c.create_line(x + 24, y + 186, x + w - 24, y + 186, fill="#E3E8F1")
        c.create_text(
            x + 24,
            y + 214,
            text="方向颜色",
            anchor="w",
            fill=INK,
            font=("Microsoft YaHei UI", 12, "bold"),
        )
        for index, direction in enumerate((Direction.UP, Direction.DOWN, Direction.LEFT, Direction.RIGHT)):
            lx = x + 28 + (index % 2) * 142
            ly = y + 254 + (index // 2) * 42
            c.create_oval(lx, ly - 7, lx + 14, ly + 7, fill=DIR_COLORS[direction], outline="")
            c.create_text(
                lx + 25,
                ly,
                text=f"{DIR_NAMES[direction]}向",
                anchor="w",
                fill=MUTED,
                font=("Microsoft YaHei UI", 10),
            )

        disabled = bool(self.animations or self.pending_transition)
        self._button(
            "game_hint",
            "提示（H）",
            x + 24,
            y + 350,
            w - 48,
            48,
            "#FFF6D8",
            "#735B10",
            disabled=disabled,
        )
        self._button(
            "game_undo",
            "撤销上一步（U）",
            x + 24,
            y + 413,
            w - 48,
            48,
            "#E8F2FF",
            "#2C5E9D",
            disabled=disabled or not self.state.history,
        )
        self._button(
            "game_restart",
            "重新开始（R）",
            x + 24,
            y + 476,
            w - 48,
            48,
            NAVY,
            "#FFFFFF",
        )
        c.create_text(
            x + 24,
            y + 552,
            text="目标：清空棋盘。提示会高亮当前可飞出的箭头。",
            anchor="w",
            fill=MUTED,
            font=("Microsoft YaHei UI", 9),
            width=w - 48,
        )

    def _draw_flying_arrows(self) -> None:
        now = time.monotonic()
        for animation in self.animations:
            raw = min(1.0, (now - animation["started"]) / animation["duration"])
            eased = 1 - (1 - raw) ** 3
            x1, y1 = animation["start"]
            x2, y2 = animation["end"]
            x = x1 + (x2 - x1) * eased
            y = y1 + (y2 - y1) * eased
            arrow: Arrow = animation["arrow"]
            size = self._cell_size * (0.74 - 0.18 * raw)
            self._draw_arrow_shape(x, y, size, arrow.direction, DIR_COLORS[arrow.direction], shadow=False)

    def _draw_toast(self) -> None:
        if not self.toast_text or time.monotonic() >= self.toast_until:
            return
        text = self.toast_text
        # 根据文字长度估算宽度，保持居中。
        width = max(210, min(510, 22 * len(text) + 44))
        x = WIDTH / 2
        y = 690
        self._rounded_rect(x - width / 2, y - 23, x + width / 2, y + 23, 18, fill=self.toast_color, outline="")
        self.canvas.create_text(
            x,
            y,
            text=text,
            fill="#FFFFFF",
            font=("Microsoft YaHei UI", 11, "bold"),
        )

    def _draw_game(self) -> None:
        self._draw_topbar()
        self._draw_board()
        self._draw_sidebar()
        self._draw_flying_arrows()
        self._draw_toast()

    def _draw_result_shell(self, won: bool) -> None:
        c = self.canvas
        c.create_oval(WIDTH / 2 - 75, 83, WIDTH / 2 + 75, 233, fill="#E9F4FF" if won else "#FFEBEC", outline="")
        c.create_text(
            WIDTH / 2,
            158,
            text="✓" if won else "×",
            fill=GREEN if won else RED,
            font=("Segoe UI Symbol", 54, "bold"),
        )
        title = "全部关卡完成" if won and self.level_index == len(LEVELS) - 1 else "关卡完成" if won else "挑战失败"
        subtitle = (
            "你已经掌握了整条箭头链的出题逻辑。"
            if won and self.level_index == len(LEVELS) - 1
            else "棋盘已清空，下一关正在等你。"
            if won
            else "失误机会已经耗尽，观察清楚后再试一次。"
        )
        c.create_text(WIDTH / 2, 278, text=title, fill=INK, font=("Microsoft YaHei UI", 30, "bold"))
        c.create_text(WIDTH / 2, 320, text=subtitle, fill=MUTED, font=("Microsoft YaHei UI", 12))

        card_x, card_y, card_w, card_h = WIDTH / 2 - 285, 365, 570, 126
        self._rounded_rect(card_x, card_y, card_x + card_w, card_y + card_h, 20, fill=CARD, outline="#D6DFEE", width=2)
        elapsed = self.result.get("elapsed", 0.0)
        values = (
            ("用时", f"{int(elapsed) // 60:02d}:{int(elapsed) % 60:02d}"),
            ("飞出箭头", str(self.result.get("moves", 0))),
            ("失误次数", str(self.result.get("misses", 0))),
            ("点击次数", str(self.result.get("clicks", 0))),
        )
        for index, (label, value) in enumerate(values):
            x = card_x + 72 + index * 142
            c.create_text(x, card_y + 38, text=label, fill=MUTED, font=("Microsoft YaHei UI", 10))
            c.create_text(x, card_y + 78, text=value, fill=INK, font=("Microsoft YaHei UI", 19, "bold"))

        if won and self.level_index + 1 < len(LEVELS):
            self._button("complete_next", "进入下一关", WIDTH / 2 - 240, 540, 210, 56, NAVY)
            self._button("complete_replay", "再玩一次", WIDTH / 2 + 30, 540, 210, 56, "#FFFFFF", NAVY)
        elif won:
            self._button("complete_replay", "再玩一次", WIDTH / 2 - 130, 540, 260, 56, NAVY)
            self._button("complete_menu", "返回首页", WIDTH / 2 - 130, 615, 260, 48, "#FFFFFF", NAVY)
        else:
            self._button("failed_retry", "重新开始", WIDTH / 2 - 240, 540, 210, 56, NAVY)
            self._button("failed_menu", "返回首页", WIDTH / 2 + 30, 540, 210, 56, "#FFFFFF", NAVY)

        if won and self.level_index + 1 < len(LEVELS):
            self._button("complete_menu", "返回首页", WIDTH / 2 - 130, 620, 260, 48, "#FFFFFF", NAVY)

    def _draw_complete(self) -> None:
        self._draw_result_shell(won=True)

    def _draw_failed(self) -> None:
        self._draw_result_shell(won=False)
