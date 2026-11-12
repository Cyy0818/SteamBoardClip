"""不打开窗口直接导出：

    SteamBoardClip.exe --export <视频> <开始秒> <结束秒> <输出文件夹> <文件名>

过程写入日志文件。退出码 0 表示 5 张 GIF 已经写出。
"""

from __future__ import annotations

import logging
import queue
import threading

from app import events, paths, planning
from app.events import Reporter
from app.i18n import tr
from app.splitter import split_worker

logger = logging.getLogger(__name__)


def run_export(arguments: list[str]) -> int:
    paths.setup_logging()
    video, start_s, end_s, output_dir, prefix = arguments
    job = planning.SplitJob(video, int(start_s), int(end_s), output_dir, prefix)

    channel: "queue.Queue[events.Event]" = queue.Queue()
    split_worker(job, Reporter(channel, threading.Event()))
    last = None
    while not channel.empty():
        event = channel.get()
        if event.kind == events.PROGRESS:
            continue
        logger.info("%s: %s", event.kind, tr("zh", event.key, **event.params))
        last = event
    return 0 if last.kind == events.DONE else 1
