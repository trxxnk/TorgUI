#!/usr/bin/env python3
"""Assemble docs/demo.gif from the lossless frames in docs/demo-frames/ (made by scripts/snap.js).

Usage: python3 scripts/make_demo_gif.py [FRAMES_DIR]
Frames are joined in file-name order. A caption and a duration (ms) are picked by file-name prefix
from STEPS; a frame without its own caption keeps the previous one. Needs Pillow.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIDTH = 1600   # frames are captured at 2400 px; 1600 stays sharp on GitHub and keeps the file small
BAR = 64
STEPS = [
    ("01", "Новое объявление: текст или ссылка на av.by", 1800),
    ("02", "Вставляем текст объявления", 1600),
    ("03", "Локальная модель в LM Studio читает объявление", 1200),
    ("04-parse-01", "Детали появляются по мере ответа модели (ускорено)", 900),
    ("04", None, 900),
    ("10", "Готово: дефекты нарисованы на кузове", 2200),
    ("11", "Карта данных: серое — о чём продавец промолчал", 1800),
    ("12", None, 1800),
    ("13", "Вписываем ответ продавца на вопрос", 2400),
    ("14", "Модель обновляет детали и описание", 1800),
    ("15", "Ответ учтён. В карточке детали: дефект, цитата, источник", 3000),
    ("16", "Модель после ответа", 2200),
    ("17", "Итог на карте данных", 3200),
]
# Small UI accents (status dots, buttons) that a per-frame palette would otherwise drop.
ACCENTS = ["#46b47a", "#3f7a5a", "#e2ac3a", "#e2574a", "#6d7582", "#6aa8f5", "#1c69d4", "#ffffff",
           "#81c4ff", "#16588e", "#e7222e", "#6b1626", "#e8ebf0", "#9aa3b0", "#14171c", "#1c2027"]
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"


def quantize(im):
    base = im.quantize(colors=256 - len(ACCENTS), method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = base.getpalette()[:(256 - len(ACCENTS)) * 3]
    for c in ACCENTS:
        pal += [int(c[i:i + 2], 16) for i in (1, 3, 5)]
    holder = Image.new("P", (1, 1))
    holder.putpalette(pal)
    # no dithering: flat UI colours stay flat and the file stays several times smaller
    return im.quantize(palette=holder, dither=Image.Dither.NONE)


def main(src):
    names = sorted(n for n in os.listdir(src) if n.endswith(".png"))
    if not names:
        sys.exit("no PNG frames in " + src)
    font = ImageFont.truetype(FONT, 30)
    frames, durations, caption = [], [], ""
    for name in names:
        step = next((s for s in STEPS if name.startswith(s[0])), None)
        if not step:
            sys.exit("no step for frame " + name)
        caption = step[1] or caption
        shot = Image.open(os.path.join(src, name)).convert("RGB")
        shot = shot.resize((WIDTH, round(shot.height * WIDTH / shot.width)), Image.Resampling.LANCZOS)
        out = Image.new("RGB", (WIDTH, shot.height + BAR), (20, 23, 28))
        out.paste(shot, (0, 0))
        draw = ImageDraw.Draw(out)
        draw.rectangle([0, shot.height, WIDTH, shot.height + BAR], fill=(28, 105, 212))
        draw.text(((WIDTH - draw.textlength(caption, font=font)) / 2, shot.height + 14), caption, font=font, fill=(255, 255, 255))
        frames.append(quantize(out))
        durations.append(step[2])
    dst = os.path.join(ROOT, "docs", "demo.gif")
    frames[0].save(dst, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True)
    print("%d frames, %.1f s, %dx%d, %d KB -> %s" % (len(frames), sum(durations) / 1000, WIDTH, frames[0].height, os.path.getsize(dst) // 1024, dst))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs", "demo-frames"))
