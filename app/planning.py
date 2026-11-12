"""纯逻辑：展柜几何、帧率与分辨率的平衡、任务校验。

本模块不读写磁盘，不依赖界面与视频解码。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Sequence

from app import config


class JobError(ValueError):
    """任务无法执行。key 是界面文案的键，params 是文案的参数。"""

    def __init__(self, key: str, **params: object) -> None:
        super().__init__(key)
        self.key = key
        self.params = params


@dataclass(frozen=True)
class SplitJob:
    """切片任务的全部参数，不可变，可以直接交给后台线程。"""

    video_path: str
    start_s: int
    end_s: int
    output_dir: str
    prefix: str
    keep_aspect: bool = True
    # 压缩选项都是上限，体积上限始终生效。
    fps_limit: int = 0  # 0 表示自动
    scale_percent: int = 100
    colors: int = 256
    max_bytes: int = config.MAX_GIF_BYTES

    @property
    def duration_s(self) -> int:
        return self.end_s - self.start_s

    @property
    def scale(self) -> float:
        return self.scale_percent / 100.0


def max_clip_seconds() -> int:
    """在最低帧率下仍然不超过帧数上限的最长片段。"""
    return config.MAX_FRAMES_PER_PASS // config.MIN_FPS


def validate_job(job: SplitJob) -> None:
    if not job.video_path or not os.path.isfile(job.video_path):
        raise JobError("err_no_video")
    if job.start_s < 0 or job.end_s <= job.start_s:
        raise JobError("err_range")
    if job.duration_s > max_clip_seconds():
        raise JobError("err_range_too_long", seconds=max_clip_seconds())
    validate_prefix(job.prefix)
    if not job.output_dir:
        raise JobError("err_no_output_dir")
    options_ok = (
        (job.fps_limit == 0 or config.MIN_FPS <= job.fps_limit <= config.MAX_OUTPUT_FPS)
        and round(config.MIN_SCALE * 100) <= job.scale_percent <= 100
        and job.colors in config.COLOR_CHOICES
        and 0 < job.max_bytes <= config.STEAM_LIMIT_BYTES
    )
    if not options_ok:
        raise JobError("err_options")


def validate_prefix(prefix: str) -> None:
    if not prefix.strip():
        raise JobError("err_prefix_empty")
    bad = sorted({ch for ch in prefix if ch in config.INVALID_FILENAME_CHARS})
    if bad:
        raise JobError("err_prefix_chars", chars=" ".join(bad))


def output_paths(output_dir: str, prefix: str) -> tuple[str, ...]:
    return tuple(
        os.path.join(output_dir, f"{prefix}_part{index}.gif")
        for index in range(1, config.SEGMENT_COUNT + 1)
    )


# 几何

def segment_boxes(
    canvas_width: int = config.CANVAS_WIDTH,
    count: int = config.SEGMENT_COUNT,
    gap: int = config.SEGMENT_GAP_PX,
) -> tuple[tuple[int, int], ...]:
    """画布上每一列的 (x1, x2) 像素范围。"""
    usable = canvas_width - gap * (count - 1)
    if count <= 0 or usable < count:
        raise ValueError("画布宽度不足以放下全部列")
    width = usable // count
    return tuple(
        (index * (width + gap), index * (width + gap) + width) for index in range(count)
    )


def cover_crop_box(
    src_width: int, src_height: int, target_width: int, target_height: int
) -> tuple[int, int, int, int]:
    """源画面里与目标宽高比一致、居中的最大裁剪框 (x1, y1, x2, y2)。"""
    if min(src_width, src_height, target_width, target_height) <= 0:
        raise ValueError("尺寸必须为正数")
    if src_width * target_height > src_height * target_width:  # 源画面更宽
        crop_width = max(1, round(src_height * target_width / target_height))
        x1 = (src_width - crop_width) // 2
        return (x1, 0, x1 + crop_width, src_height)
    crop_height = max(1, round(src_width * target_height / target_width))
    y1 = (src_height - crop_height) // 2
    return (0, y1, src_width, y1 + crop_height)


def scaled_size(width: int, height: int, scale: float) -> tuple[int, int]:
    return (max(1, round(width * scale)), max(1, round(height * scale)))


def decode_size(
    src_width: int, src_height: int, keep_aspect: bool
) -> tuple[int, int] | None:
    """ffmpeg 解码时应当缩放到的尺寸。返回 None 表示按源尺寸解码。

    让 ffmpeg 在解码阶段缩小画面，1080p 与 4K 视频的开销才接近小视频。
    这里只缩小，从不放大。
    """
    if min(src_width, src_height) <= 0:
        raise ValueError("视频尺寸必须为正数")
    if not keep_aspect:
        if src_width <= config.CANVAS_WIDTH and src_height <= config.CANVAS_HEIGHT:
            return None
        return (config.CANVAS_WIDTH, config.CANVAS_HEIGHT)
    factor = max(config.CANVAS_WIDTH / src_width, config.CANVAS_HEIGHT / src_height)
    if factor >= 1.0:
        return None
    # ffmpeg 要求偶数尺寸，向上取整保证画布被完全覆盖。
    width = max(config.CANVAS_WIDTH, -(-int(src_width * factor + 0.999) // 2) * 2)
    height = max(config.CANVAS_HEIGHT, -(-int(src_height * factor + 0.999) // 2) * 2)
    return (width, height)


# 帧率与分辨率的平衡

def initial_fps(duration_s: float) -> int:
    """第一遍渲染使用的保守帧率，之后的渲染会把它提高到预算允许的最高值。"""
    for limit, fps in config.INITIAL_FPS_STEPS:
        if duration_s <= limit:
            return fps
    return config.INITIAL_FPS_LONG


def fps_ceiling(source_fps: float, duration_s: float, limit: int = 0) -> int:
    """值得尝试的最高帧率：受源帧率、GIF 的实用上限、帧数上限、用户设置的上限约束。"""
    if source_fps <= 0 or duration_s <= 0:
        raise ValueError("源帧率与片段时长必须为正数")
    ceiling = min(config.MAX_OUTPUT_FPS, int(source_fps),
                  int(config.MAX_FRAMES_PER_PASS / duration_s))
    if limit > 0:
        ceiling = min(ceiling, limit)
    return max(config.MIN_FPS, ceiling)


def raise_fps(current: int, largest: int, budget: int, ceiling: int) -> int | None:
    """每一段都明显低于预算时返回下一个更高的帧率，否则返回 None。"""
    if largest >= budget * config.UNDERSIZE_RATIO or current >= ceiling:
        return None
    estimate = int(current * budget * config.FILL_RATIO / largest)
    return min(ceiling, max(current + 1, estimate))


def lower_fps(current: int, largest: int, budget: int, floor: int = config.MIN_FPS) -> int | None:
    """有一段超出预算时返回下一个更低的帧率，已经到下限时返回 None。"""
    if largest <= budget or current <= floor:
        return None
    estimate = int(current * budget / largest)
    return max(floor, min(current - 1, estimate))


def lower_scale(current: float, largest: int, budget: int) -> float | None:
    """帧率无法再降时返回下一个更小的缩放比例，已经到下限时返回 None。"""
    if largest <= budget or current <= config.MIN_SCALE:
        return None
    ratio = (budget / largest) ** 0.5 * config.SCALE_SAFETY
    return max(config.MIN_SCALE, round(current * ratio, 3))


@dataclass(frozen=True)
class Balance:
    """搜索的结果：最终使用的帧率、缩放比例与每一段的体积。"""

    fps: int
    scale: float
    sizes: tuple[int, ...]

    @property
    def largest(self) -> int:
        return max(self.sizes)


RenderFn = Callable[[int, float], Sequence[int]]
LogFn = Callable[..., None]


def find_balance(
    render: RenderFn,
    start_fps: int,
    ceiling: int,
    budget: int,
    log: LogFn,
    start_scale: float = 1.0,
) -> Balance:
    """在体积预算内寻找最高的帧率，必要时再缩小分辨率。

    render(fps, scale) 渲染全部 5 段并返回各段的字节数。5 段始终共用同一帧率
    与同一分辨率。顺序：保持分辨率并把帧率提高到预算允许的最高值，超出预算
    时降低帧率，帧率到下限之后才缩小分辨率。
    """
    fps, scale = min(start_fps, ceiling), start_scale
    sizes = tuple(render(fps, scale))

    while (faster := raise_fps(fps, max(sizes), budget, ceiling)) is not None:
        log("log_raise_fps", fps=faster)
        fps, sizes = faster, tuple(render(faster, scale))

    while (slower := lower_fps(fps, max(sizes), budget)) is not None:
        log("log_lower_fps", fps=slower)
        fps, sizes = slower, tuple(render(slower, scale))

    for _ in range(config.MAX_SCALE_PASSES):
        smaller = lower_scale(scale, max(sizes), budget)
        if smaller is None or smaller >= scale:
            break
        log("log_lower_scale", percent=round(smaller * 100))
        scale, sizes = smaller, tuple(render(fps, smaller))

    return Balance(fps=fps, scale=scale, sizes=sizes)


# 时间

def format_clock(seconds: float) -> str:
    total = max(0, int(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


def clamp_range(start_s: int, end_s: int, duration_s: int) -> tuple[int, int]:
    """保证 0 <= start < end <= duration。"""
    if duration_s < 1:
        raise ValueError("视频时长必须至少 1 秒")
    start = min(max(0, start_s), duration_s - 1)
    end = min(max(start + 1, end_s), duration_s)
    return (start, end)


def default_range(duration_s: int) -> tuple[int, int]:
    return clamp_range(0, config.DEFAULT_CLIP_SECONDS, duration_s)
