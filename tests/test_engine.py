"""在一段很短的视频上完整执行切片，并测试各个小模块。"""

import json

import numpy as np
import pytest
from PIL import Image

from app import config, events, gif_ops, i18n, planning, preview, settings
from app.splitter import fit_to_canvas, frame_delay_ms, run_split, split_worker
from app.upload import UploadJob, upload_worker
from app.upload.selenium_backend import read_credentials


def keys(messages):
    return [message.key for message in messages]


def test_fit_to_canvas_shapes():
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    canvas = (config.CANVAS_HEIGHT, config.CANVAS_WIDTH, 3)
    assert fit_to_canvas(frame, True).shape == canvas
    assert fit_to_canvas(frame[:200, :300], False).shape == canvas


def test_frame_delay_is_rounded_to_gif_units():
    assert [frame_delay_ms(fps) for fps in (30, 24, 15, 10, 8, 2)] == [30, 40, 70, 100, 120, 500]
    assert frame_delay_ms(100) == 20


def test_run_split_raises_fps_and_writes_five_synchronised_gifs(video, tmp_path, reporting):
    reporter, drain, _ = reporting
    result = run_split(planning.SplitJob(video, 0, 2, str(tmp_path / "out"), "demo"), reporter)

    assert len(result.paths) == config.SEGMENT_COUNT
    assert (result.width, result.height) == (126, config.CANVAS_HEIGHT)
    assert not result.over_budget
    assert planning.initial_fps(2) < result.fps <= 20  # 片段很小，帧率被提高到源帧率以内
    for path in result.paths:
        with open(path, "rb") as handle:
            data = handle.read()
        assert data[:3] == b"GIF" and data[-1:] == gif_ops.SHOWCASE_TRAILER
        assert gif_ops.gif_dimensions(path) == (126, config.CANVAS_HEIGHT)
    messages = drain()
    assert "log_raise_fps" in keys(messages)
    assert events.PROGRESS in {message.kind for message in messages}
    assert not list((tmp_path / "out").glob("*.tmp"))


def test_run_split_applies_manual_options(video, tmp_path, reporting):
    reporter, _, _ = reporting
    job = planning.SplitJob(video, 0, 1, str(tmp_path), "small", keep_aspect=False,
                            fps_limit=4, scale_percent=50, colors=32)
    result = run_split(job, reporter)
    assert result.fps <= 4
    assert (result.width, result.height) == (63, 180)
    with Image.open(result.paths[0]) as image:
        assert image.mode == "P"


def test_run_split_lowers_fps_then_scale_to_meet_the_limit(video, tmp_path, reporting):
    reporter, drain, _ = reporting
    free = run_split(planning.SplitJob(video, 0, 2, str(tmp_path), "free"), reporter)
    drain()

    half = planning.SplitJob(video, 0, 2, str(tmp_path), "half", max_bytes=max(free.sizes) // 2)
    lowered = run_split(half, reporter)
    assert "log_lower_fps" in keys(drain())
    assert lowered.fps < free.fps and (lowered.width, lowered.height) == (126, 360)

    floor = run_split(planning.SplitJob(video, 0, 2, str(tmp_path), "floor",
                                        fps_limit=config.MIN_FPS), reporter)
    drain()
    tight = planning.SplitJob(video, 0, 2, str(tmp_path), "tight",
                              max_bytes=int(max(floor.sizes) * 0.6))
    shrunk = run_split(tight, reporter)
    assert "log_lower_scale" in keys(drain())
    assert shrunk.fps == config.MIN_FPS and shrunk.width < 126
    assert not shrunk.over_budget


def test_split_worker_reports_cancel_errors_and_success(video, tmp_path, reporting):
    reporter, drain, cancel = reporting
    cancel.set()
    split_worker(planning.SplitJob(video, 0, 2, str(tmp_path), "c"), reporter)
    assert drain()[-1].kind == events.CANCELLED
    assert not list(tmp_path.glob("*.gif")) and not list(tmp_path.glob("*.tmp"))
    cancel.clear()

    split_worker(planning.SplitJob("nope.mp4", 0, 2, str(tmp_path), "c"), reporter)
    last = drain()[-1]
    assert (last.kind, last.key) == (events.ERROR, "err_no_video")

    split_worker(planning.SplitJob(video, 0, 1, str(tmp_path), "ok"), reporter)
    last = drain()[-1]
    assert last.kind == events.DONE and last.payload.fps >= config.MIN_FPS


def test_unwritable_output_fails_before_rendering(video, tmp_path, reporting):
    reporter, drain, _ = reporting
    blocker = tmp_path / "not_a_folder"
    blocker.write_text("x", encoding="utf-8")
    split_worker(planning.SplitJob(video, 0, 1, str(blocker), "p"), reporter)
    messages = drain()
    assert messages[-1].key == "err_output_unwritable"
    assert "log_render" not in keys(messages)


def test_stamp_trailer(tmp_path):
    path = tmp_path / "a.gif"
    Image.new("P", (4, 4)).save(path, format="GIF")
    assert path.read_bytes()[-1:] == b";"
    gif_ops.stamp_trailer(str(path))
    assert path.read_bytes()[-1:] == gif_ops.SHOWCASE_TRAILER
    assert gif_ops.gif_dimensions(str(path)) == (4, 4)
    empty = tmp_path / "empty.gif"
    empty.write_bytes(b"")
    with pytest.raises(ValueError):
        gif_ops.stamp_trailer(str(empty))


def test_preview_plays_inside_range(video):
    player = preview.VideoPreview()
    with pytest.raises(planning.JobError):
        player.open("missing.mp4")
    info = player.open(video)
    assert (info.width, info.height, info.duration_s) == (800, 450, 3)
    assert player.frame.shape == (config.CANVAS_HEIGHT, config.CANVAS_WIDTH, 3)
    for step in range(1, 40):
        player.tick(step * 0.1, 1.0, 2.0, True)
        assert 0.9 <= player.position_s <= 2.2
    with pytest.raises(planning.JobError):
        player.open("missing.mp4")
    assert player.info == info  # 打开失败时原来的视频保持不变
    strip = preview.build_filmstrip(video, 650)
    assert strip.shape == (preview.THUMB_HEIGHT, 650, 3) and strip.any()
    with pytest.raises(planning.JobError):
        preview.build_filmstrip("missing.mp4", 650)
    player.close()
    assert player.frame is None and player.info is None


def test_settings_roundtrip_and_validation(tmp_path):
    path = str(tmp_path / "nested" / "settings.json")
    assert settings.load(path) == settings.Settings()
    custom = settings.Settings(language="en", fps_limit=12, scale_percent=75, colors=64,
                               limit_mb=3.5)
    settings.save(path, custom)
    assert settings.load(path) == custom

    # 另一个版本的程序写出的设置文件：多出的设置项不读取，缺少的设置项使用默认值。
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"language": "en", "dsh_path": ""}, handle)
    assert settings.load(path) == settings.Settings(language="en")

    for bad in ({"language": "xx"}, {"fps_limit": 999}, {"colors": "many"},
                {"limit_mb": 99.0}, {"keep_aspect": "yes"}):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(bad, handle)
        with pytest.raises(ValueError):
            settings.load(path)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("{not json")
    with pytest.raises(json.JSONDecodeError):
        settings.load(path)


def test_translations_are_complete():
    assert set(i18n.STRINGS["zh"]) == set(i18n.STRINGS["en"])
    assert i18n.tr("en", "log_render", number=1, fps=8, width=126, height=360).startswith("Pass 1")
    assert i18n.tr("zh", "ready") == "就绪"
    with pytest.raises(KeyError):
        i18n.tr("zh", "no_such_key")
    with pytest.raises(KeyError):
        i18n.tr("zh", "log_render")


def test_reporter_events_and_cancel(reporting):
    reporter, drain, cancel = reporting
    reporter.progress(7)
    reporter.done("k", payload=1, a=2)
    progress, done = drain()
    assert progress.progress == 1.0 and (done.payload, done.params["a"]) == (1, 2)
    reporter.wait(0)
    cancel.set()
    with pytest.raises(events.Cancelled):
        reporter.check_cancelled()
    with pytest.raises(events.Cancelled):
        reporter.wait(5)


def test_upload_job_titles(tmp_path):
    gifs = tuple(str(tmp_path / f"g_part{i}.gif") for i in range(1, 6))
    job = UploadJob(gifs, "Chrome", title="gif")
    assert [job.item_title(i) for i in range(1, 6)] == [f"gif_{i}" for i in range(1, 6)]
    assert UploadJob(gifs).title == ""  # 默认不显示标题


def test_upload_worker_validates_before_opening_a_browser(tmp_path, reporting):
    reporter, drain, _ = reporting
    upload_worker(UploadJob((str(tmp_path / "missing_part1.gif"),)), reporter)
    last = drain()[-1]
    assert (last.kind, last.key) == (events.ERROR, "err_missing_gifs")


def test_title_option_in_state(tmp_path):
    from app.ui.state import AppState

    state = AppState(settings.Settings(output_dir=str(tmp_path), use_title=True, workshop_title="  "))
    state.start_upload()
    assert state.status[0] == "err_title_empty" and not state.busy
    saved = state.to_settings()
    assert saved.use_title is True and settings.Settings().use_title is False


def test_read_credentials(tmp_path):
    path = tmp_path / "user.txt"
    path.write_text("name\nsecret\n", encoding="utf-8")
    assert read_credentials(str(path)) == ("name", "secret")
    path.write_bytes(b"\xef\xbb\xbfname\nsecret\n")  # 记事本保存时带有 BOM
    assert read_credentials(str(path)) == ("name", "secret")
    path.write_text("only-name\n", encoding="utf-8")
    with pytest.raises(planning.JobError):
        read_credentials(str(path))
