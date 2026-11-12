import queue
import threading

import cv2
import numpy as np
import pytest

from app.events import Reporter


@pytest.fixture(scope="session")
def video(tmp_path_factory):
    """用 OpenCV 编码一段 3 秒、800x450、20 fps 的视频，画面里有一个移动的圆。"""
    path = tmp_path_factory.mktemp("video") / "clip.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 20, (800, 450))
    for index in range(60):
        frame = np.full((450, 800, 3), (index * 4) % 255, dtype=np.uint8)
        cv2.circle(frame, (100 + index * 10, 225), 60, (0, 0, 255), -1)
        writer.write(frame)
    writer.release()
    return str(path)


@pytest.fixture
def reporting():
    """返回 (reporter, 读取全部消息的函数, 取消标志)。"""
    channel = queue.Queue()
    cancel = threading.Event()

    def drain():
        items = []
        while not channel.empty():
            items.append(channel.get())
        return items

    return Reporter(channel, cancel), drain, cancel
