import re
from decimal import Decimal, ROUND_HALF_UP

from efatura import pdf_metni_al
from utils import fatura_no_temizle, tarih_parse, tutar_parse

HESAP_KODU_DESENI = re.compile(r"^\d{3}\.\d{1,2}\.\d{3}$")
TUTAR_SATIR_DESENI = re.compile(r"^\d{1,3}(?:\.\d{3})*(?:,\d{2})$")
TARIH_SATIR_DESENI = re.compile(r"^:\s*(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})$")
FIS_NO_SATIR_DESENI = re.compile(r"^:\s*(\d{3,10})$")
NEDEN_SATIR_DESENI = re.compile(r"^:\s*(.+)$")
ACIKLAMA_DESENI = re.compile(r"(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})\s+([A-Za-z0-9#№\-/]+)")
ORAN_DESENI = re.compile(r"\.(\d{3})$")
FIS_NO_ETIKET = re.compile(r"^Fiş\s*No\s*:?\s*(\d{3,10})?$")
NEDEN_ETIKET = re.compile(r"^Belge\s*Düzenleme\s*Nedeni\s*:?\s*(.*)$")
HEADER_TARIH = re.compile(r"^Tarih\s*:\s*(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})$")

KIRILIM_BASLANGICI = ("MAHSUP", "FİŞ TOPLAM")


def _mahsup_mi(metin):
    ust = (metin or "").upper()
    return "MAHSUP" in ust and "FİŞİ" in ust and ("Z RAPORU" in ust or "FİŞ TOPLAM" in ust)


def _fis_baslangici_mi(satir):
    return satir == "Tarih" or bool(HEADER_TARIH.match(satir))


def _baslik_oku(satirlar, i):
    """'Tarih' satırından başlayan fiş başlık bloğunu okur."""
    tarih = None
    fis_no = None
    neden = ""
    j = i
    sinir = min(i + 30, len(satirlar))
    beklenen_neden = False
    while j < sinir:
        satir = satirlar[j]
        if HESAP_KODU_DESENI.match(satir) or satir.startswith("FİŞ TOPLAM"):
            break
        m = TARIH_SATIR_DESENI.match(satir)
        if m and tarih is None:
            tarih = tarih_parse(m.group(1))
            j += 1
            continue
        m = HEADER_TARIH.match(satir)
        if m and tarih is None:
            tarih = tarih_parse(m.group(1))
            j += 1
            continue
        m = FIS_NO_SATIR_DESENI.match(satir)
        if m and fis_no is None:
            fis_no = m.group(1)
            j += 1
            continue
        m = FIS_NO_ETIKET.match(satir)
        if m and m.group(1) and fis_no is None:
            fis_no = m.group(1)
            j += 1
            continue
        m = NEDEN_ETIKET.match(satir)
        if m:
            if m.group(1).strip():
                neden = m.group(1).strip()
            else:
                beklenen_neden = True
            j += 1
            continue
        if beklenen_neden and satir.startswith(":"):
            neden = satir[1:].strip()
            beklenen_neden = False
        j += 1
    return tarih, fis_no, neden, j


def _satirlari_oku(satirlar, baslangic):
    satirlar_liste = []
    i = baslangic
    while i < len(satirlar):
        satir = satirlar[i]
        if _fis_baslangici_mi(satir):
            break
        if satir.startswith("FİŞ TOPLAM"):
            break
        m = HESAP_KODU_DESENI.match(satir)
        if m:
            hesap_kodu = satir
            hesap_adi = ""
            if i + 1 < len(satirlar) and not HESAP_KODU_DESENI.match(satirlar[i + 1]):
                hesap_adi = satirlar[i + 1]
            aciklama = None
            k = i + 2
            sinir = min(i + 8, len(satirlar))
            while k < sinir:
                s = satirlar[k]
                if HESAP_KODU_DESENI.match(s) or s.startswith("FİŞ TOPLAM") or _fis_baslangici_mi(s):
                    break
                if ACIKLAMA_DESENI.search(s):
                    aciklama = s
                    break
                k += 1
            borc = alacak = None
            if aciklama is not None:
                k += 1
                tutarlar = []
                while k < len(satirlar) and len(tutarlar) < 2:
                    s = satirlar[k]
                    if TUTAR_SATIR_DESENI.match(s):
                        tutarlar.append(tutar_parse(s))
                    elif HESAP_KODU_DESENI.match(s) or s.startswith("FİŞ TOPLAM") or _fis_baslangici_mi(s):
                        break
                    k += 1
                if len(tutarlar) == 2:
                    borc, alacak = tutarlar
            satirlar_liste.append({
                "hesap_kodu": hesap_kodu,
                "hesap_adi": hesap_adi,
                "aciklama": aciklama,
                "borc": borc,
                "alacak": alacak,
            })
        i += 1
    return satirlar_liste, i


def _fisleri_oku(dosya_yolu):
    metin = pdf_metni_al(dosya_yolu)
    if not _mahsup_mi(metin):
        return None
    satirlar = [s.strip() for s in metin.splitlines() if s.strip()]
    fisler = []
    i = 0
    acik_fis = None
    while i < len(satirlar):
        satir = satirlar[i]
        if _fis_baslangici_mi(satir):
            tarih, fis_no, neden, satir_bas = _baslik_oku(satirlar, i)
            if tarih is None and fis_no is None:
                i += 1
                continue
            rows, bitis = _satirlari_oku(satirlar, satir_bas)
            if acik_fis and acik_fis["fis_no"] and acik_fis["fis_no"] == fis_no:
                acik_fis["rows"].extend(rows)
            else:
                if acik_fis:
                    fisler.append(acik_fis)
                acik_fis = {"tarih": tarih, "fis_no": fis_no, "neden": neden, "rows": rows}
            i = bitis
        else:
            i += 1
    if acik_fis:
        fisler.append(acik_fis)
    return fisler


def _belge_grubu(aciklama):
    m = ACIKLAMA_DESENI.search(aciklama or "")
    if not m:
        return None
    tarih = tarih_parse(m.group(1))
    token = m.group(2)
    geri_kalan = aciklama[m.end():].strip()
    ust = aciklama.upper()
    if "Z RAPORU" in ust:
        belge = "Z" + token if token.isdigit() else token.upper()
        tip = "Z RAPORU"
        unvan = ""
    elif token.upper().startswith("EAR"):
        belge = fatura_no_temizle(token)
        tip = "E-ARSIV"
        unvan = geri_kalan
    elif token.upper().startswith("EFA"):
        belge = fatura_no_temizle(token)
        tip = "E-FATURA"
        unvan = geri_kalan
    else:
        belge = fatura_no_temizle(token)
        tip = "MAHSUP"
        unvan = geri_kalan
    return {"belge": belge, "tarih": tarih, "tip": tip, "unvan": unvan}


def _gruplar(satirlar_liste):
    gruplar = {}
    sira = []
    for satir in satirlar_liste:
        if satir["aciklama"] is None or satir["borc"] is None or satir["alacak"] is None:
            continue
        bg = _belge_grubu(satir["aciklama"])
        if not bg or not bg["belge"]:
            continue
        anahtar = bg["belge"]
        if anahtar not in gruplar:
            gruplar[anahtar] = {
                "belge": bg["belge"],
                "tarih": bg["tarih"],
                "tip": bg["tip"],
                "unvan": bg["unvan"],
                "satirlar": [],
            }
            sira.append(anahtar)
        gruplar[anahtar]["satirlar"].append(satir)
    return [gruplar[a] for a in sira]


def _kdv_hesapla(grup):
    kdv_oranlar = []
    oranlar = []
    bilinmeyen = False
    for satir in grup["satirlar"]:
        hesap = satir["hesap_kodu"]
        if not (hesap.startswith("391") or hesap.startswith("191")):
            continue
        if "KDV" not in (satir["hesap_adi"] or "").upper():
            continue
        m = ORAN_DESENI.search(hesap)
        oran = int(m.group(1)) if m else 0
        if hesap.startswith("391"):
            deger = satir["alacak"] if satir["alacak"] else satir["borc"]
        else:
            deger = satir["borc"] if satir["borc"] else satir["alacak"]
        if deger is None:
            continue
        deger = abs(deger)
        if oran == 0:
            bilinmeyen = True
            continue
        kdv_oranlar.append((oran, deger))
        if oran not in oranlar:
            oranlar.append(oran)
    return kdv_oranlar, sorted(oranlar), bilinmeyen


def _matrah_ve_kdv(kdv_oranlar):
    if not kdv_oranlar:
        return None, None
    kdv = sum(d for _, d in kdv_oranlar)
    matrah = sum((d * Decimal(100) / Decimal(o)) for o, d in kdv_oranlar)
    return (matrah.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            kdv.quantize(Decimal("0.01")))


def _fatura_kaydi(dosya_yolu, grup, fis_no, neden):
    kdv_oranlar, oranlar, bilinmeyen = _kdv_hesapla(grup)
    if not kdv_oranlar:
        return None
    matrah, kdv = _matrah_ve_kdv(kdv_oranlar)
    notlar = [f"MAHSUP fişi {fis_no} ({neden})", "Matrah KDV oranlarından hesaplandı"]
    if bilinmeyen:
        notlar.append("Oranı bilinmeyen KDV var")
    return {
        "dosya": dosya_yolu,
        "tip": "fis_listesi",
        "sayfa": 1,
        "belge_no": grup["belge"],
        "tarih": grup["tarih"],
        "satici_vkn": "",
        "alici_vkn": "",
        "satici_unvan": grup["unvan"],
        "matrah": matrah,
        "kdv": kdv,
        "toplam": (matrah + kdv).quantize(Decimal("0.01")),
        "oranlar": oranlar,
        "fatura_tipi": grup["tip"],
        "oran_kontrol": "",
        "notlar": notlar,
    }


def _cetvel_kaydi(grup, fis_no):
    kdv_oranlar, oranlar, bilinmeyen = _kdv_hesapla(grup)
    if not kdv_oranlar:
        return None
    matrah, kdv = _matrah_ve_kdv(kdv_oranlar)
    return {
        "vkn": "",
        "belge_no": grup["belge"],
        "tarih": grup["tarih"],
        "matrah": matrah,
        "kdv": kdv,
        "unvan": grup["unvan"],
        "notlar": [f"Hesap: MAHSUP {fis_no}"],
    }


def fis_listesi_parse(dosya_yolu):
    try:
        fisler = _fisleri_oku(dosya_yolu)
    except Exception:
        return None
    if fisler is None:
        return None
    sonuc = []
    for fis in fisler:
        for grup in _gruplar(fis["rows"]):
            kayit = _fatura_kaydi(dosya_yolu, grup, fis["fis_no"], fis["neden"])
            if kayit:
                sonuc.append(kayit)
    return sonuc


def fis_listesi_hesap_parse(dosya_yolu):
    """MAHSUP fişi PDF'inden hesap bazlı belge kayıtlarını döndürür.

    Her kayıt: {belge, tarih, hesap, hesap_adi, borc, alacak}
    Muavin defteriyle hesap bazlı çapraz kontrol için kullanılır.
    """
    try:
        fisler = _fisleri_oku(dosya_yolu)
    except Exception:
        return None
    if fisler is None:
        return None
    kayitlar = []
    for fis in fisler:
        for satir in fis["rows"]:
            if satir["aciklama"] is None or satir["borc"] is None or satir["alacak"] is None:
                continue
            bg = _belge_grubu(satir["aciklama"])
            if not bg or not bg["belge"]:
                continue
            kayitlar.append({
                "belge": bg["belge"],
                "tarih": bg["tarih"],
                "hesap": satir["hesap_kodu"],
                "hesap_adi": satir["hesap_adi"],
                "borc": satir["borc"],
                "alacak": satir["alacak"],
            })
    return kayitlar


def fis_listesi_cetvel_parse(dosya_yolu):
    try:
        fisler = _fisleri_oku(dosya_yolu)
    except Exception:
        return None
    if fisler is None:
        return None
    kayitlar = []
    for fis in fisler:
        for grup in _gruplar(fis["rows"]):
            kayit = _cetvel_kaydi(grup, fis["fis_no"])
            if kayit:
                kayitlar.append(kayit)
    return {
        "dosya": dosya_yolu,
        "kayitlar": kayitlar,
        "notlar": ["MAHSUP fişi (fiş listesi) olarak okundu"],
    }
