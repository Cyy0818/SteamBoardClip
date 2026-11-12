"""生成图标：深色底上的 5 条展柜列。

assets/icon.ico 是 exe 文件的图标，
assets/app_settings/icon.png 是窗口与任务栏的图标。
"""

import os

from PIL import Image, ImageDraw

SIZE = 256
BACKGROUND = (23, 24, 26, 255)
ACCENT = (102, 192, 244, 255)


def build() -> Image.Image:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((8, 8, SIZE - 8, SIZE - 8), radius=44, fill=BACKGROUND)
    bar_width, gap, top, bottom = 28, 10, 60, SIZE - 60
    left = (SIZE - (bar_width * 5 + gap * 4)) // 2
    for index in range(5):
        x = left + index * (bar_width + gap)
        draw.rectangle((x, top, x + bar_width, bottom), fill=ACCENT)
    return image


def main() -> None:
    assets = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
    os.makedirs(os.path.join(assets, "app_settings"), exist_ok=True)
    image = build()
    image.save(os.path.join(assets, "icon.ico"),
               sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    image.save(os.path.join(assets, "app_settings", "icon.png"))


if __name__ == "__main__":
    main()
