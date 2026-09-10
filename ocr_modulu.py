# -*- coding: utf-8 -*-
"""
RapidOCR tabanlı OCR modülü.
PP-OCRv4 modellerini ONNX Runtime ile çalıştırır.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_ocr = None


def _get_ocr():
    global _ocr
    if _ocr is None:
        try:
            from rapidocr import RapidOCR
            _ocr = RapidOCR()
        except ImportError:
            logger.error("rapidocr kurulu değil: pip install rapidocr")
            return None
    return _ocr


def gorsel_onyukle(gorsel_yolu: str | Path) -> Optional[np.ndarray]:
    """Görüntüyü okur ve OCR için hazırlar."""
    try:
        img = cv2.imread(str(gorsel_yolu))
        if img is None:
            logger.error("Görüntü okunamadı: %s", gorsel_yolu)
            return None
        return img
    except Exception as e:
        logger.error("Görüntü yükleme hatası: %s", e)
        return None


def metin_oku(
    gorsel_yolu: str | Path,
    esik: float = 0.5,
    buyutme: int = 1,
) -> list[dict]:
    """
    Görüntüden metin tanır.
    [{text, confidence, box}] listesi döner.
    """
    ocr = _get_ocr()
    if ocr is None:
        return []

    img = gorsel_onyukle(gorsel_yolu)
    if img is None:
        return []

    # Görüntüyü büyüt (daha iyi tanıma için)
    if buyutme > 1:
        img = cv2.resize(img, None, fx=buyutme, fy=buyutme, interpolation=cv2.INTER_CUBIC)

    cikti = ocr(img)
    if cikti is None or not hasattr(cikti, "txts") or cikti.txts is None:
        return []

    satirlar = []
    for box, metin, guven in zip(cikti.boxes, cikti.txts, cikti.scores):
        if float(guven) >= esik:
            satirlar.append({
                "text": metin,
                "confidence": float(guven),
                "box": box.tolist() if hasattr(box, "tolist") else box,
            })
    return satirlar


def duz_metin_oku(
    gorsel_yolu: str | Path,
    esik: float = 0.5,
    buyutme: int = 1,
) -> str:
    """Görüntüden düz metin döner (satır satır)."""
    satirlar = metin_oku(gorsel_yolu, esik=esik, buyutme=buyutme)
    return "\n".join(s["text"] for s in satirlar)


def captcha_coz(
    gorsel_yolu: str | Path,
    esik: float = 0.3,
) -> str:
    """Captcha görüntüsünden metin tanır (düşük eşik ile)."""
    ocr = _get_ocr()
    if ocr is None:
        return ""

    img = gorsel_onyukle(gorsel_yolu)
    if img is None:
        return ""

    # Captcha için ön işleme
    gri = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Otsu threshold
    _, ikili = cv2.threshold(gri, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Morfolojik temizleme
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    ikili = cv2.morphologyEx(ikili, cv2.MORPH_CLOSE, kernel)

    # 3x büyütme
    ikili_buyuk = cv2.resize(ikili, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

    cikti = ocr(ikili_buyuk)
    if cikti is None or not hasattr(cikti, "txts") or cikti.txts is None:
        return ""

    # En yüksek güvenli sonucu al
    en_iyi = ""
    max_guven = 0.0
    for metin, guven in zip(cikti.txts, cikti.scores):
        metin = metin.strip()
        guven = float(guven)
        if guven > max_guven and metin:
            max_guven = guven
            en_iyi = metin

    # Sadece alfanümerik karakterleri tut
    return re.sub(r"[^a-zA-Z0-9]", "", en_iyi)


def tablo_oku(
    gorsel_yolu: str | Path,
    esik: float = 0.5,
) -> list[list[str]]:
    """
    Tablo görüntüsünden satır/sütun yapısını koruyarak okur.
    [[satir1_sutun1, satir1_sutun2, ...], ...] formatında.
    """
    satirlar = metin_oku(gorsel_yolu, esik=esik)
    if not satirlar:
        return []

    # Y koordinatlarına göre sırala
    satirlar.sort(key=lambda s: min(p[1] for p in s["box"]))

    # Satır grupla (aynı yatay hizada olanlar)
    tablo = []
    mevcut_satir = []
    son_y = None

    for s in satirlar:
        y = sum(p[1] for p in s["box"]) / 4
        if son_y is None or abs(y - son_y) < 20:
            mevcut_satir.append(s)
        else:
            # X koordinatlarına göre sırala ve metinleri birleştir
            mevcut_satir.sort(key=lambda s: min(p[0] for p in s["box"]))
            tablo.append([m["text"] for m in mevcut_satir])
            mevcut_satir = [s]
        son_y = y

    if mevcut_satir:
        mevcut_satir.sort(key=lambda s: min(p[0] for p in s["box"]))
        tablo.append([m["text"] for m in mevcut_satir])

    return tablo


def pdfden_sayfa_gorsel(pdf_yolu: str | Path, sayfa_no: int = 0) -> Optional[np.ndarray]:
    """PDF sayfasını görsele çevirir."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(pdf_yolu))
        if sayfa_no >= len(doc):
            logger.error("Sayfa numarası geçersiz: %d / %d", sayfa_no, len(doc))
            return None
        sayfa = doc[sayfa_no]
        pix = sayfa.get_pixmap(dpi=300)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, 3)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        doc.close()
        return img
    except ImportError:
        logger.error("PyMuPDF kurulu değil: pip install PyMuPDF")
        return None
    except Exception as e:
        logger.error("PDF okuma hatası: %s", e)
        return None


def pdf_oku(pdf_yolu: str | Path, sayfa_no: int = 0) -> str:
    """PDF sayfasından metin okur."""
    gorsel = pdfden_sayfa_gorsel(pdf_yolu, sayfa_no)
    if gorsel is None:
        return ""
    return duz_metin_oku(gorsel)


def fatura_oku(fatura_yolu: str | Path) -> dict:
    """
    Fatura görüntüsünden yapılandırılmış veri çıkarır.
    {tarih, seri, numara, vkn_tckn, toplam, kdv, satirlar} formatında.
    """
    satirlar = metin_oku(fatura_yolu, esik=0.4)
    tum_metin = "\n".join(s["text"] for s in satirlar)

    sonuc = {
        "ham_metin": tum_metin,
        "tarih": None,
        "seri": None,
        "numara": None,
        "vkn_tckn": None,
        "toplam": None,
        "kdv": None,
        "satirlar": [],
    }

    # Tarih pattern (GG.AA.YYYY veya GG/AA/YYYY)
    tarih_eslesme = re.search(r"(\d{1,2}[./]\d{1,2}[./]\d{4})", tum_metin)
    if tarih_eslesme:
        sonuc["tarih"] = tarih_eslesme.group(1)

    # VKN/TCKN (10 veya 11 haneli)
    vkn_eslesme = re.search(r"\b(\d{10,11})\b", tum_metin)
    if vkn_eslesme:
        sonuc["vkn_tckn"] = vkn_eslesme.group(1)

    # Toplam tutar
    tutar_patterns = [
        r"(?:Toplam|TOPLAM|Genel\s+Toplam)[^\d]*(\d+[.,]\d{2})",
        r"(?:Tutar|TUTAR)[^\d]*(\d+[.,]\d{2})",
    ]
    for pat in tutar_patterns:
        eslesme = re.search(pat, tum_metin, re.IGNORECASE)
        if eslesme:
            sonuc["toplam"] = eslesme.group(1).replace(",", ".")
            break

    # KDV tutarı
    kdv_patterns = [
        r"(?:KDV|K\.D\.V\.|Vergi)[^\d]*(\d+[.,]\d{2})",
        r"(?:Toplam\s+Vergi|TOPLAM\s+VERGİ)[^\d]*(\d+[.,]\d{2})",
    ]
    for pat in kdv_patterns:
        eslesme = re.search(pat, tum_metin, re.IGNORECASE)
        if eslesme:
            sonuc["kdv"] = eslesme.group(1).replace(",", ".")
            break

    return sonuc


def goruntu_on_isleme(img: np.ndarray, yontem: str = "otsu") -> np.ndarray:
    """OCR öncesi görüntü ön işleme."""
    gri = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if yontem == "otsu":
        _, sonuc = cv2.threshold(gri, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    elif yontem == "adaptif":
        sonuc = cv2.adaptiveThreshold(
            gri, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
    elif yontem == "denoise":
        sonuc = cv2.fastNlMeansDenoising(gri, None, 10, 7, 21)
        _, sonuc = cv2.threshold(sonuc, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    else:
        sonuc = gri

    return sonuc
