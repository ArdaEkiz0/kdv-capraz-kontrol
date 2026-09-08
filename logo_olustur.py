"""Uygulama logosunu uretir: logo.ico (16-256) ve logo.png (64).

Kullanim: py -3 -X utf8 logo_olustur.py
"""
import os
from PIL import Image, ImageDraw

YOL = os.path.dirname(os.path.abspath(__file__))
S = 512

MAVI = (59, 130, 246)
MOR = (124, 58, 237)
BEYAZ = (255, 255, 255)
CIZGI = (203, 213, 225)
YESIL = (16, 185, 129)


def gradyan(boyut):
    img = Image.new("RGB", (boyut, boyut))
    px = img.load()
    for y in range(boyut):
        for x in range(boyut):
            t = (x + y) / (2 * boyut)
            px[x, y] = tuple(int(a + (b - a) * t) for a, b in zip(MAVI, MOR))
    return img


def logo_uret():
    arka = gradyan(S)
    maske = Image.new("L", (S, S), 0)
    ImageDraw.Draw(maske).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=255)
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    img.paste(arka, (0, 0), maske)

    ciz = ImageDraw.Draw(img)

    ciz.rounded_rectangle([128, 84, 368, 436], radius=28, fill=BEYAZ)
    for i, y in enumerate((168, 232, 296)):
        genislik = 190 if i < 2 else 120
        ciz.rounded_rectangle([176, y, 176 + genislik, y + 26], radius=13, fill=CIZGI)

    ciz.ellipse([268, 268, 476, 476], fill=YESIL, outline=(255, 255, 255, 255), width=16)
    ciz.line([(318, 376), (360, 418)], fill=BEYAZ, width=30)
    ciz.line([(360, 418), (428, 328)], fill=BEYAZ, width=30)

    return img


def ana():
    img = logo_uret()

    master = img.resize((256, 256), Image.LANCZOS)
    master.save(os.path.join(YOL, "logo.ico"),
                sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                       (64, 64), (128, 128), (256, 256)])

    img.resize((64, 64), Image.LANCZOS).save(os.path.join(YOL, "logo.png"))
    print("logo.ico ve logo.png olusturuldu")


if __name__ == "__main__":
    ana()
