"""工具栏、状态栏与可以收起的日志。"""

from __future__ import annotations

import os

from imgui_bundle import imgui, portable_file_dialogs as pfd

from app.i18n import tr
from app.planning import format_clock
from app.ui import theme, widgets
from app.ui.state import AppState
from app.ui.theme import px

TOOLBAR_HEIGHT = 40
STATUS_HEIGHT = 26
LOG_HEIGHT = 150
_NO_SCROLL = int(imgui.WindowFlags_.no_scrollbar)


def _centre_y(height: float) -> float:
    return (px(height) - imgui.get_text_line_height()) / 2


def toolbar(state: AppState, width: float) -> None:
    imgui.push_style_color(int(imgui.Col_.child_bg), theme.PANEL)
    imgui.begin_child("toolbar", imgui.ImVec2(width, px(TOOLBAR_HEIGHT)), window_flags=_NO_SCROLL)
    origin = imgui.get_cursor_screen_pos()
    y = _centre_y(TOOLBAR_HEIGHT)
    info = state.info

    imgui.set_cursor_pos(imgui.ImVec2(px(16), y))
    if info is None:
        widgets.text(tr(state.language, "no_video"), theme.TEXT_DIM)
    else:
        widgets.text(os.path.basename(info.path))
        imgui.same_line(0, px(14))
        widgets.mono_text(
            f"{info.width}×{info.height}  {info.fps:.0f} fps  {format_clock(info.duration_s)}",
            theme.TEXT_DIM)
    imgui.same_line(0, px(18))
    imgui.begin_disabled(state.busy)
    if widgets.link(tr(state.language, "open")):
        chosen = pfd.open_file(
            tr(state.language, "pick_video_title"), "",
            [tr(state.language, "video_files"), state.supported_filter(),
             tr(state.language, "all_files"), "*"],
        ).result()
        if chosen:
            state.open_video(chosen[0])
    imgui.end_disabled()

    _language_switch(state, width, y)
    imgui.get_window_draw_list().add_rect_filled(
        imgui.ImVec2(origin.x, origin.y + px(TOOLBAR_HEIGHT) - 1),
        imgui.ImVec2(origin.x + width, origin.y + px(TOOLBAR_HEIGHT)), theme.u32(theme.LINE))
    imgui.end_child()
    imgui.pop_style_color()


def _language_switch(state: AppState, width: float, y: float) -> None:
    labels = (("zh", "中文"), ("en", "EN"))
    total = sum(imgui.calc_text_size(label).x for _, label in labels) + px(22)
    imgui.set_cursor_pos(imgui.ImVec2(width - px(16) - total, y))
    for index, (code, label) in enumerate(labels):
        if index:
            imgui.same_line(0, px(8))
            widgets.text("/", theme.LINE_STRONG)
            imgui.same_line(0, px(8))
        if state.language == code:
            widgets.text(label)
        elif widgets.link(f"{label}##lang_{code}", theme.TEXT_DIM):
            state.language = code


def log_panel(state: AppState, width: float) -> None:
    imgui.push_style_color(int(imgui.Col_.child_bg), theme.STAGE)
    imgui.begin_child("log", imgui.ImVec2(width, px(LOG_HEIGHT)))
    origin = imgui.get_cursor_screen_pos()
    imgui.get_window_draw_list().add_rect_filled(
        origin, imgui.ImVec2(origin.x + width, origin.y + 1), theme.u32(theme.LINE))
    imgui.set_cursor_pos(imgui.ImVec2(px(14), px(8)))
    imgui.begin_group()
    for key, params in state.log[-200:]:
        color = theme.DANGER if key.startswith("err_") else theme.TEXT_SOFT
        widgets.text(tr(state.language, key, **params), color)
    imgui.end_group()
    if imgui.get_scroll_y() >= imgui.get_scroll_max_y() - px(40):
        imgui.set_scroll_here_y(1.0)
    imgui.end_child()
    imgui.pop_style_color()


def status_bar(state: AppState, width: float) -> None:
    imgui.push_style_color(int(imgui.Col_.child_bg), theme.STAGE)
    imgui.begin_child("status", imgui.ImVec2(width, px(STATUS_HEIGHT)), window_flags=_NO_SCROLL)
    origin = imgui.get_cursor_screen_pos()
    draw = imgui.get_window_draw_list()
    draw.add_rect_filled(origin, imgui.ImVec2(origin.x + width, origin.y + 1), theme.u32(theme.LINE))
    if state.busy:
        draw.add_rect_filled(origin, imgui.ImVec2(origin.x + width * state.progress, origin.y + px(2)),
                             theme.u32(theme.ACCENT))
    y = _centre_y(STATUS_HEIGHT)
    key, params = state.status
    imgui.set_cursor_pos(imgui.ImVec2(px(14), y))
    widgets.text(tr(state.language, key, **params),
                 theme.DANGER if state.status_is_error else theme.TEXT_SOFT)

    log_label = tr(state.language, "log")
    x = width - px(14) - imgui.calc_text_size(log_label).x
    imgui.set_cursor_pos(imgui.ImVec2(x, y))
    if widgets.link(log_label, theme.TEXT if state.show_log else theme.TEXT_DIM):
        state.show_log = not state.show_log
    if state.busy:
        cancel_label = tr(state.language, "cancel")
        x -= px(18) + imgui.calc_text_size(cancel_label).x
        imgui.set_cursor_pos(imgui.ImVec2(x, y))
        if widgets.link(cancel_label):
            state.cancel()
        percent = f"{round(state.progress * 100)}%"
        x -= px(18) + widgets.mono_width(percent)
        imgui.set_cursor_pos(imgui.ImVec2(x, y + px(1)))
        widgets.mono_text(percent, theme.TEXT_SOFT)
    imgui.end_child()
    imgui.pop_style_color()
