"""SteamBoardClip 入口：python SteamBoardClip.py"""

import sys


def main() -> int:
    arguments = sys.argv[1:]
    if arguments and arguments[0] == "--export":
        from app.cli import run_export

        return run_export(arguments[1:])
    from app.ui.app import main as run_app

    run_app()
    return 0


if __name__ == "__main__":
    sys.exit(main())
