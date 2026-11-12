"""GIF 文件的两个小操作。"""

from __future__ import annotations

import os

from PIL import Image

# Steam 的艺术作品上传只在文件最后一个字节（GIF trailer 0x3B）被替换成 0x21 时
# 才接受这种竖长的展柜 GIF。浏览器与 Steam 仍然能播放，因为全部帧在此之前已经读完。
SHOWCASE_TRAILER = b"\x21"


def stamp_trailer(gif_path: str) -> None:
    """把文件的最后一个字节改写成 SHOWCASE_TRAILER。"""
    if os.path.getsize(gif_path) == 0:
        raise ValueError(f"GIF 文件为空: {gif_path}")
    with open(gif_path, "rb+") as handle:
        handle.seek(-1, os.SEEK_END)
        handle.write(SHOWCASE_TRAILER)


def gif_dimensions(gif_path: str) -> tuple[int, int]:
    with Image.open(gif_path) as image:
        return image.size
