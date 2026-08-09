import re

from utils import fatura_no_temizle, sayilari_bul, tarih_parse, tutar_parse, vkn_temizle
from efatura import pdf_metni_al

HARFLI_RAKAM = r"A-Za-z0-9ÇĞİÖŞÜçğıöşü\-/"

AMOUNT_DESENI = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?")
TARIH_DESENI = re.compile(r"\d{1,2}[./\-]\d{1,2}[./\-]\d{4}")
VKN_DESENI = re.compile(r"(?<!\d)\d{10,11}(?!\d)")
SIRA_DESENI = re.compile(r"\d{1,4}")
BELGE_DESENI = re.compile(rf"[{HARFLI_RAKAM}]+")


def hucre_sinifla(hucre):
    h = hucre.strip()
    if not h:
        return None, None
    if VKN_DESENI.fullmatch(h):
        return "vkn", h
    if TARIH_DESENI.fullmatch(h) and "," not in h:
        return "tarih", tarih_parse(h)
    h_temiz = h.replace("(", "0").replace(")", "0").replace("O", "0").replace("l", "1")
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})|\d+,\d{1,2}", h_temiz):
        return "tutar", tutar_parse(h_temiz)
    if BELGE_DESENI.fullmatch(h) and not SIRA_DESENI.fullmatch(h):
        harf = sum(1 for c in h if c.isalpha())
        rakam = sum(1 for c in h if c.isdigit())
        if harf and rakam >= 4:
            return "belge", fatura_no_temizle(h)
        if harf == 0 and 7 <= rakam <= 12 and not VKN_DESENI.fullmatch(h):
            return "belge", fatura_no_temizle(h)
    if SIRA_DESENI.fullmatch(h) and len(h) <= 4:
        return "sira", None
    return "metin", None


def satir_parcet(satir_metni):
    kelimeler = satir_metni.split()
    hucreler = []
    for k in kelimeler:
        sinif, deger = hucre_sinifla(k)
        hucreler.append((k, sinif, deger))
    return hucreler


def cetvel_satir_parse(hucreler):
    kayit = {
        "vkn": None,
        "belge_no": None,
        "tarih": None,
        "matrah": None,
        "kdv": None,
        "unvan": None,
        "notlar": [],
    }
    tutarlar = []
    belge_adaylari = []
    metinler = []
    for hucre, sinif, deger in hucreler:
        if sinif == "vkn":
            kayit["vkn"] = deger
        elif sinif == "tarih":
            kayit["tarih"] = deger
        elif sinif == "tutar":
            if deger is not None:
                tutarlar.append(deger)
        elif sinif == "belge":
            belge_adaylari.append((sum(1 for c in deger if c.isdigit()), deger))
        elif sinif == "metin":
            metinler.append(hucre)

    if belge_adaylari:
        kayit["belge_no"] = max(belge_adaylari, key=lambda x: x[0])[1]

    if len(tutarlar) >= 2:
        kayit["matrah"] = tutarlar[-2]
        kayit["kdv"] = tutarlar[-1]
    elif len(tutarlar) == 1:
        kayit["matrah"] = tutarlar[0]
        kayit["notlar"].append("KDV tutarı bulunamadı")
    else:
        kayit["notlar"].append("Tutar bulunamadı")

    if metinler:
        kayit["unvan"] = " ".join(metinler)[:100]

    if not kayit["vkn"]:
        return None
    return kayit


def blob_parse_fallback(satir_metni):
    kayit = {
        "vkn": None,
        "belge_no": None,
        "tarih": None,
        "matrah": None,
        "kdv": None,
        "unvan": None,
        "notlar": [],
    }
    vkn_m = VKN_DESENI.search(satir_metni)
    if vkn_m:
        kayit["vkn"] = vkn_m.group(0)
    tarih_m = TARIH_DESENI.search(satir_metni)
    if tarih_m:
        kayit["tarih"] = tarih_parse(tarih_m.group(0))
    temiz = re.sub(r"\d{1,2}[./\-]\d{1,2}[./\-]\d{4}", " ", satir_metni)
    if kayit["vkn"]:
        temiz = re.sub(re.escape(kayit["vkn"]), " ", temiz)
    tutarlar = sayilari_bul(temiz)
    if len(tutarlar) >= 2:
        kayit["matrah"] = tutarlar[-2]
        kayit["kdv"] = tutarlar[-1]
    elif len(tutarlar) == 1:
        kayit["matrah"] = tutarlar[0]
    if not kayit["vkn"]:
        return None
    adaylar = re.findall(rf"[{HARFLI_RAKAM}]+", temiz)
    en_iyi = None
    for a in adaylar:
        rakam = sum(1 for c in a if c.isdigit())
        harf = sum(1 for c in a if c.isalpha())
        if rakam < 6:
            continue
        if kayit["vkn"] and vkn_temizle(kayit["vkn"]) in a:
            continue
        puan = rakam * 10 + (1 if harf else 0)
        if en_iyi is None or puan > en_iyi[1]:
            en_iyi = (fatura_no_temizle(a), puan)
    if en_iyi:
        kayit["belge_no"] = en_iyi[0]
    kayit["unvan"] = " ".join(x for x in re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü\.\-/]{2,}", temiz) if len(x) > 2)[:100]
    return kayit


def cetvel_parse(dosya_yolu, ocr_denenebilir=True):
    sonuc = {
        "dosya": dosya_yolu,
        "kayitlar": [],
        "notlar": [],
    }
    try:
        metin = pdf_metni_al(dosya_yolu)
    except Exception as hata:
        sonuc["notlar"].append(f"PDF okunamadı: {hata}")
        return sonuc

    if not metin or not metin.strip():
        metin = _ocr_denemesi(dosya_yolu, sonuc)
        if not metin or not metin.strip():
            sonuc["notlar"].append("PDF'den metin çıkarılamadı (tarayıcı/taranmış PDF olabilir)")
            return sonuc

    sonuc["kayitlar"] = _kayitlari_ayikla(metin)

    if not sonuc["kayitlar"] and ocr_denenebilir and sonuc["notlar"]:
        ocr_metni = _ocr_denemesi(dosya_yolu, sonuc, tekrar=True)
        if ocr_metni and ocr_metni.strip() and ocr_metni != metin:
            sonuc["kayitlar"] = _kayitlari_ayikla(ocr_metni)

    if not sonuc["kayitlar"]:
        sonuc["notlar"].append("Cetvelde veri satırı bulunamadı (format farklı olabilir, satır içi VKN kontrol edin)")
    return sonuc


def _ocr_denemesi(dosya_yolu, sonuc, tekrar=False):
    from ocr import ocr_metin, tesseract_mevcut_mi
    if not tesseract_mevcut_mi():
        sonuc["notlar"].append("Taranmış PDF; Tesseract OCR kurulu değil")
        return None
    try:
        ocr_metni = ocr_metin(dosya_yolu)
        if ocr_metni.strip():
            if tekrar:
                sonuc["notlar"].append("OCR sonucu yeniden denendi")
            sonuc["notlar"].append("Taranmış PDF, OCR ile okundu")
            return ocr_metni
    except Exception as hata:
        sonuc["notlar"].append(f"OCR başarısız: {hata}")
    return None


def _kayitlari_ayikla(metin):
    satirlar = [s.strip() for s in metin.splitlines() if s.strip()]
    gruplar = []
    mevcut = []
    for satir in satirlar:
        if VKN_DESENI.search(satir):
            if mevcut:
                gruplar.append(mevcut)
            mevcut = [satir]
        elif mevcut:
            mevcut.append(satir)
    if mevcut:
        gruplar.append(mevcut)

    kayitlar = []
    gorulen = set()
    for grup in gruplar:
        kayit = None
        hucreli = []
        for satir in grup:
            hucreli.extend(satir_parcet(satir))
        kayit = cetvel_satir_parse(hucreli)
        if not kayit or (kayit["matrah"] is None and kayit["belge_no"] is None):
            kayit = blob_parse_fallback(" ".join(grup))
        if not kayit:
            continue
        anahtar = (kayit["vkn"], kayit["belge_no"] or "", str(kayit["matrah"] or ""), str(kayit["kdv"] or ""))
        if anahtar in gorulen:
            kayit["notlar"].append("Cetvel içinde mükerrer satır")
        gorulen.add(anahtar)
        kayitlar.append(kayit)
    return kayitlar
