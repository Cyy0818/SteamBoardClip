"""后台线程通过队列发给界面线程的消息。"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from typing import Any, Mapping

LOG = "log"
PROGRESS = "progress"
DONE = "done"
ERROR = "error"
CANCELLED = "cancelled"


class Cancelled(Exception):
    """用户要求停止时在后台线程里抛出。"""


@dataclass(frozen=True)
class Event:
    kind: str
    key: str = ""
    params: Mapping[str, Any] = field(default_factory=dict)
    progress: float | None = None
    payload: Any = None


class Reporter:
    """后台线程用它上报进度并响应取消。"""

    def __init__(self, events: "queue.Queue[Event]", cancel: threading.Event) -> None:
        self._events = events
        self._cancel = cancel

    def log(self, key: str, **params: Any) -> None:
        self._events.put(Event(LOG, key, params))

    def progress(self, fraction: float) -> None:
        self._events.put(Event(PROGRESS, progress=min(1.0, max(0.0, fraction))))

    def done(self, key: str, payload: Any = None, **params: Any) -> None:
        self._events.put(Event(DONE, key, params, payload=payload))

    def error(self, key: str, **params: Any) -> None:
        self._events.put(Event(ERROR, key, params))

    def cancelled(self) -> None:
        self._events.put(Event(CANCELLED, "msg_cancelled"))

    def check_cancelled(self) -> None:
        if self._cancel.is_set():
            raise Cancelled()

    def wait(self, seconds: float) -> None:
        """等待指定秒数，期间被取消则立刻抛出 Cancelled。"""
        if self._cancel.wait(seconds):
            raise Cancelled()
