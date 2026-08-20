import os
import re
from decimal import Decimal

from utils import fatura_no_temizle, tarih_parse, tutar_parse, vkn_temizle

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except Exception:
        fitz = None


def _pdfminer_metni(dosya_yolu):
    from pdfminer.high_level import extract_text
    return extract_text(dosya_yolu)


def pdf_metni_al(dosya_yolu):
    if fitz is not None:
        try:
            doc = fitz.open(dosya_yolu)
            parcalar = []
            for sayfa in doc:
                parcalar.append(sayfa.get_text())
            doc.close()
            return "\n".join(parcalar)
        except Exception:
            pass
    return _pdfminer_metni(dosya_yolu)


def eslesme_bul(metin, pattern, sayi=1):
    liste = re.findall(pattern, metin, re.IGNORECASE)
    if not liste:
        return None
    if sayi == 1:
        return liste[0]
    return liste


def sayfa_parse(sayfa_metni):
    sonuc = {
        "belge_no": None,
        "tarih": None,
        "satici_vkn": None,
        "alici_vkn": None,
        "matrah": None,
        "kdv": None,
        "toplam": None,
        "oranlar": [],
        "notlar": [],
    }
    metin = sayfa_metni or ""

    belge = eslesme_bul(metin, r"Belge\s*No\s*:?\s*([A-Za-z0-9\-/\.#№]+)")
    if belge:
        sonuc["belge_no"] = fatura_no_temizle(belge)

    if not sonuc["belge_no"]:
        sayisal_veri = eslesme_bul(metin, r"(?:Mal\s*Hizmet\s*(?:Toplam\s*)?Tutar\w*|Hesaplanan\s*KDV|Toplam|Ödenecek\s*Tutar)", sayi=0)
        if not sayisal_veri:
            return None

    tarih = eslesme_bul(metin, r"(?:Belge|Düzenlenme|Düzenleme|İşlem|İrsaliye)?\s*Tarihi\s*:?\s*(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})")
    if tarih:
        sonuc["tarih"] = tarih_parse(tarih)

    vkn_listesi = eslesme_bul(metin, r"Vergi\s*Kimlik\s*No\s*:?\s*(\d{10,11})", sayi=0)
    if vkn_listesi:
        if len(vkn_listesi) >= 2:
            sonuc["satici_vkn"] = vkn_listesi[0]
            sonuc["alici_vkn"] = vkn_listesi[1]
        else:
            sonuc["satici_vkn"] = vkn_listesi[0]

    matrah = eslesme_bul(metin, r"Mal\s*Hizmet\s*(?:Toplam\s*)?Tutar\w*\s*:?\s*([\d\.\,]+)")
    if matrah:
        sonuc["matrah"] = tutar_parse(matrah)

    kdv_listesi = eslesme_bul(metin, r"Hesaplanan\s*KDV\s*(?:\([^)]*\)\s*)?:?\s*([\d\.\,]+)", sayi=0)
    if kdv_listesi:
        toplam_kdv = sum((tutar_parse(k) or Decimal("0")) for k in kdv_listesi)
        if toplam_kdv:
            sonuc["kdv"] = toplam_kdv.quantize(Decimal("0.01"))

    toplam = eslesme_bul(metin, r"(?:Ödenecek\s*Tutar|Tahsil\s*Edilecek\s*Tutar|Tahakkuk\s*Edilen)\s*:?\s*([\d\.\,]+)")
    if not toplam:
        toplamlar = eslesme_bul(metin, r"Toplam\s*:?\s*([\d\.\,]+)", sayi=0)
        if toplamlar:
            toplam = toplamlar[-1]
    if toplam:
        sonuc["toplam"] = tutar_parse(toplam)

    oranlar = eslesme_bul(metin, r"KDV\s*Oran\w*\s*:?\s*%?\s*(\d{1,2})", sayi=0)
    if oranlar:
        sonuc["oranlar"] = sorted(set(int(o) for o in oranlar))

    if sonuc["kdv"] is None and sonuc["toplam"] is not None and sonuc["matrah"] is not None:
        fark = sonuc["toplam"] - sonuc["matrah"]
        if fark > 0:
            sonuc["kdv"] = fark.quantize(Decimal("0.01"))
            sonuc["notlar"].append("KDV tutarı (Toplam - Matrah) olarak hesaplandı")

    if sonuc["matrah"] is None or sonuc["kdv"] is None:
        sonuc["notlar"].append("Matrah/KDV tutarları bulunamadı, manuel kontrol edin")
    elif sonuc["toplam"] is not None:
        beklenen = (sonuc["matrah"] + sonuc["kdv"]).quantize(Decimal("0.01"))
        if abs(beklenen - sonuc["toplam"]) > Decimal("0.02"):
            sonuc["notlar"].append("Matrah+KDV ≠ Toplam (PDF tutarları tutarsız görünüyor)")

    sonuc["satici_vkn"] = vkn_temizle(sonuc["satici_vkn"])
    sonuc["alici_vkn"] = vkn_temizle(sonuc["alici_vkn"])
    return sonuc


def efatura_parse(dosya_yolu):
    sonuc_listesi = []
    try:
        doc = fitz.open(dosya_yolu)
    except Exception as hata:
        try:
            tam_metin = _pdfminer_metni(dosya_yolu)
            fatura = sayfa_parse(tam_metin)
            if fatura:
                fatura["dosya"] = dosya_yolu
                fatura["sayfa"] = 1
                fatura["notlar"].append("pdfminer ile okundu")
                return [fatura]
        except Exception:
            pass
        return [{
            "dosya": dosya_yolu,
            "sayfa": 1,
            "belge_no": None,
            "tarih": None,
            "satici_vkn": None,
            "alici_vkn": None,
            "matrah": None,
            "kdv": None,
            "toplam": None,
            "oranlar": [],
            "notlar": [f"PDF okunamadı: {hata}"],
        }]

    sayfa_sayisi = len(doc)
    for i in range(sayfa_sayisi):
        sayfa_metni = doc[i].get_text()
        fatura = sayfa_parse(sayfa_metni)
        if fatura is None:
            continue
        fatura["dosya"] = dosya_yolu
        fatura["sayfa"] = i + 1
        sonuc_listesi.append(fatura)
    doc.close()

    if not sonuc_listesi:
        from ocr import ocr_metin, tesseract_mevcut_mi
        notlar = []
        if not tesseract_mevcut_mi():
            notlar.append("PDF'den metin çıkarılamadı; Tesseract OCR kurulu değil (taranmış PDF olabilir)")
        else:
            try:
                ocr_metni = ocr_metin(dosya_yolu)
                fatura = sayfa_parse(ocr_metni)
                if fatura:
                    fatura["dosya"] = dosya_yolu
                    fatura["sayfa"] = 1
                    fatura["notlar"].append("OCR ile okundu")
                    sonuc_listesi.append(fatura)
                else:
                    notlar.append("OCR ile de fatura bilgisi çıkarılamadı")
            except Exception as hata:
                notlar.append(f"OCR başarısız: {hata}")
        if not sonuc_listesi:
            sonuc_listesi.append({
                "dosya": dosya_yolu,
                "sayfa": 1,
                "belge_no": None,
                "tarih": None,
                "satici_vkn": None,
                "alici_vkn": None,
                "matrah": None,
                "kdv": None,
                "toplam": None,
                "oranlar": [],
                "notlar": notlar if notlar else ["PDF'den metin çıkarılamadı (tarayıcı/taranmış PDF olabilir)"],
            })
    return sonuc_listesi
