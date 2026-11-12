"""程序用到的各个位置，源码运行与打包运行通用。"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from app import config


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> str:
    """打包运行时是 exe 所在的文件夹，源码运行时是项目根目录。"""
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_dir() -> str:
    """随程序发布的只读资源所在的文件夹。"""
    if is_frozen():
        return sys._MEIPASS
    return app_dir()


def assets_dir() -> str:
    return os.path.join(resource_dir(), "assets")


def user_data_dir() -> str:
    return os.path.join(os.environ["LOCALAPPDATA"], config.APP_NAME)


def default_output_dir() -> str:
    return os.path.join(app_dir(), "output")


def credentials_file() -> str:
    return os.path.join(app_dir(), config.CREDENTIALS_FILENAME)


def settings_file() -> str:
    return os.path.join(user_data_dir(), "settings.json")


def log_file() -> str:
    return os.path.join(user_data_dir(), "app.log")


def setup_logging() -> None:
    """日志写入文件，打包后的窗口程序没有控制台。"""
    os.makedirs(user_data_dir(), exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[RotatingFileHandler(log_file(), maxBytes=512 * 1024, backupCount=1,
                                      encoding="utf-8")],
    )
