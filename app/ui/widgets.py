"""可以重复使用的小绘制函数。"""

from __future__ import annotations

from contextlib import contextmanager

from imgui_bundle import imgui

from app.ui import theme
from app.ui.theme import px


@contextmanager
def mono():
    """时间码与体积使用等宽数字。"""
    imgui.push_font(theme.mono_font(), 0.0)
    try:
        yield
    finally:
        imgui.pop_font()


def text(label: str, color: imgui.ImVec4 = theme.TEXT) -> None:
    imgui.text_colored(color, label)


def mono_text(label: str, color: imgui.ImVec4 = theme.TEXT) -> None:
    with mono():
        imgui.text_colored(color, label)


def mono_width(label: str) -> float:
    with mono():
        return imgui.calc_text_size(label).x


def link(label: str, color: imgui.ImVec4 = theme.ACCENT) -> bool:
    """可以点击的纯文字，鼠标悬停时变亮。"""
    visible = label.split("##")[0]
    size = imgui.calc_text_size(visible)
    origin = imgui.get_cursor_screen_pos()
    clicked = imgui.invisible_button(label, size)
    hovered = imgui.is_item_hovered()
    if hovered:
        imgui.set_mouse_cursor(int(imgui.MouseCursor_.hand))
    shade = theme.WHITE if hovered else color
    imgui.get_window_draw_list().add_text(origin, theme.u32(shade), visible)
    return clicked


def primary_button(label: str, size: imgui.ImVec2) -> bool:
    colors = (
        (imgui.Col_.button, theme.ACCENT),
        (imgui.Col_.button_hovered, theme.ACCENT_HOVER),
        (imgui.Col_.button_active, theme.ACCENT_ACTIVE),
        (imgui.Col_.text, theme.ON_ACCENT),
        (imgui.Col_.border, theme.CLEAR),
    )
    for index, color in colors:
        imgui.push_style_color(int(index), color)
    clicked = imgui.button(label, size)
    imgui.pop_style_color(len(colors))
    return clicked


def outline_button(label: str, size: imgui.ImVec2) -> bool:
    imgui.push_style_color(int(imgui.Col_.border), theme.LINE_STRONG)
    clicked = imgui.button(label, size)
    imgui.pop_style_color()
    return clicked


def toggle(str_id: str, value: bool) -> tuple[bool, bool]:
    """手绘的开关，返回 (是否被点击, 新的值)。"""
    width, height = px(30), px(16)
    origin = imgui.get_cursor_screen_pos()
    clicked = imgui.invisible_button(str_id, imgui.ImVec2(width, height))
    if clicked:
        value = not value
    draw = imgui.get_window_draw_list()
    track = theme.ACCENT if value else theme.LINE_STRONG
    draw.add_rect_filled(origin, imgui.ImVec2(origin.x + width, origin.y + height),
                         theme.u32(track), height / 2)
    knob_x = origin.x + (width - height / 2 if value else height / 2)
    draw.add_circle_filled(imgui.ImVec2(knob_x, origin.y + height / 2), height / 2 - px(2),
                           theme.u32(theme.STAGE if value else theme.TEXT_SOFT))
    return clicked, value


def hairline(width: float) -> None:
    origin = imgui.get_cursor_screen_pos()
    imgui.get_window_draw_list().add_rect_filled(
        origin, imgui.ImVec2(origin.x + width, origin.y + 1), theme.u32(theme.LINE))
    imgui.dummy(imgui.ImVec2(width, 1))
