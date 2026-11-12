"""把 5 张 GIF 上传到 Steam 创意工坊。"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from app import config, planning
from app.events import Cancelled, Reporter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UploadJob:
    gif_paths: tuple[str, ...]
    browser: str = config.BROWSERS[0]
    title: str = ""  # 空字符串表示条目不显示名称

    def item_title(self, index: int) -> str:
        return f"{self.title}_{index}"


def upload_worker(job: UploadJob, reporter: Reporter) -> None:
    """后台线程入口：任何结果都以一条结束消息报告给界面。"""
    from app.upload import selenium_backend

    try:
        for path in job.gif_paths:
            if not os.path.isfile(path):
                raise planning.JobError("err_missing_gifs", name=os.path.basename(path))
        selenium_backend.run(job, reporter)
    except Cancelled:
        reporter.cancelled()
    except planning.JobError as error:
        reporter.error(error.key, **error.params)
    except Exception as error:
        logger.exception("上传失败")
        reporter.error("err_unexpected", detail=str(error))
    else:
        reporter.done("msg_upload_done")
