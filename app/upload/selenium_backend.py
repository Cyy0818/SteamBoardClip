"""内置上传方式：通过 Selenium 控制 Edge 或者 Chrome。"""

from __future__ import annotations

import os
import time

from app import config, paths, planning
from app.events import Reporter

_LOGIN_FORM = '//*[@id="responsive_page_template_content"]//form'
# 展柜需要这三个隐藏字段：应用 480、通用文件类型、公开可见。
_SHOWCASE_FIELDS_JS = """
    $J('[name=consumer_app_id]').val(480);
    $J('[name=file_type]').val(0);
    $J('[name=visibility]').val(0);
"""
# 没有填写标题时使用：提交之前把标题替换成空白字符，展柜里的条目下方不显示名称。
# v_trim 被替换成原样返回，页面提交时不会把空白标题裁掉。
_BLANK_TITLE_JS = (
    "v_trim=_=>{return _},"
    "$J('#title').val(' \\n'+Array.from(Array(126),_=>'\\t').join(''));"
)


def read_credentials(path: str) -> tuple[str, str]:
    """读取 user.txt：第 1 行账号，第 2 行密码。内容不写入日志。"""
    with open(path, "r", encoding="utf-8-sig") as handle:
        account, password = handle.readline().strip(), handle.readline().strip()
    if not account or not password:
        raise planning.JobError("err_credentials")
    return (account, password)


def _start_browser(browser: str):
    from selenium import webdriver

    if browser == "Chrome":
        return webdriver.Chrome(options=webdriver.ChromeOptions())
    options = webdriver.EdgeOptions()
    options.page_load_strategy = "eager"
    return webdriver.Edge(options=options)


def _autofill(driver, credentials: tuple[str, str]) -> None:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    WebDriverWait(driver, config.PAGE_LOAD_TIMEOUT_S).until(
        lambda d: d.find_element(By.XPATH, f"{_LOGIN_FORM}//input")
    )
    fields = driver.find_elements(By.XPATH, f"{_LOGIN_FORM}//input")
    if len(fields) < 2:
        raise planning.JobError("err_login_form")
    for field, value in zip(fields[:2], credentials):
        field.clear()
        field.send_keys(value)
    driver.find_element(By.XPATH, f'{_LOGIN_FORM}//button[@type="submit"]').click()


def _wait_for_login(driver, reporter: Reporter) -> None:
    deadline = time.monotonic() + config.LOGIN_TIMEOUT_S
    while driver.current_url != config.STEAM_EDIT_URL:
        if time.monotonic() > deadline:
            raise planning.JobError("err_login_timeout")
        reporter.wait(0.5)


def _upload_one(driver, job, index: int, gif_path: str) -> None:
    from selenium.common.exceptions import TimeoutException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    wait = WebDriverWait(driver, config.PAGE_LOAD_TIMEOUT_S)
    title_field = wait.until(lambda d: d.find_element(By.CLASS_NAME, "titleField"))
    if job.title:
        title_field.clear()
        title_field.send_keys(job.item_title(index))
    driver.find_element(By.ID, "file").send_keys(os.path.abspath(gif_path))
    driver.find_element(By.ID, "agree_terms").click()
    driver.execute_script(_SHOWCASE_FIELDS_JS)
    if not job.title:
        driver.execute_script(_BLANK_TITLE_JS)
    driver.find_element(By.XPATH, '//*[@id="SubmitItemForm"]/div[6]/a[2]').click()
    # 条目创建成功之后 Steam 会离开编辑页面。
    try:
        WebDriverWait(driver, config.SUBMIT_TIMEOUT_S).until(
            lambda d: d.current_url != config.STEAM_EDIT_URL
        )
    except TimeoutException as error:
        raise planning.JobError("err_submit_timeout", index=index) from error


def run(job, reporter: Reporter) -> None:
    reporter.log("log_browser_start", browser=job.browser)
    driver = _start_browser(job.browser)
    try:
        _upload_all(driver, job, reporter)
    except BaseException:
        # 取消、超时或者出错时关闭浏览器。成功时浏览器保持打开，用于检查结果。
        driver.quit()
        raise


def _upload_all(driver, job, reporter: Reporter) -> None:
    driver.get(config.STEAM_EDIT_URL)
    reporter.check_cancelled()

    if driver.current_url != config.STEAM_EDIT_URL:
        if os.path.exists(paths.credentials_file()):
            _autofill(driver, read_credentials(paths.credentials_file()))
        reporter.log("log_login_wait")
        _wait_for_login(driver, reporter)

    total = len(job.gif_paths)
    for index, gif_path in enumerate(job.gif_paths, start=1):
        reporter.check_cancelled()
        reporter.log("log_uploading", index=index, total=total)
        if index > 1:
            driver.get(config.STEAM_EDIT_URL)
        _upload_one(driver, job, index, gif_path)
        reporter.progress(index / total)
