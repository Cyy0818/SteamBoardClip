import pytest

from app import config, planning

MB = 1048576


def make_job(video, tmp_path, **overrides):
    values = dict(video_path=video, start_s=0, end_s=2, output_dir=str(tmp_path), prefix="out")
    values.update(overrides)
    return planning.SplitJob(**values)


def test_segment_boxes_match_showcase_layout():
    assert planning.segment_boxes() == ((0, 126), (131, 257), (262, 388), (393, 519), (524, 650))


def test_segment_boxes_rejects_too_narrow_canvas():
    with pytest.raises(ValueError):
        planning.segment_boxes(canvas_width=10, count=5, gap=5)


@pytest.mark.parametrize("src, expected", [
    ((1920, 1080), (0, 8, 1920, 1071)),
    ((1000, 1000), (0, 223, 1000, 777)),
    ((3000, 360), (1175, 0, 1825, 360)),
])
def test_cover_crop_box_is_centred_with_target_aspect(src, expected):
    box = planning.cover_crop_box(*src, config.CANVAS_WIDTH, config.CANVAS_HEIGHT)
    assert box == expected
    width, height = box[2] - box[0], box[3] - box[1]
    assert abs(width / height - config.CANVAS_WIDTH / config.CANVAS_HEIGHT) < 0.01


def test_cover_crop_box_rejects_empty_source():
    with pytest.raises(ValueError):
        planning.cover_crop_box(0, 100, 650, 360)


@pytest.mark.parametrize("duration, fps", [(5, 10), (15, 10), (16, 8), (45, 6), (90, 5), (300, 4)])
def test_initial_fps_steps(duration, fps):
    assert planning.initial_fps(duration) == fps


def test_fps_ceiling_bounds():
    assert planning.fps_ceiling(60.0, 10) == config.MAX_OUTPUT_FPS
    assert planning.fps_ceiling(24.0, 10) == 24
    assert planning.fps_ceiling(60.0, 10, limit=12) == 12
    assert planning.fps_ceiling(60.0, 120) == 20  # 120 秒内最多 2400 帧
    assert planning.fps_ceiling(60.0, 1200) == config.MIN_FPS
    with pytest.raises(ValueError):
        planning.fps_ceiling(0.0, 10)
    with pytest.raises(ValueError):
        planning.fps_ceiling(30.0, 0)


def test_decode_size_only_shrinks():
    assert planning.decode_size(640, 360, True) is None
    assert planning.decode_size(1920, 1080, False) == (650, 360)
    width, height = planning.decode_size(1920, 1080, True)
    assert width >= config.CANVAS_WIDTH and height >= config.CANVAS_HEIGHT
    assert width % 2 == 0 and height % 2 == 0 and width < 1920
    with pytest.raises(ValueError):
        planning.decode_size(0, 0, True)


def test_raise_and_lower_fps():
    budget = 5 * MB
    assert planning.raise_fps(10, 2 * MB, budget, 30) == 21
    assert planning.raise_fps(10, 4 * MB, budget, 30) is None
    assert planning.raise_fps(30, 1 * MB, budget, 30) is None
    assert planning.lower_fps(20, 10 * MB, budget) == 10
    assert planning.lower_fps(20, 4 * MB, budget) is None
    assert planning.lower_fps(config.MIN_FPS, 10 * MB, budget) is None


def test_lower_scale_respects_floor():
    budget = 5 * MB
    assert planning.lower_scale(1.0, 4 * MB, budget) is None
    assert 0.5 <= planning.lower_scale(1.0, 8 * MB, budget) < 1.0
    assert planning.lower_scale(1.0, 500 * MB, budget) == config.MIN_SCALE
    assert planning.lower_scale(config.MIN_SCALE, 8 * MB, budget) is None


def test_validate_job_accepts_good_job(video, tmp_path):
    planning.validate_job(make_job(video, tmp_path))
    limit = planning.max_clip_seconds()
    planning.validate_job(make_job(video, tmp_path, end_s=limit))


@pytest.mark.parametrize("overrides, key", [
    (dict(video_path="missing.mp4"), "err_no_video"),
    (dict(start_s=5, end_s=5), "err_range"),
    (dict(end_s=planning.max_clip_seconds() + 1), "err_range_too_long"),
    (dict(prefix="  "), "err_prefix_empty"),
    (dict(prefix="a/b"), "err_prefix_chars"),
    (dict(output_dir=""), "err_no_output_dir"),
    (dict(fps_limit=1), "err_options"),
    (dict(scale_percent=10), "err_options"),
    (dict(colors=7), "err_options"),
    (dict(max_bytes=10 * MB), "err_options"),
])
def test_validate_job_rejects_bad_input(video, tmp_path, overrides, key):
    with pytest.raises(planning.JobError) as caught:
        planning.validate_job(make_job(video, tmp_path, **overrides))
    assert caught.value.key == key


def test_output_paths_and_clock(tmp_path):
    paths = planning.output_paths(str(tmp_path), "demo")
    assert len(paths) == config.SEGMENT_COUNT
    assert paths[0].endswith("demo_part1.gif") and paths[-1].endswith("demo_part5.gif")
    assert planning.format_clock(0) == "00:00"
    assert planning.format_clock(125.9) == "02:05"


def test_clamp_and_default_range():
    assert planning.clamp_range(-5, 500, 100) == (0, 100)
    assert planning.clamp_range(50, 20, 100) == (50, 51)
    assert planning.clamp_range(200, 300, 100) == (99, 100)
    assert planning.default_range(30) == (0, 30)
    assert planning.default_range(900) == (0, config.DEFAULT_CLIP_SECONDS)
    with pytest.raises(ValueError):
        planning.clamp_range(0, 1, 0)
