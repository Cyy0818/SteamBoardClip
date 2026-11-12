"""颜色、尺寸与字体：中性炭灰色加一种强调色。"""

from __future__ import annotations

import os

from imgui_bundle import hello_imgui, imgui

BASE_FONT_SIZE = 16.0
MONO_FONT_SIZE = 14.0


def _rgb(hex_color: str, alpha: float = 1.0) -> imgui.ImVec4:
    value = hex_color.lstrip("#")
    red, green, blue = (int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return imgui.ImVec4(red, green, blue, alpha)


WINDOW = _rgb("#1e1f22")
STAGE = _rgb("#17181a")
PANEL = _rgb("#232427")
FIELD = _rgb("#1a1b1e")
LINE = _rgb("#34363b")
LINE_STRONG = _rgb("#4a4d53")
TEXT = _rgb("#dcdde0")
TEXT_SOFT = _rgb("#a9acb2")
TEXT_DIM = _rgb("#6f7278")
ACCENT = _rgb("#66c0f4")
ACCENT_HOVER = _rgb("#86cff8")
ACCENT_ACTIVE = _rgb("#4fa9dd")
ON_ACCENT = _rgb("#12202b")
DANGER = _rgb("#e5746a")
WHITE = _rgb("#ffffff")
PLACEHOLDER = _rgb("#232427")
CLEAR = imgui.ImVec4(0, 0, 0, 0)

# Windows 自带的字体：微软雅黑显示中文，Consolas 显示等宽数字。
_UI_FONT = "msyh.ttc"
_MONO_FONT = "consola.ttf"

_fonts: dict[str, imgui.ImFont] = {}


def u32(color: imgui.ImVec4, alpha: float | None = None) -> int:
    if alpha is not None:
        color = imgui.ImVec4(color.x, color.y, color.z, alpha)
    return imgui.color_convert_float4_to_u32(color)


def px(value: float) -> float:
    """把设计稿里的像素换算到当前字号，布局随 DPI 缩放。"""
    return value * imgui.get_font_size() / BASE_FONT_SIZE


def mono_font() -> imgui.ImFont:
    return _fonts["mono"]


def _system_font(name: str) -> str:
    path = os.path.join(os.environ["WINDIR"], "Fonts", name)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"缺少系统字体: {path}")
    return path


def load_fonts() -> None:
    """hello_imgui 的字体回调，第一个加载的字体是默认字体。"""
    params = hello_imgui.FontLoadingParams()
    params.inside_assets = False  # 使用系统字体的绝对路径
    hello_imgui.load_font(_system_font(_UI_FONT), BASE_FONT_SIZE, params)
    _fonts["mono"] = hello_imgui.load_font(_system_font(_MONO_FONT), MONO_FONT_SIZE, params)


def apply_style() -> None:
    style = imgui.get_style()
    style.window_rounding = 0.0
    style.child_rounding = 0.0
    style.frame_rounding = 3.0
    style.popup_rounding = 3.0
    style.grab_rounding = 3.0
    style.scrollbar_rounding = 3.0
    style.window_border_size = 0.0
    style.child_border_size = 0.0
    style.frame_border_size = 1.0
    style.popup_border_size = 1.0
    style.scrollbar_size = 10.0
    style.frame_padding = imgui.ImVec2(9, 5)
    style.item_spacing = imgui.ImVec2(8, 8)
    style.window_padding = imgui.ImVec2(0, 0)

    palette = {
        imgui.Col_.text: TEXT,
        imgui.Col_.text_disabled: TEXT_DIM,
        imgui.Col_.window_bg: WINDOW,
        imgui.Col_.child_bg: CLEAR,
        imgui.Col_.popup_bg: PANEL,
        imgui.Col_.border: LINE,
        imgui.Col_.frame_bg: FIELD,
        imgui.Col_.frame_bg_hovered: _rgb("#202226"),
        imgui.Col_.frame_bg_active: _rgb("#26282d"),
        imgui.Col_.button: CLEAR,
        imgui.Col_.button_hovered: _rgb("#2c2e33"),
        imgui.Col_.button_active: _rgb("#34363b"),
        imgui.Col_.header: _rgb("#2c2e33"),
        imgui.Col_.header_hovered: _rgb("#34363b"),
        imgui.Col_.header_active: _rgb("#3c3f45"),
        imgui.Col_.check_mark: ACCENT,
        imgui.Col_.slider_grab: ACCENT,
        imgui.Col_.slider_grab_active: ACCENT_HOVER,
        imgui.Col_.separator: LINE,
        imgui.Col_.scrollbar_bg: CLEAR,
        imgui.Col_.scrollbar_grab: LINE,
        imgui.Col_.scrollbar_grab_hovered: LINE_STRONG,
        imgui.Col_.scrollbar_grab_active: LINE_STRONG,
        imgui.Col_.text_selected_bg: _rgb("#66c0f4", 0.35),
        imgui.Col_.nav_cursor: ACCENT,
    }
    for index, color in palette.items():
        style.set_color_(int(index), color)
