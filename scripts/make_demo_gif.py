#!/usr/bin/env python3
"""Assemble docs/demo.gif from screenshots of the running app.

Usage: python3 scripts/make_demo_gif.py [FRAMES_DIR]   (default: docs/demo-frames)
FRAMES_DIR holds 800x450 screenshots; the frame list below names them by the
unique tag at the end of each file name, with a caption and a duration in ms.
Needs Pillow.
"""
import glob
import os
import sys

from PIL import Image, ImageDraw, ImageFont

FRAMES = [
    ("svmpea", "Новое объявление: текст или ссылка на av.by", 1800),
    ("n5oeeq", "Вставляем текст объявления", 1500),
    ("qghwd6", "Локальная модель в LM Studio читает объявление", 1000),
    ("zd5cia", "Детали появляются по мере ответа модели (ускорено)", 800),
    ("0tzv3p", None, 800), ("hpyxn9", None, 800), ("hayyzc", None, 800),
    ("nk2s07", None, 800), ("0n2oci", None, 800), ("m29ohc", None, 800),
    ("dtkcrv", "Готово: дефекты нарисованы на кузове", 2000),
    ("7milwa", "Карта данных: серое — о чём продавец промолчал", 1600),
    ("ft4h7e", None, 1600),
    ("8q2rzg", "Вписываем ответ продавца на вопрос", 2200),
    ("qgv0cy", "Модель обновляет детали и описание", 1600),
    ("yoq2ph", "Ответ учтён. В карточке детали: дефект, цитата, источник", 2800),
    ("74x9lx", "Итог на карте данных", 2800),
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
    return im.quantize(palette=holder, dither=Image.Dither.FLOYDSTEINBERG)


def main(src):
    font = ImageFont.truetype(FONT, 17)
    frames, durations, caption = [], [], ""
    for tag, text, ms in FRAMES:
        found = glob.glob(os.path.join(src, "*%s.jpg" % tag))
        if len(found) != 1:
            sys.exit("frame %s: expected one file, found %d" % (tag, len(found)))
        caption = text or caption
        out = Image.new("RGB", (800, 486), (20, 23, 28))
        out.paste(Image.open(found[0]).convert("RGB"), (0, 0))
        draw = ImageDraw.Draw(out)
        draw.rectangle([0, 450, 800, 486], fill=(28, 105, 212))
        draw.text(((800 - draw.textlength(caption, font=font)) / 2, 458), caption, font=font, fill=(255, 255, 255))
        frames.append(quantize(out))
        durations.append(ms)
    dst = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "demo.gif")
    frames[0].save(dst, save_all=True, append_images=frames[1:], duration=durations, loop=0)
    print("%d frames, %.1f s, %d KB -> %s" % (len(frames), sum(durations) / 1000, os.path.getsize(dst) // 1024, dst))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "demo-frames"))
