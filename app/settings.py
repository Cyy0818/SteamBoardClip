"""保存在 JSON 文件里的用户设置。"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields

from app import config

LANGUAGES = ("zh", "en")
DEFAULT_LIMIT_MB = round(config.MAX_GIF_BYTES / 1048576, 2)


@dataclass(frozen=True)
class Settings:
    language: str = "zh"
    output_dir: str = ""  # 空字符串表示程序旁边的 output 文件夹
    prefix: str = config.DEFAULT_OUTPUT_PREFIX
    use_title: bool = False  # 关闭时上传的条目不显示名称
    workshop_title: str = config.DEFAULT_WORKSHOP_TITLE
    browser: str = config.BROWSERS[0]
    keep_aspect: bool = True
    show_guides: bool = True
    fps_limit: int = 0
    scale_percent: int = 100
    colors: int = 256
    limit_mb: float = DEFAULT_LIMIT_MB


def validate(settings: Settings) -> None:
    """设置文件内容不合法时抛出 ValueError。"""
    for item in fields(Settings):
        value = getattr(settings, item.name)
        expected = type(getattr(Settings(), item.name))
        if type(value) is not expected:
            raise ValueError(f"设置项 {item.name} 的类型应为 {expected.__name__}")
    checks = {
        "language": settings.language in LANGUAGES,
        "browser": settings.browser in config.BROWSERS,
        "fps_limit": settings.fps_limit in config.FPS_LIMIT_CHOICES,
        "scale_percent": settings.scale_percent in config.SCALE_PERCENT_CHOICES,
        "colors": settings.colors in config.COLOR_CHOICES,
        "limit_mb": config.MIN_LIMIT_MB <= settings.limit_mb <= DEFAULT_LIMIT_MB,
    }
    for name, passed in checks.items():
        if not passed:
            raise ValueError(f"设置项 {name} 的值无效: {getattr(settings, name)!r}")


def load(path: str) -> Settings:
    """读取设置。文件不存在说明是第一次运行，返回默认值。"""
    if not os.path.exists(path):
        return Settings()
    with open(path, "r", encoding="utf-8") as handle:
        saved = json.load(handle)
    # 设置文件可能由另一个版本的程序写出，当前版本没有的设置项不读取。
    known = {item.name for item in fields(Settings)}
    settings = Settings(**{name: value for name, value in saved.items() if name in known})
    validate(settings)
    return settings


def save(path: str, settings: Settings) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(asdict(settings), handle, ensure_ascii=False, indent=2)
