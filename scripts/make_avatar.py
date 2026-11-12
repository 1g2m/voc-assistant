# -*- coding: utf-8 -*-
"""
客服头像生成器
================
生成「西门子售后智能客服」的客服头像图标（petrol 圆底 + 白色耳机客服图形 + 亮青麦克风），
输出到 assets/avatar_service.png。重复运行会覆盖生成。

运行：python scripts/make_avatar.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 128          # 画布边长（px）
PETROL = "#00646E"  # 圆底色（品牌 petrol）
WHITE = "#FFFFFF"   # 耳机图形
ACCENT = "#2CCBDA"  # 麦克风亮点（品牌亮青）

OUT = Path(__file__).parent.parent / "assets" / "avatar_service.png"


def make_avatar() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 圆形底
    d.ellipse((0, 0, SIZE, SIZE), fill=PETROL)

    # 头梁（上半弧）
    d.arc((36, 30, 92, 86), start=180, end=360, fill=WHITE, width=8)

    # 左右耳罩
    d.rounded_rectangle((30, 58, 46, 84), radius=7, fill=WHITE)
    d.rounded_rectangle((82, 58, 98, 84), radius=7, fill=WHITE)

    # 麦克风杆（从左耳罩下沿弯出）+ 亮青咪头
    d.arc((30, 72, 64, 106), start=15, end=115, fill=WHITE, width=6)
    d.ellipse((54, 92, 68, 106), fill=ACCENT)

    return img


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    make_avatar().save(OUT)
    print(f"✅ 已生成 {OUT}")
