"""窗口设置与每一帧的布局。"""

from __future__ import annotations

import logging
import time

from imgui_bundle import hello_imgui, imgui, immapp

from app import config, paths, settings as settings_store
from app.ui import chrome, inspector, stage, theme
from app.ui.state import AppState
from app.ui.theme import px

INSPECTOR_WIDTH = 320
WINDOW_SIZE = (1120, 960)
_ROOT_FLAGS = int(
    imgui.WindowFlags_.no_decoration
    | imgui.WindowFlags_.no_move
    | imgui.WindowFlags_.no_saved_settings
    | imgui.WindowFlags_.no_bring_to_front_on_focus
    | imgui.WindowFlags_.no_scroll_with_mouse
)


def draw_frame(state: AppState) -> None:
    state.drain_events()
    state.tick_preview(time.monotonic())
    # 只有画面在播放时才连续重绘，其余时间让 hello_imgui 进入空闲。
    hello_imgui.get_runner_params().fps_idling.enable_idling = not (
        state.playing and state.info is not None and not state.busy
    )

    viewport = imgui.get_main_viewport()
    imgui.set_next_window_pos(viewport.work_pos)
    imgui.set_next_window_size(viewport.work_size)
    imgui.begin("##root", None, _ROOT_FLAGS)
    width, height = viewport.work_size.x, viewport.work_size.y

    # 各个区域放在明确的坐标上，彼此紧贴。
    top = px(chrome.TOOLBAR_HEIGHT)
    bottom = height - px(chrome.STATUS_HEIGHT)
    log_height = px(chrome.LOG_HEIGHT) if state.show_log else 0.0
    body = bottom - log_height - top
    side = px(INSPECTOR_WIDTH)

    imgui.set_cursor_pos(imgui.ImVec2(0, 0))
    chrome.toolbar(state, width)
    imgui.set_cursor_pos(imgui.ImVec2(0, top))
    stage.draw(state, imgui.ImVec2(width - side, body))
    imgui.set_cursor_pos(imgui.ImVec2(width - side, top))
    inspector.draw(state, imgui.ImVec2(side, body))
    if state.show_log:
        imgui.set_cursor_pos(imgui.ImVec2(0, bottom - log_height))
        chrome.log_panel(state, width)
    imgui.set_cursor_pos(imgui.ImVec2(0, bottom))
    chrome.status_bar(state, width)
    imgui.end()


def build_runner_params(state: AppState) -> hello_imgui.RunnerParams:
    # 窗口与任务栏的图标来自 assets/app_settings/icon.png。
    hello_imgui.set_assets_folder(paths.assets_dir())
    params = hello_imgui.RunnerParams()
    params.app_window_params.window_title = config.APP_NAME
    params.app_window_params.window_geometry.size = WINDOW_SIZE
    params.app_window_params.restore_previous_geometry = True
    params.imgui_window_params.show_menu_bar = False
    params.imgui_window_params.default_imgui_window_type = (
        hello_imgui.DefaultImGuiWindowType.no_default_window
    )
    params.ini_folder_type = hello_imgui.IniFolderType.app_user_config_folder
    params.ini_filename = f"{config.APP_NAME}/window.ini"
    params.ini_filename_use_app_window_title = False
    params.callbacks.show_gui = lambda: draw_frame(state)
    params.callbacks.post_init = theme.apply_style
    params.callbacks.load_additional_fonts = theme.load_fonts
    params.callbacks.before_exit = lambda: _shutdown(state)
    return params


def _shutdown(state: AppState) -> None:
    state.cancel()
    state.preview.close()
    settings_store.save(paths.settings_file(), state.to_settings())


def main() -> None:
    paths.setup_logging()
    try:
        state = AppState(settings_store.load(paths.settings_file()))
        immapp.run(build_runner_params(state))
    except Exception:
        # 窗口程序没有控制台，异常先写入日志文件再继续向外抛出。
        logging.getLogger(__name__).exception("程序异常终止")
        raise
