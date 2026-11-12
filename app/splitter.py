"""把视频的一个时间段切成 5 张帧率与尺寸一致的展柜 GIF。"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from app import config, planning
from app.events import Cancelled, Reporter
from app.gif_ops import gif_dimensions, stamp_trailer

logger = logging.getLogger(__name__)

# 一遍渲染里解码与量化所占的进度比例，剩下的是写文件。
_DECODE_SHARE = 0.85
TEMP_SUFFIX = ".tmp"


@dataclass(frozen=True)
class SplitResult:
    paths: tuple[str, ...]
    sizes: tuple[int, ...]
    fps: int
    width: int
    height: int
    max_bytes: int

    @property
    def over_budget(self) -> bool:
        return max(self.sizes) > self.max_bytes


def fit_to_canvas(frame: np.ndarray, keep_aspect: bool) -> np.ndarray:
    """把一帧铺到展柜画布上：居中裁剪，或者直接拉伸。"""
    height, width = frame.shape[:2]
    if keep_aspect:
        x1, y1, x2, y2 = planning.cover_crop_box(
            width, height, config.CANVAS_WIDTH, config.CANVAS_HEIGHT
        )
        frame = frame[y1:y2, x1:x2]
        height, width = frame.shape[:2]
    shrinking = width > config.CANVAS_WIDTH or height > config.CANVAS_HEIGHT
    interpolation = cv2.INTER_AREA if shrinking else cv2.INTER_CUBIC
    return cv2.resize(
        frame, (config.CANVAS_WIDTH, config.CANVAS_HEIGHT), interpolation=interpolation
    )


def frame_delay_ms(fps: int) -> int:
    """GIF 的帧间隔以 1/100 秒为单位存储，这里四舍五入到该单位。"""
    return max(2, round(100 / fps)) * 10


def _quantise(column: np.ndarray, size: tuple[int, int] | None, colors: int) -> Image.Image:
    """把一列 RGB 画面转换成调色板图像，这就是 GIF 编码器保存的内容。"""
    if size is not None:
        column = cv2.resize(column, size, interpolation=cv2.INTER_AREA)
    image = Image.fromarray(np.ascontiguousarray(column))
    return image.convert("P", palette=Image.Palette.ADAPTIVE, colors=colors)


def _save_gif(frames: list[Image.Image], temp_path: str, fps: int) -> int:
    """把一段写入临时文件并改写 trailer，返回字节数。"""
    frames[0].save(
        temp_path,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=frame_delay_ms(fps),
        loop=0,
    )
    stamp_trailer(temp_path)
    return os.path.getsize(temp_path)


def check_writable(folder: str) -> None:
    """在渲染开始之前确认输出文件夹可以写入。"""
    probe = os.path.join(folder, f".write_test{TEMP_SUFFIX}")
    try:
        os.makedirs(folder, exist_ok=True)
        with open(probe, "wb"):
            pass
    except OSError as error:
        raise planning.JobError("err_output_unwritable") from error
    os.remove(probe)


class _Renderer:
    """每次调用用一遍解码渲染出全部 5 段。"""

    def __init__(self, clip, job: planning.SplitJob, reporter: Reporter,
                 pool: ThreadPoolExecutor) -> None:
        self._clip = clip
        self._job = job
        self._reporter = reporter
        self._pool = pool
        self._boxes = planning.segment_boxes()
        self.paths = planning.output_paths(job.output_dir, job.prefix)
        self.passes = 0

    def __call__(self, fps: int, scale: float) -> tuple[int, ...]:
        self.passes += 1
        column_width = self._boxes[0][1] - self._boxes[0][0]
        size = None
        if scale < 1.0:
            size = planning.scaled_size(column_width, config.CANVAS_HEIGHT, scale)
        out_width, out_height = size or (column_width, config.CANVAS_HEIGHT)
        self._reporter.log(
            "log_render", number=self.passes, fps=fps, width=out_width, height=out_height
        )

        columns: list[list[Image.Image]] = [[] for _ in self._boxes]
        expected = max(1, int(self._clip.duration * fps))
        for index, frame in enumerate(self._clip.iter_frames(fps=fps, dtype="uint8")):
            self._reporter.check_cancelled()
            canvas = fit_to_canvas(frame, self._job.keep_aspect)
            parts = self._pool.map(
                lambda box: _quantise(canvas[:, box[0]:box[1]], size, self._job.colors),
                self._boxes,
            )
            for column, part in zip(columns, parts):
                column.append(part)
            if index % 5 == 0:
                self._reporter.progress(_DECODE_SHARE * min(1.0, (index + 1) / expected))

        if not columns[0]:
            raise planning.JobError("err_no_frames")
        self._reporter.check_cancelled()
        # 5 段先写入临时文件，全部写完再一起替换，
        # 输出文件夹里始终只有完整、一致、已经改写 trailer 的一组文件。
        temp_paths = [f"{path}{TEMP_SUFFIX}" for path in self.paths]
        try:
            sizes = tuple(
                self._pool.map(lambda pair: _save_gif(pair[0], pair[1], fps),
                               zip(columns, temp_paths))
            )
            self._reporter.check_cancelled()
            for temp_path, path in zip(temp_paths, self.paths):
                os.replace(temp_path, path)
        finally:
            for temp_path in temp_paths:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        self._reporter.progress(1.0)
        self._reporter.log(
            "log_pass_sizes",
            sizes=" / ".join(f"{size_bytes / 1048576:.2f}" for size_bytes in sizes),
        )
        return sizes


def _open_clip(clip_factory, job: planning.SplitJob):
    """用 ffmpeg 在 CPU 上解码，并在解码阶段缩小画面。

    先读取源尺寸，再让 ffmpeg 自己缩小大画面，Python 拿到的帧接近 650x360。
    """
    probe = clip_factory(job.video_path, audio=False)
    width, height = probe.size
    target = planning.decode_size(width, height, job.keep_aspect)
    if target is None:
        return probe
    probe.close()
    return clip_factory(job.video_path, audio=False, target_resolution=target)


def run_split(job: planning.SplitJob, reporter: Reporter) -> SplitResult:
    """执行切片并返回结果。失败或者被取消时抛出异常。"""
    from moviepy import VideoFileClip  # 加载较慢，用到时才导入

    planning.validate_job(job)
    check_writable(job.output_dir)
    reporter.log("log_loading")

    source = _open_clip(VideoFileClip, job)
    try:
        end_s = min(float(job.end_s), float(source.duration))
        if end_s <= job.start_s:
            raise planning.JobError("err_range")
        clip = source.subclipped(job.start_s, end_s)
        duration_s = end_s - job.start_s
        ceiling = planning.fps_ceiling(source.fps, duration_s, job.fps_limit)
        with ThreadPoolExecutor(max_workers=min(config.SEGMENT_COUNT, os.cpu_count())) as pool:
            renderer = _Renderer(clip, job, reporter, pool)
            balance = planning.find_balance(
                renderer,
                planning.initial_fps(duration_s),
                ceiling,
                job.max_bytes,
                reporter.log,
                start_scale=job.scale,
            )
    finally:
        source.close()

    width, height = gif_dimensions(renderer.paths[0])
    return SplitResult(
        paths=renderer.paths,
        sizes=tuple(os.path.getsize(path) for path in renderer.paths),
        fps=balance.fps,
        width=width,
        height=height,
        max_bytes=job.max_bytes,
    )


def split_worker(job: planning.SplitJob, reporter: Reporter) -> None:
    """后台线程入口：任何结果都以一条结束消息报告给界面。"""
    try:
        result = run_split(job, reporter)
    except Cancelled:
        reporter.cancelled()
    except planning.JobError as error:
        reporter.error(error.key, **error.params)
    except Exception as error:
        logger.exception("切片失败")
        reporter.error("err_unexpected", detail=str(error))
    else:
        if result.over_budget:
            reporter.log("log_over_budget", size=f"{max(result.sizes) / 1048576:.2f}")
        reporter.done(
            "msg_split_done",
            payload=result,
            fps=result.fps,
            width=result.width,
            height=result.height,
            size=f"{max(result.sizes) / 1048576:.2f}",
        )
