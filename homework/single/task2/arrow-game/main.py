"""程序入口：运行 python main.py 即可启动游戏。"""

from arrow_game.app import ArrowGameApp


def main() -> None:
    app = ArrowGameApp()
    app.mainloop()


if __name__ == "__main__":
    main()
