import os
import shutil
import tempfile

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except Exception:
        fitz = None
from PIL import Image, ImageOps

import pytesseract

COZUNURLUK = 300


def tesseract_mevcut_mi():
    try:
        return fitz is not None and shutil.which("tesseract") is not None
    except Exception:
        return False


def sayfa_gorsel(dosya_yolu, sayfa_no, cozunurluk=COZUNURLUK):
    if fitz is None:
        raise RuntimeError("pymupdf yüklenemedi (DLL sorunu)")
    from efatura import PDF_KILIDI
    doc = fitz.open(dosya_yolu)
    try:
        with PDF_KILIDI:
            sayfa = doc[sayfa_no]
            matris = fitz.Matrix(cozunurluk / 72, cozunurluk / 72)
            pix = sayfa.get_pixmap(matrix=matris, alpha=False)
            gecici = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            gecici.close()
            pix.save(gecici.name)
        gorsel = Image.open(gecici.name)
        gorsel.load()
        os.unlink(gecici.name)
        return gorsel
    finally:
        doc.close()


def cizgileri_temizle(img):
    try:
        import numpy as np
    except ImportError:
        return ImageOps.grayscale(img)
    arr = np.array(ImageOps.grayscale(img))
    H, W = arr.shape
    karanlik = arr < 140
    sonuc = arr.copy()
    esik = max(40, int(W * 0.18))
    for y in range(H):
        satir = karanlik[y]
        uzun, en_iyi = 0, 0
        for x in range(W):
            if satir[x]:
                uzun += 1
                en_iyi = max(en_iyi, uzun)
            else:
                uzun = 0
        if en_iyi > esik:
            sonuc[y] = 255
    esik_d = max(40, int(H * 0.18))
    for x in range(W):
        sutun = karanlik[:, x]
        uzun, en_iyi = 0, 0
        for y in range(H):
            if sutun[y]:
                uzun += 1
                en_iyi = max(en_iyi, uzun)
            else:
                uzun = 0
        if en_iyi > esik_d:
            sonuc[:, x] = 255
    return Image.fromarray(sonuc)


def ocr_metin(dosya_yolu, sayfa_no=None):
    from efatura import PDF_KILIDI
    with PDF_KILIDI:
        doc = fitz.open(dosya_yolu)
        sayfalar = range(len(doc)) if sayfa_no is None else [sayfa_no]
        doc.close()
    parcalar = []
    for i in sayfalar:
        gorsel = sayfa_gorsel(dosya_yolu, i)
        try:
            temiz = cizgileri_temizle(gorsel)
            metin = pytesseract.image_to_string(
                temiz, lang="tur", config="--psm 4"
            )
        finally:
            gorsel.close()
        parcalar.append(metin)
    return "\n".join(parcalar)
