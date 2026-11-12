"""程序状态，以及界面触发的各种操作。"""

from __future__ import annotations

import os
import queue
import threading
from typing import Any, Callable, Mapping

from app import config, events, paths, planning, settings as settings_store
from app.events import Event, Reporter
from app.preview import VideoPreview, build_filmstrip
from app.splitter import SplitResult, split_worker
from app.upload import UploadJob, upload_worker

THUMBS = "thumbs"
MAX_LOG_LINES = 500
FILMSTRIP_WIDTH = 650
SCRUB_INTERVAL_S = 0.1

Message = tuple[str, Mapping[str, Any]]


class AppState:
    """界面显示的全部内容，只在界面线程里修改。"""

    def __init__(self, saved: settings_store.Settings) -> None:
        self.language = saved.language
        self.output_dir = saved.output_dir or paths.default_output_dir()
        self.prefix = saved.prefix
        self.workshop_title = saved.workshop_title
        self.browser = saved.browser
        self.keep_aspect = saved.keep_aspect
        self.show_guides = saved.show_guides
        self.fps_limit = saved.fps_limit
        self.scale_percent = saved.scale_percent
        self.colors = saved.colors
        self.limit_mb = saved.limit_mb

        self.preview = VideoPreview()
        self.start_s = 0
        self.end_s = 1
        self.playing = True
        self.filmstrip = None
        self.filmstrip_dirty = False
        self.frame_dirty = False
        self.drag_target: str | None = None
        self._pending_scrub: float | None = None
        self._last_scrub = 0.0

        self.events: "queue.Queue[Event]" = queue.Queue()
        self.cancel_flag = threading.Event()
        self.busy = False
        self.progress = 0.0
        self.status: Message = ("ready", {})
        self.status_is_error = False
        self.log: list[Message] = []
        self.show_log = False
        self.result: SplitResult | None = None

    @property
    def info(self):
        return self.preview.info

    @property
    def max_bytes(self) -> int:
        return int(self.limit_mb * 1048576)

    def to_settings(self) -> settings_store.Settings:
        # 默认输出文件夹保存为空字符串，程序被移动之后仍然指向程序旁边。
        custom_dir = "" if self.output_dir == paths.default_output_dir() else self.output_dir
        return settings_store.Settings(
            language=self.language, output_dir=custom_dir, prefix=self.prefix,
            workshop_title=self.workshop_title, browser=self.browser,
            keep_aspect=self.keep_aspect, show_guides=self.show_guides,
            fps_limit=self.fps_limit, scale_percent=self.scale_percent,
            colors=self.colors, limit_mb=self.limit_mb,
        )

    # 状态与日志
    def say(self, key: str, error: bool = False, **params: Any) -> None:
        self.status = (key, params)
        self.status_is_error = error
        self.log = [*self.log, (key, params)][-MAX_LOG_LINES:]

    # 视频
    def open_video(self, path: str) -> None:
        try:
            info = self.preview.open(path)
        except planning.JobError as error:
            self.say(error.key, error=True, **error.params)
            return
        self.filmstrip = None
        self.result = None
        self.start_s, self.end_s = planning.default_range(info.duration_s)
        self.playing = True
        self.frame_dirty = True
        self.say("loaded", name=os.path.basename(path))
        threading.Thread(target=self._load_filmstrip, args=(path,), daemon=True).start()

    def _load_filmstrip(self, path: str) -> None:
        self.events.put(Event(THUMBS, payload=(path, build_filmstrip(path, FILMSTRIP_WIDTH))))

    def set_range(self, start_s: int, end_s: int) -> None:
        self.start_s, self.end_s = planning.clamp_range(start_s, end_s, self.info.duration_s)

    def scrub(self, seconds: float) -> None:
        """请求显示指定时间的画面。长 GOP 视频的跳转很慢，
        所以跳转有频率限制，始终以最后一次请求为准。"""
        self._pending_scrub = seconds

    def _flush_scrub(self, now: float) -> None:
        if self._pending_scrub is None or now - self._last_scrub < SCRUB_INTERVAL_S:
            return
        self.preview.show(self._pending_scrub, self.keep_aspect)
        self._pending_scrub = None
        self._last_scrub = now
        self.frame_dirty = True

    def tick_preview(self, now: float) -> None:
        self._flush_scrub(now)
        if self._pending_scrub is not None:
            return
        if self.info is None or self.busy or not self.playing or self.drag_target:
            return
        before = self.preview.frame
        self.preview.tick(now, self.start_s, self.end_s, self.keep_aspect)
        if self.preview.frame is not before:
            self.frame_dirty = True

    # 后台任务
    def _start(self, worker: Callable[..., None], job: Any) -> None:
        self.cancel_flag = threading.Event()
        self.busy = True
        self.progress = 0.0
        reporter = Reporter(self.events, self.cancel_flag)
        threading.Thread(target=worker, args=(job, reporter), daemon=True).start()

    def start_export(self) -> None:
        if self.info is None:
            self.say("err_no_video", error=True)
            return
        job = planning.SplitJob(
            video_path=self.info.path, start_s=self.start_s, end_s=self.end_s,
            output_dir=self.output_dir.strip(), prefix=self.prefix.strip(),
            keep_aspect=self.keep_aspect, fps_limit=self.fps_limit,
            scale_percent=self.scale_percent, colors=self.colors, max_bytes=self.max_bytes,
        )
        try:
            planning.validate_job(job)
        except planning.JobError as error:
            self.say(error.key, error=True, **error.params)
            return
        self.result = None
        self._start(split_worker, job)

    def start_upload(self) -> None:
        job = UploadJob(
            gif_paths=planning.output_paths(self.output_dir.strip(), self.prefix.strip()),
            title=self.workshop_title.strip(), browser=self.browser,
        )
        self._start(upload_worker, job)

    def cancel(self) -> None:
        self.cancel_flag.set()

    def drain_events(self) -> None:
        while not self.events.empty():
            self._handle(self.events.get_nowait())

    def _handle(self, event: Event) -> None:
        if event.kind == THUMBS:
            path, strip = event.payload
            if self.info is not None and self.info.path == path:
                self.filmstrip, self.filmstrip_dirty = strip, True
        elif event.kind == events.PROGRESS:
            self.progress = event.progress
        elif event.kind == events.LOG:
            self.say(event.key, **event.params)
        else:  # 结束消息：完成、出错或者已取消
            self.busy = False
            self.progress = 0.0
            if isinstance(event.payload, SplitResult):
                self.result = event.payload
            self.say(event.key, error=event.kind == events.ERROR, **event.params)

    def open_output_folder(self) -> None:
        if not os.path.isdir(self.output_dir):
            self.say("err_folder", error=True)
            return
        os.startfile(self.output_dir)

    def supported_filter(self) -> str:
        return " ".join(f"*.{ext}" for ext in config.VIDEO_EXTENSIONS)
