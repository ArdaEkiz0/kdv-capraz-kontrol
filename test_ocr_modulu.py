# -*- coding: utf-8 -*-
"""OCR modülü testleri."""
import os
import sys
import tempfile
import numpy as np
import cv2

YOL = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, YOL)
TEMP = tempfile.gettempdir()

BASARILI = True


def kontrol(ad, kosul, detay=""):
    global BASARILI
    durum = "TAMAM" if kosul else "HATA"
    if not kosul:
        BASARILI = False
    print(f"  [{durum}] {ad} {detay}")


def test_rapidocr_yukleme():
    print("\n== 1) RAPIDOCR YUKLEME ==")
    try:
        from rapidocr_onnxruntime import RapidOCR
        ocr = RapidOCR()
        kontrol("RapidOCR import", True)
        kontrol("OCR nesnesi olustu", ocr is not None)
    except Exception as e:
        kontrol("RapidOCR import", False, str(e))


def test_metin_oku():
    print("\n== 2) METIN OKUMA ==")
    from ocr_modulu import metin_oku

    img = np.ones((120, 400, 3), dtype=np.uint8) * 255
    cv2.putText(img, "KDV Kontrol 2026", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 2)
    cv2.putText(img, "1234567890", (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    test_yolu = os.path.join(TEMP, "_test_ocr_kdv.png")
    cv2.imwrite(test_yolu, img)

    sonuclar = metin_oku(test_yolu, esik=0.3)
    kontrol("Sonuc listesi dolu", len(sonuclar) > 0, f"({len(sonuclar)} satir)")

    metinler = " ".join(s["text"] for s in sonuclar)
    kontrol("KDV tanindi", "KDV" in metinler or "KD" in metinler, f"({metinler[:50]})")
    kontrol("Guven yuksek", all(s["confidence"] > 0.5 for s in sonuclar))

    os.remove(test_yolu)


def test_duz_metin():
    print("\n== 3) DUZ METIN ==")
    from ocr_modulu import duz_metin_oku

    img = np.ones((80, 300, 3), dtype=np.uint8) * 255
    cv2.putText(img, "TEST 123", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    test_yolu = os.path.join(TEMP, "_test_ocr_kdv2.png")
    cv2.imwrite(test_yolu, img)

    duz = duz_metin_oku(test_yolu, esik=0.3)
    kontrol("Duz metin string", isinstance(duz, str))
    kontrol("Metin icerigi", "TEST" in duz or "123" in duz, f"({duz[:30]})")

    os.remove(test_yolu)


def test_on_isleme():
    print("\n== 4) GORUNTU ON ISLEME ==")
    from ocr_modulu import goruntu_on_isleme

    img = np.ones((100, 200, 3), dtype=np.uint8) * 200
    cv2.putText(img, "Test", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (50, 50, 50), 2)

    for yontem in ["otsu", "adaptif", "denoise"]:
        sonuc = goruntu_on_isleme(img, yontem)
        kontrol(f"Isleme ({yontem})", sonuc is not None and len(sonuc.shape) == 2)


if __name__ == "__main__":
    test_rapidocr_yukleme()
    test_metin_oku()
    test_duz_metin()
    test_on_isleme()
    print(f"\nSONUC: {'BASARILI' if BASARILI else 'BASARISIZ'}")
    sys.exit(0 if BASARILI else 1)
