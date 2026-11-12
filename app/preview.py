"""视频预览：用 OpenCV 在 CPU 上解码，并限制解码频率。"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from app import config
from app.planning import JobError, cover_crop_box
from app.splitter import fit_to_canvas

THUMB_COUNT = 10
THUMB_HEIGHT = 56


@dataclass(frozen=True)
class VideoInfo:
    path: str
    width: int
    height: int
    fps: float
    duration_s: int


def open_capture(path: str) -> cv2.VideoCapture:
    capture = cv2.VideoCapture(path)
    if not capture.isOpened():
        capture.release()
        raise JobError("err_open_failed")
    return capture


def probe(capture: cv2.VideoCapture, path: str) -> VideoInfo:
    fps = capture.get(cv2.CAP_PROP_FPS)
    if not 1.0 <= fps <= 240.0:
        raise JobError("err_open_failed")
    frames = capture.get(cv2.CAP_PROP_FRAME_COUNT)
    duration = frames / fps if frames > 0 else _container_duration(path)
    if duration < 1:
        raise JobError("err_open_failed")
    return VideoInfo(
        path=path,
        width=int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
        height=int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        fps=fps,
        duration_s=int(duration),
    )


def _container_duration(path: str) -> float:
    """部分 webm 与 mkv 文件不提供帧数，这时向 ffmpeg 查询时长。"""
    from moviepy.video.io.ffmpeg_reader import ffmpeg_parse_infos

    return float(ffmpeg_parse_infos(path)["duration"])


def build_filmstrip(path: str, width: int, count: int = THUMB_COUNT) -> np.ndarray:
    """把整段视频均匀取样的缩略图横向拼成一张 BGR 图像。"""
    capture = open_capture(path)
    try:
        info = probe(capture, path)
        thumb_width = width // count
        strip = np.zeros((THUMB_HEIGHT, thumb_width * count, 3), dtype=np.uint8)
        for index in range(count):
            capture.set(cv2.CAP_PROP_POS_MSEC, (index + 0.5) * info.duration_s * 1000 / count)
            ok, frame = capture.read()
            if not ok:
                raise ValueError(f"无法读取第 {index + 1} 张缩略图: {path}")
            x1, y1, x2, y2 = cover_crop_box(frame.shape[1], frame.shape[0],
                                            thumb_width, THUMB_HEIGHT)
            thumb = cv2.resize(frame[y1:y2, x1:x2], (thumb_width, THUMB_HEIGHT),
                               interpolation=cv2.INTER_AREA)
            strip[:, index * thumb_width:(index + 1) * thumb_width] = thumb
        return strip
    finally:
        capture.release()


class VideoPreview:
    """在一个时间范围内循环播放视频，每秒最多解码 PREVIEW_MAX_FPS 帧。"""

    def __init__(self) -> None:
        self._capture: cv2.VideoCapture | None = None
        self._frame: np.ndarray | None = None
        self._last_tick = 0.0
        self._keep_aspect = True
        self.info: VideoInfo | None = None
        self.position_s = 0.0

    @property
    def frame(self) -> np.ndarray | None:
        return self._frame

    def open(self, path: str) -> VideoInfo:
        """打开视频并显示第一帧。无法打开时抛出 JobError，原来的视频保持不变。"""
        capture = open_capture(path)
        info = probe(capture, path)
        self.close()
        self._capture = capture
        self.info = info
        self.show(0.0, self._keep_aspect)
        return info

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
        self._capture = None
        self._frame = None
        self.info = None
        self.position_s = 0.0

    def show(self, seconds: float, keep_aspect: bool) -> None:
        """跳到指定时间并解码一帧，拖动时间轴时使用。
        指定时间已经在最后一帧之后时，画面保持不变。"""
        self._keep_aspect = keep_aspect
        self._capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, seconds) * 1000.0)
        self._read()

    def tick(self, now: float, start_s: float, end_s: float, keep_aspect: bool) -> None:
        """在 [start_s, end_s) 内推进播放，界面每帧调用一次。"""
        interval = 1.0 / min(self.info.fps, config.PREVIEW_MAX_FPS)
        elapsed = now - self._last_tick
        if elapsed < interval:
            return
        self._keep_aspect = keep_aspect
        # 跳过若干源视频帧来跟上真实时间，跳过的帧不转换颜色。
        # 跳帧数量有上限，电脑太慢时表现为慢动作。
        due = int(min(elapsed, 0.5) * self.info.fps)
        for _ in range(min(config.PREVIEW_MAX_SKIP, max(0, due - 1))):
            self._capture.grab()
        self._last_tick = now
        # 播放到范围末尾或者文件末尾时回到范围开头。
        if self.position_s >= end_s or self.position_s < start_s or not self._read():
            self.show(start_s, keep_aspect)

    def _read(self) -> bool:
        ok, frame = self._capture.read()
        if not ok:
            return False
        self._frame = fit_to_canvas(frame, self._keep_aspect)
        self.position_s = self._capture.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        return True
