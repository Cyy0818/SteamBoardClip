"""切片、上传与界面共用的常量。"""

APP_NAME = "SteamBoardClip"
APP_VERSION = "1.0.0"

# 展柜几何：视频铺到 650x360 的画布上，切成 5 列，每列 126px，
# 列与列之间留出 Steam 展柜格子之间的 5px 空隙。
SEGMENT_COUNT = 5
SEGMENT_GAP_PX = 5
CANVAS_WIDTH = 650
CANVAS_HEIGHT = 360

# 体积预算：Steam 的上限是 5 MB，默认值略低于上限。
STEAM_LIMIT_BYTES = 5 * 1024 * 1024
MAX_GIF_BYTES = int(4.95 * 1024 * 1024)
MIN_LIMIT_MB = 0.5
# 最大一段低于预算的这个比例时，提高帧率重新渲染。
UNDERSIZE_RATIO = 0.70
# 提高帧率时瞄准预算的这个比例，给估算误差留出余量。
FILL_RATIO = 0.85

# 帧率与分辨率
MIN_FPS = 2
MAX_OUTPUT_FPS = 30
# (片段秒数, 起始帧率)，取第一条满足的。
INITIAL_FPS_STEPS = ((15, 10), (30, 8), (60, 6), (90, 5))
INITIAL_FPS_LONG = 4
# 帧率降到下限仍然超出预算时才缩小分辨率，缩放比例不低于 MIN_SCALE。
MIN_SCALE = 0.5
SCALE_SAFETY = 0.93
MAX_SCALE_PASSES = 6

# 压缩选项的可选值，帧率 0 表示自动。
FPS_LIMIT_CHOICES = (0, 30, 24, 20, 15, 12, 10, 8, 6, 4)
SCALE_PERCENT_CHOICES = (100, 90, 75, 60, 50)
COLOR_CHOICES = (256, 128, 64, 32)

# 低配置电脑：全部计算在 CPU 上完成。
# 一遍渲染的帧以 8 位调色板图像保存在内存里，每帧 5 列，每列约 45 KB，
# 限制帧数等于限制内存，2400 帧约 550 MB。
MAX_FRAMES_PER_PASS = 2400
# 预览每秒最多解码的帧数。
PREVIEW_MAX_FPS = 20
# 预览每次刷新最多跳过的源视频帧数。
PREVIEW_MAX_SKIP = 4

# 默认值
DEFAULT_CLIP_SECONDS = 120
DEFAULT_OUTPUT_PREFIX = "output_gif"
DEFAULT_WORKSHOP_TITLE = "gif"
VIDEO_EXTENSIONS = ("mp4", "mkv", "mov", "avi", "m4v", "webm", "flv", "wmv")
INVALID_FILENAME_CHARS = '<>:"/\\|?*'

# Steam 上传
STEAM_EDIT_URL = "https://steamcommunity.com/sharedfiles/edititem/767/3/"
BROWSERS = ("Edge", "Chrome")
PAGE_LOAD_TIMEOUT_S = 20
LOGIN_TIMEOUT_S = 300
SUBMIT_TIMEOUT_S = 90
CREDENTIALS_FILENAME = "user.txt"
