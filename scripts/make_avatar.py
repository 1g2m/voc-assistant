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
INK = "#062B30"     # 耳机图形（深墨青，在浅色渐变底上保持对比）
WHITE = "#FFFFFF"   # 麦克风咪头点缀
# 渐变圆底：左上亮青 → 右下 petrol（贴合页面 hero 极光渐变色系）
GRAD_START = (44, 203, 218)   # #2CCBDA
GRAD_END = (0, 100, 110)      # #00646E

OUT = Path(__file__).parent.parent / "assets" / "avatar_service.png"


def _gradient_base() -> Image.Image:
    """对角线性渐变底（左上 GRAD_START → 右下 GRAD_END）"""
    base = Image.new("RGB", (SIZE, SIZE))
    px = base.load()
    for y in range(SIZE):
        for x in range(SIZE):
            t = (x + y) / (2 * (SIZE - 1))
            px[x, y] = tuple(int(a + (b - a) * t) for a, b in zip(GRAD_START, GRAD_END))
    return base


def make_avatar() -> Image.Image:
    # 渐变圆底（用圆形 mask 从渐变方块中抠出）
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, SIZE, SIZE), fill=255)
    img = Image.composite(_gradient_base().convert("RGBA"), Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0)), mask)
    d = ImageDraw.Draw(img)

    # 头梁（上半弧）
    d.arc((36, 30, 92, 86), start=180, end=360, fill=INK, width=8)

    # 左右耳罩
    d.rounded_rectangle((30, 58, 46, 84), radius=7, fill=INK)
    d.rounded_rectangle((82, 58, 98, 84), radius=7, fill=INK)

    # 麦克风杆（从左耳罩下沿弯出）+ 白色咪头
    d.arc((30, 72, 64, 106), start=15, end=115, fill=INK, width=6)
    d.ellipse((54, 92, 68, 106), fill=WHITE)

    return img


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    make_avatar().save(OUT)
    print(f"✅ 已生成 {OUT}")
