"""右侧：属性行与两个操作按钮。"""

from __future__ import annotations

from typing import Callable

from imgui_bundle import imgui, portable_file_dialogs as pfd

from app import config
from app.i18n import tr
from app.planning import format_clock
from app.settings import DEFAULT_LIMIT_MB
from app.ui import theme, widgets
from app.ui.state import AppState
from app.ui.theme import px

_MARGIN = 20
_FIELD_WIDTH = 180
_ACTIONS_HEIGHT = 96


def draw(state: AppState, size: imgui.ImVec2) -> None:
    t: Callable[..., str] = lambda key, **params: tr(state.language, key, **params)
    imgui.push_style_color(int(imgui.Col_.child_bg), theme.PANEL)
    imgui.begin_child("inspector", size)
    origin = imgui.get_cursor_screen_pos()
    imgui.get_window_draw_list().add_rect_filled(
        origin, imgui.ImVec2(origin.x + 1, origin.y + size.y), theme.u32(theme.LINE))

    inner = size.x - px(_MARGIN) * 2
    imgui.set_cursor_pos(imgui.ImVec2(px(_MARGIN), px(8)))
    # 子窗口延伸到面板边缘，滚动条位于右侧留白里。
    imgui.begin_child("rows", imgui.ImVec2(size.x - px(_MARGIN) - px(3),
                                           size.y - px(_ACTIONS_HEIGHT) - px(8)))
    imgui.begin_disabled(state.busy)
    _clip_rows(state, t, inner)
    _output_rows(state, t, inner)
    _compress_rows(state, t, inner)
    imgui.end_disabled()
    _result_rows(state, t, inner)
    imgui.begin_disabled(state.busy)
    _upload_rows(state, t, inner)
    imgui.end_disabled()
    imgui.end_child()

    _actions(state, t, inner, size.y)
    imgui.end_child()
    imgui.pop_style_color()


def _group(label: str, inner: float, first: bool = False, caption: str = "") -> None:
    if not first:
        imgui.dummy(imgui.ImVec2(0, px(4)))
        widgets.hairline(inner)
    imgui.dummy(imgui.ImVec2(0, px(2)))
    widgets.text(label, theme.TEXT_DIM)
    if caption:
        imgui.same_line(inner - imgui.calc_text_size(caption).x)
        widgets.text(caption, theme.TEXT_DIM)


def _label(label: str, inner: float, field_width: float = _FIELD_WIDTH) -> None:
    imgui.align_text_to_frame_padding()
    widgets.text(label, theme.TEXT_SOFT)
    imgui.same_line(inner - px(field_width))
    imgui.set_next_item_width(px(field_width))


def _clip_rows(state: AppState, t, inner: float) -> None:
    _group(t("group_clip"), inner, first=True)
    duration = state.info.duration_s if state.info else 0
    imgui.begin_disabled(state.info is None)
    _label(t("start"), inner, 90)
    with widgets.mono():
        changed, value = imgui.drag_int("##start", state.start_s, 0.2, 0, max(0, duration - 1),
                                        format_clock(state.start_s))
    if changed:
        state.set_range(min(value, state.end_s - 1), state.end_s)
        state.scrub(state.start_s)
    _label(t("end"), inner, 90)
    with widgets.mono():
        changed, value = imgui.drag_int("##end", state.end_s, 0.2, 1, max(1, duration),
                                        format_clock(state.end_s))
    if changed:
        state.set_range(state.start_s, max(value, state.start_s + 1))
        state.scrub(max(state.start_s, state.end_s - 0.2))
    imgui.end_disabled()


def _output_rows(state: AppState, t, inner: float) -> None:
    _group(t("group_output"), inner)
    _label(t("prefix"), inner)
    _, state.prefix = imgui.input_text("##prefix", state.prefix)

    button = px(30)
    imgui.align_text_to_frame_padding()
    widgets.text(t("save_to"), theme.TEXT_SOFT)
    imgui.same_line(inner - px(_FIELD_WIDTH))
    imgui.set_next_item_width(px(_FIELD_WIDTH) - button - px(4))
    _, state.output_dir = imgui.input_text("##folder", state.output_dir)
    imgui.same_line(0, px(4))
    if widgets.outline_button("…##pick_folder", imgui.ImVec2(button, 0)):
        chosen = pfd.select_folder(t("pick_folder_title"), state.output_dir).result()
        if chosen:
            state.output_dir = chosen

    for key, attribute in (("keep_aspect", "keep_aspect"), ("guides", "show_guides")):
        imgui.align_text_to_frame_padding()
        widgets.text(t(key), theme.TEXT_SOFT)
        imgui.same_line(inner - px(30))
        imgui.set_cursor_pos_y(imgui.get_cursor_pos_y() + px(6))
        changed, value = widgets.toggle(f"##{attribute}", getattr(state, attribute))
        if changed:
            setattr(state, attribute, value)
            if attribute == "keep_aspect" and state.info is not None:
                state.scrub(state.preview.position_s)


def _combo(str_id: str, current, choices: tuple, labels: list[str]):
    index = choices.index(current) if current in choices else 0
    changed, index = imgui.combo(str_id, index, labels)
    return choices[index] if changed else current


def _compress_rows(state: AppState, t, inner: float) -> None:
    _group(t("group_compress"), inner)
    _label(t("fps"), inner)
    state.fps_limit = _combo(
        "##fps", state.fps_limit, config.FPS_LIMIT_CHOICES,
        [t("auto") if fps == 0 else f"≤ {fps} fps" for fps in config.FPS_LIMIT_CHOICES])
    _label(t("scale"), inner)
    state.scale_percent = _combo(
        "##scale", state.scale_percent, config.SCALE_PERCENT_CHOICES,
        [f"{percent}%" for percent in config.SCALE_PERCENT_CHOICES])
    _label(t("colors"), inner)
    state.colors = _combo("##colors", state.colors, config.COLOR_CHOICES,
                          [str(count) for count in config.COLOR_CHOICES])
    _label(t("limit"), inner)
    changed, value = imgui.drag_float("##limit", state.limit_mb, 0.02, config.MIN_LIMIT_MB,
                                      DEFAULT_LIMIT_MB, "%.2f MB")
    if changed:
        state.limit_mb = min(DEFAULT_LIMIT_MB, max(config.MIN_LIMIT_MB, value))


def _result_rows(state: AppState, t, inner: float) -> None:
    result = state.result
    if result is None:
        return
    limit = result.max_bytes
    _group(t("group_result"), inner, caption=t("limit_caption", size=f"{limit / 1048576:.2f}"))
    draw = imgui.get_window_draw_list()
    bar_left, bar_width = px(20), inner - px(20) - px(84)
    for index, size_bytes in enumerate(result.sizes, start=1):
        origin = imgui.get_cursor_screen_pos()
        widgets.mono_text(str(index), theme.TEXT_SOFT)
        line_height = imgui.get_text_line_height()
        y = origin.y + line_height / 2 - px(2)
        draw.add_rect_filled(imgui.ImVec2(origin.x + bar_left, y),
                             imgui.ImVec2(origin.x + bar_left + bar_width, y + px(4)),
                             theme.u32(theme.LINE))
        fill = min(1.0, size_bytes / limit)
        color = theme.DANGER if size_bytes > limit else theme.TEXT_SOFT
        draw.add_rect_filled(imgui.ImVec2(origin.x + bar_left, y),
                             imgui.ImVec2(origin.x + bar_left + bar_width * fill, y + px(4)),
                             theme.u32(color))
        label = f"{size_bytes / 1048576:.2f} MB"
        imgui.same_line(inner - widgets.mono_width(label))
        widgets.mono_text(label, theme.DANGER if size_bytes > limit else theme.TEXT)


def _upload_rows(state: AppState, t, inner: float) -> None:
    _group(t("group_upload"), inner)
    imgui.align_text_to_frame_padding()
    widgets.text(t("use_title"), theme.TEXT_SOFT)
    imgui.same_line(inner - px(30))
    imgui.set_cursor_pos_y(imgui.get_cursor_pos_y() + px(6))
    _, state.use_title = widgets.toggle("##use_title", state.use_title)
    if state.use_title:
        _label(t("title"), inner)
        _, state.workshop_title = imgui.input_text("##title", state.workshop_title)
    _label(t("browser"), inner)
    state.browser = _combo("##browser", state.browser, config.BROWSERS, list(config.BROWSERS))


def _actions(state: AppState, t, inner: float, height: float) -> None:
    top = height - px(_ACTIONS_HEIGHT)
    gap = px(8)
    upload_width = px(92)
    imgui.set_cursor_pos(imgui.ImVec2(px(_MARGIN), top))
    widgets.hairline(inner)
    imgui.set_cursor_pos(imgui.ImVec2(px(_MARGIN), top + px(14)))
    imgui.begin_disabled(state.busy)
    if widgets.primary_button(t("export"), imgui.ImVec2(inner - upload_width - gap, px(34))):
        state.start_export()
    imgui.same_line(0, gap)
    if widgets.outline_button(t("upload"), imgui.ImVec2(upload_width, px(34))):
        state.start_upload()
    imgui.end_disabled()
    imgui.set_cursor_pos(imgui.ImVec2(px(_MARGIN), top + px(60)))
    if widgets.link(t("open_folder")):
        state.open_output_folder()
