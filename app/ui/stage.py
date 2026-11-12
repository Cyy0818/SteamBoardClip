"""左侧：按实际尺寸显示的展柜预览，以及选择片段的时间轴。"""

from __future__ import annotations

from imgui_bundle import imgui

from app import config, planning
from app.planning import format_clock
from app.ui import theme, widgets
from app.ui.state import AppState
from app.ui.texture import Texture
from app.ui.theme import px

_RULER_STEPS = (5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600)
_HANDLE_GRAB = 9.0
_PREVIEW = Texture()
_FILMSTRIP = Texture()


def draw(state: AppState, size: imgui.ImVec2) -> None:
    imgui.push_style_color(int(imgui.Col_.child_bg), theme.STAGE)
    imgui.begin_child("stage", size, window_flags=int(imgui.WindowFlags_.no_scrollbar))
    origin = imgui.get_cursor_screen_pos()

    # 空间足够时预览按实际输出尺寸显示。
    scale = min(px(1), (size.x - px(48)) / config.CANVAS_WIDTH,
                (size.y - px(250)) / config.CANVAS_HEIGHT)
    scale = max(scale, 0.2)
    width, height = config.CANVAS_WIDTH * scale, config.CANVAS_HEIGHT * scale
    left = origin.x + (size.x - width) / 2
    top = origin.y + px(40)

    _draw_caption(state, left, top - px(22), width)
    _draw_preview(state, left, top, width, height, scale)
    _draw_column_numbers(left, top + height + px(6), scale)
    _draw_timeline(state, left, top + height + px(44), width)

    imgui.end_child()
    imgui.pop_style_color()


def _draw_caption(state: AppState, left: float, top: float, width: float) -> None:
    imgui.set_cursor_screen_pos(imgui.ImVec2(left, top))
    widgets.mono_text(f"{config.CANVAS_WIDTH} × {config.CANVAS_HEIGHT}", theme.TEXT_DIM)
    if state.result is not None:
        label = f"{state.result.fps} fps"
        imgui.set_cursor_screen_pos(imgui.ImVec2(left + width - widgets.mono_width(label), top))
        widgets.mono_text(label, theme.TEXT_DIM)


def _draw_preview(state: AppState, left: float, top: float, width: float, height: float,
                  scale: float) -> None:
    draw = imgui.get_window_draw_list()
    frame = state.preview.frame
    imgui.set_cursor_screen_pos(imgui.ImVec2(left, top))
    if frame is not None:
        if state.frame_dirty:
            _PREVIEW.upload(frame)
            state.frame_dirty = False
        _PREVIEW.draw(width, height)
    else:
        draw.add_rect_filled(imgui.ImVec2(left, top), imgui.ImVec2(left + width, top + height),
                             theme.u32(theme.PLACEHOLDER))
        imgui.dummy(imgui.ImVec2(width, height))
    if state.show_guides:
        gutter = theme.u32(theme.STAGE)
        for _, x2 in planning.segment_boxes()[:-1]:
            draw.add_rect_filled(
                imgui.ImVec2(left + x2 * scale, top),
                imgui.ImVec2(left + (x2 + config.SEGMENT_GAP_PX) * scale, top + height), gutter)


def _draw_column_numbers(left: float, top: float, scale: float) -> None:
    for index, (x1, x2) in enumerate(planning.segment_boxes(), start=1):
        label = str(index)
        centre = left + (x1 + x2) / 2 * scale
        imgui.set_cursor_screen_pos(imgui.ImVec2(centre - widgets.mono_width(label) / 2, top))
        widgets.mono_text(label, theme.TEXT_DIM)


def _ruler_step(duration: int) -> int:
    for step in _RULER_STEPS:
        if duration / step <= 6:
            return step
    return _RULER_STEPS[-1]


def _draw_timeline(state: AppState, left: float, top: float, width: float) -> None:
    draw = imgui.get_window_draw_list()
    info = state.info
    duration = info.duration_s if info else 0
    strip_top = top + px(24)
    strip_height = px(56)
    strip_bottom = strip_top + strip_height

    def to_x(seconds: float) -> float:
        return left + (seconds / duration * width if duration else 0.0)

    # 刻度
    if duration:
        step = _ruler_step(duration)
        for mark in range(0, duration + 1, step):
            x = to_x(mark)
            draw.add_line(imgui.ImVec2(x, top + px(12)), imgui.ImVec2(x, top + px(20)),
                          theme.u32(theme.LINE_STRONG))
            if x + px(44) < left + width:
                imgui.set_cursor_screen_pos(imgui.ImVec2(x + px(4), top - px(2)))
                widgets.mono_text(format_clock(mark), theme.TEXT_DIM)

    # 缩略图条
    imgui.set_cursor_screen_pos(imgui.ImVec2(left, strip_top))
    if state.filmstrip is not None:
        if state.filmstrip_dirty:
            _FILMSTRIP.upload(state.filmstrip)
            state.filmstrip_dirty = False
        _FILMSTRIP.draw(width, strip_height)
    else:
        draw.add_rect_filled(imgui.ImVec2(left, strip_top), imgui.ImVec2(left + width, strip_bottom),
                             theme.u32(theme.PLACEHOLDER))

    if duration:
        _handle_timeline_input(state, left, strip_top, width, strip_height, duration)
        start_x, end_x = to_x(state.start_s), to_x(state.end_s)
        dim = theme.u32(theme.STAGE, 0.72)
        draw.add_rect_filled(imgui.ImVec2(left, strip_top), imgui.ImVec2(start_x, strip_bottom), dim)
        draw.add_rect_filled(imgui.ImVec2(end_x, strip_top), imgui.ImVec2(left + width, strip_bottom), dim)
        accent = theme.u32(theme.ACCENT)
        draw.add_rect(imgui.ImVec2(start_x, strip_top), imgui.ImVec2(end_x, strip_bottom), accent)
        grip = px(7)
        for x in (start_x - grip, end_x):
            draw.add_rect_filled(imgui.ImVec2(x, strip_top - 1), imgui.ImVec2(x + grip, strip_bottom + 1), accent)
            draw.add_line(imgui.ImVec2(x + grip / 2, strip_top + strip_height * 0.38),
                          imgui.ImVec2(x + grip / 2, strip_top + strip_height * 0.62),
                          theme.u32(theme.STAGE))
        head = to_x(min(max(state.preview.position_s, state.start_s), state.end_s))
        white = theme.u32(theme.WHITE)
        draw.add_line(imgui.ImVec2(head, strip_top - px(8)), imgui.ImVec2(head, strip_bottom + px(6)), white)
        draw.add_triangle_filled(imgui.ImVec2(head - px(4.5), strip_top - px(8)),
                                 imgui.ImVec2(head + px(4.5), strip_top - px(8)),
                                 imgui.ImVec2(head, strip_top - px(2)), white)

    _draw_transport(state, left, strip_bottom + px(20), width)


def _handle_timeline_input(state: AppState, left: float, top: float, width: float,
                           height: float, duration: int) -> None:
    pad = px(_HANDLE_GRAB)
    imgui.set_cursor_screen_pos(imgui.ImVec2(left - pad, top - px(8)))
    imgui.invisible_button("##timeline", imgui.ImVec2(width + pad * 2, height + px(16)))
    mouse_x = imgui.get_io().mouse_pos.x
    start_x = left + state.start_s / duration * width
    end_x = left + state.end_s / duration * width
    near_start, near_end = abs(mouse_x - start_x) <= pad, abs(mouse_x - end_x) <= pad

    if imgui.is_item_hovered() and (near_start or near_end):
        imgui.set_mouse_cursor(int(imgui.MouseCursor_.resize_ew))
    if imgui.is_item_activated() and not state.busy:
        if near_start and near_end:
            state.drag_target = "start" if mouse_x < (start_x + end_x) / 2 else "end"
        else:
            state.drag_target = "start" if near_start else "end" if near_end else "seek"
    if imgui.is_item_active() and state.drag_target:
        seconds = min(max((mouse_x - left) / width * duration, 0.0), float(duration))
        if state.drag_target == "start" and round(seconds) != state.start_s:
            state.set_range(min(round(seconds), state.end_s - 1), state.end_s)
            state.scrub(state.start_s)
        elif state.drag_target == "end" and round(seconds) != state.end_s:
            state.set_range(state.start_s, max(round(seconds), state.start_s + 1))
            state.scrub(max(state.start_s, state.end_s - 0.2))
        elif state.drag_target == "seek":
            target = min(max(seconds, state.start_s), max(state.start_s, state.end_s - 0.1))
            if abs(target - state.preview.position_s) > 0.15:
                state.scrub(target)
    elif state.drag_target:
        state.drag_target = None


def _draw_transport(state: AppState, left: float, top: float, width: float) -> None:
    draw = imgui.get_window_draw_list()
    size = px(18)
    imgui.set_cursor_screen_pos(imgui.ImVec2(left, top))
    if imgui.invisible_button("##play", imgui.ImVec2(size, size)) and state.info is not None:
        state.playing = not state.playing
    color = theme.u32(theme.TEXT if state.info else theme.TEXT_DIM)
    if state.playing and state.info is not None:  # 暂停图标
        bar = px(4)
        draw.add_rect_filled(imgui.ImVec2(left + px(2), top + px(1)),
                             imgui.ImVec2(left + px(2) + bar, top + size - px(1)), color)
        draw.add_rect_filled(imgui.ImVec2(left + px(10), top + px(1)),
                             imgui.ImVec2(left + px(10) + bar, top + size - px(1)), color)
    else:
        draw.add_triangle_filled(imgui.ImVec2(left + px(3), top + px(1)),
                                 imgui.ImVec2(left + px(3), top + size - px(1)),
                                 imgui.ImVec2(left + px(16), top + size / 2), color)

    imgui.set_cursor_screen_pos(imgui.ImVec2(left + px(30), top + px(1)))
    widgets.mono_text(format_clock(state.preview.position_s), theme.TEXT)
    if state.info is not None:
        label = (f"{format_clock(state.start_s)} – {format_clock(state.end_s)}   "
                 f"{state.end_s - state.start_s} s")
        imgui.set_cursor_screen_pos(imgui.ImVec2(left + width - widgets.mono_width(label), top + px(1)))
        widgets.mono_text(label, theme.TEXT_DIM)
