import os
import re
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from utils import fatura_no_temizle, tarih_parse, tutar_parse, vkn_temizle

KOLON_SINONIMLERI = {
    "belge_no": [
        "BELGE NO", "BELGE NUMARASI", "BELGE", "FATURA NO", "FATURA NUMARASI",
        "FATURA", "EVRAK NO", "IRSALIYE NO",
    ],
    "tarih": [
        "TARIH", "BELGE TARIHI", "FATURA TARIHI", "DUZENLENME TARIHI",
        "DUZENLEME TARIHI", "ISLEM TARIHI", "EVRAK TARIHI", "TARIH",
    ],
    "vkn": [
        "VKN", "VERGI KIMLIK NO", "VERGI NO", "TC KIMLIK NO", "TCKN",
        "KIMLIK NO", "T.C. KIMLIK NO",
    ],
    "matrah": [
        "MATRAH", "KDV MATRAHI", "MAL HIZMET TUTARI", "MAL HIZMET BEDELI",
        "KDV HARIC TUTAR", "TUTAR", "BEDEL", "ARACILIK HIZMETI",
    ],
    "kdv": [
        "KDV TUTARI", "HESAPLANAN KDV", "KDV", "VERGI TUTARI", "KDV TOPLAMI",
    ],
    "toplam": [
        "GENEL TOPLAM", "FATURA TOPLAMI", "TOPLAM TUTAR", "TOPLAM",
        "ODENECEK TUTAR", "ODENEN TUTAR", "GENEL TOPLAM",
    ],
    "oran": ["KDV ORANI", "ORAN", "KDV ORANI %", "ORAN %"],
    "unvan": [
        "UNVAN", "FIRMA UNVANI", "FIRMA", "TEDARIKCI", "SATICI",
        "ALICI UNVANI", "CARI", "CARİ", "MUSTERI",
    ],
}


def _norm_baslik(deger):
    if deger is None:
        return ""
    metin = str(deger).upper()
    tr = {"İ": "I", "Ğ": "G", "Ü": "U", "Ş": "S", "Ö": "O", "Ç": "C", "I": "I"}
    for k, v in tr.items():
        metin = metin.replace(k, v)
    parcalar = []
    for c in metin:
        if c.isalnum():
            parcalar.append(c)
        else:
            parcalar.append(" ")
    return " ".join("".join(parcalar).split())


def _kolon_bul(basliklar, alan):
    for i, h in enumerate(basliklar):
        n = _norm_baslik(h)
        if not n or len(n) < 2:
            continue
        for sinonim in KOLON_SINONIMLERI[alan]:
            s = _norm_baslik(sinonim)
            if s in n or n in s:
                return i
    return None


def _spreadsheetml_satirlar(dosya_yolu):
    """Excel 2003 XML (SpreadsheetML) biçimini satır listesine çevirir.

    ZENOM gibi bazı programlar .xls uzantıyla bu biçimi dışa aktarır;
    xlrd/openpyxl bu dosyaları açamaz. Sayı tipindeki hücreler doğrudan
    Decimal'e çevrilir (binlik/ondalık karışıklığı olmasın).
    """
    import xml.etree.ElementTree as ET
    ns = "{urn:schemas-microsoft-com:office:spreadsheet}"
    agac = ET.parse(dosya_yolu)
    kok = agac.getroot()
    tumu = []
    for tablo in kok.iter(ns + "Table"):
        for satir in tablo.iter(ns + "Row"):
            hucreler = []
            for hucre in satir.findall(ns + "Cell"):
                idx = hucre.get(ns + "Index")
                try:
                    hedef = int(idx) - 1 if idx else len(hucreler)
                except (TypeError, ValueError):
                    hedef = len(hucreler)
                while len(hucreler) < hedef:
                    hucreler.append(None)
                veri = hucre.find(ns + "Data")
                deger = None
                if veri is not None and veri.text is not None:
                    metin = str(veri.text).strip()
                    if metin:
                        if veri.get(ns + "Type") == "Number":
                            try:
                                deger = Decimal(metin.replace(",", ""))
                            except Exception:
                                deger = metin
                        else:
                            deger = metin
                hucreler.append(deger)
            tumu.append(hucreler)
    return tumu


def excel_satirlar(dosya_yolu):
    try:
        with open(dosya_yolu, "rb") as fh:
            bas = fh.read(2048)
    except OSError:
        bas = b""
    if bas.lstrip().startswith(b"<?xml") and (
            b"SpreadsheetML" in bas or b"office:spreadsheet" in bas):
        return _spreadsheetml_satirlar(dosya_yolu)
    if dosya_yolu.lower().endswith(".xls"):
        import xlrd
        wb = xlrd.open_workbook(dosya_yolu)
        ws = wb.sheet_by_index(0)
        satirlar = [list(ws.row_values(i)) for i in range(ws.nrows)]
        wb.release_resources()
        return satirlar
    import openpyxl
    wb = openpyxl.load_workbook(dosya_yolu, data_only=True)
    ws = wb.active
    satirlar = []
    for satir in ws.iter_rows(values_only=True):
        satirlar.append(list(satir))
    wb.close()
    return satirlar


def _excel_seri_tarih(deger):
    try:
        from datetime import timedelta
        sayi = float(deger)
    except Exception:
        return None
    if not (20000 <= sayi <= 80000):
        return None
    try:
        from datetime import datetime
        return (datetime(1899, 12, 30) + timedelta(days=sayi)).strftime("%Y-%m-%d")
    except Exception:
        return None


def _huc_re(deger):
    if deger is None:
        return None
    if isinstance(deger, (datetime, date)):
        return deger.strftime("%Y-%m-%d")
    return deger


def _huc_tutar(deger):
    if deger is None:
        return None
    if isinstance(deger, (int, float)):
        return tutar_parse(str(deger))
    return tutar_parse(deger)


def _gelen_tutar(deger):
    """Gelen faturalar formatındaki sayı hücresini 2 ondalıklı tutara çevirir.

    Excel bu hücreleri sayı olarak tutar; KDV TUTAR hücreleri matrah*oran
    sonucu 3 ondalıklı float olabilir (örn. 578.612). tutar_parse bunu
    nokta=binlik sanıp 578612 yapar, bu yüzden float için direkt Decimal.
    """
    if deger is None:
        return None
    if isinstance(deger, (int, float)):
        try:
            d = Decimal(str(deger))
            if d.is_finite():
                return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except Exception:
            pass
    return tutar_parse(deger)


def _baslik_satiri_bul(satirlar):
    for i, satir in enumerate(satirlar):
        eşleşme = 0
        for alan in ("belge_no", "vkn", "matrah", "kdv", "tarih"):
            if _kolon_bul(satir, alan) is not None:
                eşleşme += 1
        if eşleşme >= 2:
            return i
    return None


def _satir_veri(satir, kolonlar, kayit, harita):
    for alan, (hedef_alan, tur) in harita.items():
        idx = kolonlar.get(alan)
        if idx is None or idx >= len(satir):
            continue
        deger = satir[idx]
        if deger is None:
            continue
        if tur == "tarih":
            t = _huc_re(deger)
            if isinstance(t, str):
                kayit[hedef_alan] = tarih_parse(t)
            elif isinstance(deger, (int, float)):
                kayit[hedef_alan] = _excel_seri_tarih(deger)
        elif tur == "tutar":
            kayit[hedef_alan] = _huc_tutar(deger)
        elif tur == "vkn":
            kayit[hedef_alan] = vkn_temizle(deger)
        elif tur == "belge":
            kayit[hedef_alan] = fatura_no_temizle(deger)
        else:
            kayit[hedef_alan] = str(deger).strip()


def _toplam_satiri_mi(satir, kolonlar):
    for deger in satir:
        if deger is None:
            continue
        n = _norm_baslik(deger)
        if n in ("TOPLAM", "GENEL TOPLAM", "ARA TOPLAM", "GENELTOPLAM"):
            return True
    return False


def _kolon_haritasi(satirlar, baslik_i):
    baslik = satirlar[baslik_i]
    kolonlar = {}
    for alan in KOLON_SINONIMLERI:
        idx = _kolon_bul(baslik, alan)
        if idx is not None:
            kolonlar[alan] = idx
    return kolonlar


def fatura_excel_parse(dosya_yolu):
    satirlar = excel_satirlar(dosya_yolu)
    baslik_i = _baslik_satiri_bul(satirlar)
    sonuc = []
    if baslik_i is None:
        return [{
            "dosya": dosya_yolu, "tip": "excel", "satir": 1,
            "belge_no": None, "tarih": None, "satici_vkn": None, "alici_vkn": None,
            "matrah": None, "kdv": None, "toplam": None, "oranlar": [], "notlar": [],
            "unvan": None,
        }]
    kolonlar = _kolon_haritasi(satirlar, baslik_i)
    for i in range(baslik_i + 1, len(satirlar)):
        satir = satirlar[i]
        if not any(c is not None and str(c).strip() for c in satir):
            continue
        if _toplam_satiri_mi(satir, kolonlar):
            continue
        kayit = {
            "dosya": dosya_yolu, "tip": "excel", "satir": i + 1,
            "belge_no": None, "tarih": None, "satici_vkn": None, "alici_vkn": None,
            "matrah": None, "kdv": None, "toplam": None, "oranlar": [], "notlar": [],
            "unvan": None, "oran": None,
        }
        _satir_veri(satir, kolonlar, kayit, {
            "belge_no": ("belge_no", "belge"), "tarih": ("tarih", "tarih"),
            "vkn": ("satici_vkn", "vkn"), "matrah": ("matrah", "tutar"),
            "kdv": ("kdv", "tutar"), "toplam": ("toplam", "tutar"),
            "oran": ("oran", "tutar"), "unvan": ("unvan", "metin"),
        })
        if not kayit["belge_no"] and not kayit["satici_vkn"] and kayit["matrah"] is None:
            continue
        oran_deger = kayit["oran"]
        if oran_deger is not None:
            try:
                kayit["oranlar"] = [int(oran_deger)]
            except (TypeError, ValueError):
                o = tutar_parse(oran_deger)
                if o is not None:
                    kayit["oranlar"] = [int(o)]
        if kayit["matrah"] is None or kayit["kdv"] is None:
            kayit["notlar"].append("Matrah/KDV bulunamadı, manuel kontrol edin")
        elif kayit["toplam"] is not None and abs(kayit["matrah"] + kayit["kdv"] - kayit["toplam"]) > 0.02:
            kayit["notlar"].append("Matrah+KDV ≠ Toplam")
        sonuc.append(kayit)
    if not sonuc:
        sonuc.append({
            "dosya": dosya_yolu, "tip": "excel", "satir": 1,
            "belge_no": None, "tarih": None, "satici_vkn": None, "alici_vkn": None,
            "matrah": None, "kdv": None, "toplam": None, "oranlar": [],
            "notlar": ["Excel'de veri satırı bulunamadı (başlık satırı tanınamadı)"], "unvan": None,
        })
    return sonuc


def fatura_gib_arsiv_liste_parse(dosya_yolu):
    """GİB e-Arşiv portalı 'Excel'e Aktar' liste çıktısı.

    Başlıklar: Sıra | Ünvanı/Adı Soyadı | Vergi Kimlik/T.C. Kimlik Numarası |
    Fatura No | Düzenleme Tarihi | Toplam Tutar | Ödenecek Tutar |
    Vergiler Toplamı | Para Birimi | ... (DVD 'e-Arşiv Faturalarım' ve
    earsivportal liste dışa aktarımları). Her satır bir faturadır.
    Toplam Tutar = KDV hariç matrah, Ödenecek Tutar = genel toplam,
    Vergiler Toplamı = KDV.

    Format tanınmazsa None döner.
    """
    satirlar = excel_satirlar(dosya_yolu)
    baslik_i = None
    kolon = {}
    for i, satir in enumerate(satirlar):
        normlar = [_norm_baslik(c) for c in satir]
        if ("FATURA NO" in normlar and "VERGILER TOPLAMI" in normlar
                and any(n.startswith("DUZENLEME TARIHI") for n in normlar)):
            baslik_i = i
            for j, n in enumerate(normlar):
                if not n:
                    continue
                if n == "FATURA NO":
                    kolon["belge"] = j
                elif n.startswith("DUZENLEME TARIHI"):
                    kolon["tarih"] = j
                elif n.startswith("UNVANI"):
                    kolon["unvan"] = j
                elif n.startswith("VERGI KIMLIK"):
                    kolon["vkn"] = j
                elif n == "TOPLAM TUTAR":
                    kolon["matrah"] = j
                elif n == "ODENECEK TUTAR":
                    kolon["toplam"] = j
                elif n == "VERGILER TOPLAMI":
                    kolon["kdv"] = j
                elif n == "PARA BIRIMI":
                    kolon["para"] = j
            break
    if baslik_i is None:
        return None

    sonuc = []
    for i in range(baslik_i + 1, len(satirlar)):
        satir = satirlar[i]
        if not any(c is not None and str(c).strip() for c in satir):
            continue
        belge_ham = satir[kolon["belge"]] if kolon["belge"] < len(satir) else None
        if belge_ham is None or not str(belge_ham).strip():
            continue
        kayit = {
            "dosya": dosya_yolu, "tip": "excel", "satir": i + 1,
            "belge_no": fatura_no_temizle(str(belge_ham)),
            "tarih": None, "satici_vkn": None, "alici_vkn": None,
            "matrah": None, "kdv": None, "toplam": None,
            "oranlar": [], "notlar": [], "unvan": None, "oran": None,
        }
        if "tarih" in kolon and kolon["tarih"] < len(satir):
            tv = satir[kolon["tarih"]]
            if tv is not None:
                t = tarih_parse(str(tv).strip()) or _excel_seri_tarih(tv)
                kayit["tarih"] = str(t) if t else None
        if "vkn" in kolon and kolon["vkn"] < len(satir):
            kayit["satici_vkn"] = vkn_temizle(str(satir[kolon["vkn"]] or ""))
        if "unvan" in kolon and kolon["unvan"] < len(satir):
            kayit["unvan"] = str(satir[kolon["unvan"]] or "").strip()[:80] or None
        for alan in ("matrah", "kdv", "toplam"):
            if alan in kolon and kolon[alan] < len(satir):
                kayit[alan] = tutar_parse(satir[kolon[alan]])
        para = None
        if "para" in kolon and kolon["para"] < len(satir):
            para = str(satir[kolon["para"]] or "").strip().upper()
        if para and para not in ("TRY", "TL"):
            kayit["notlar"].append(f"Para birimi TRY değil: {para}")
        if kayit["matrah"] is None or kayit["kdv"] is None:
            kayit["notlar"].append("Matrah/KDV bulunamadı, manuel kontrol edin")
        elif kayit["toplam"] is not None \
                and abs(kayit["matrah"] + kayit["kdv"] - kayit["toplam"]) > Decimal("0.02"):
            kayit["notlar"].append("Matrah+KDV ≠ Toplam")
        elif kayit["matrah"] > 0:
            oran = (kayit["kdv"] / kayit["matrah"] * 100).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP)
            tahmini = kayit["matrah"] * oran / 100
            if abs(tahmini - kayit["kdv"]) <= Decimal("0.02") and 0 < oran <= 100:
                kayit["oranlar"] = [int(oran)]
        sonuc.append(kayit)
    if not sonuc:
        return None
    return sonuc


def fatura_luca_ozet_parse(dosya_yolu):
    """Luca Akıllı Entegrasyon özet tablosu (cek_luca_belgeleri çıktısı).

    Başlıklar: Belge No | Tarih | Tür | VKN/TCKN | Unvan | Durum |
    Matrah | KDV | Genel Toplam | KDV Oranlar | Para | ETTN | ZIP.
    'KDV Oranlar' hücresi '20%:500.00/100.00; 1%:...' biçiminde çok
    oranlı kırılımı taşır. Format tanınmazsa None döner.
    """
    satirlar = excel_satirlar(dosya_yolu)
    baslik_i = None
    kolon = {}
    for i, satir in enumerate(satirlar):
        normlar = [_norm_baslik(c) for c in satir]
        if "BELGE NO" in normlar and "GENEL TOPLAM" in normlar \
                and ("ETTN" in normlar or "KDV ORANLAR" in normlar):
            baslik_i = i
            for j, n in enumerate(normlar):
                if n == "BELGE NO":
                    kolon["belge"] = j
                elif n == "TARIH":
                    kolon["tarih"] = j
                elif n == "TUR":
                    kolon["tur"] = j
                elif n.startswith("VKN"):
                    kolon["vkn"] = j
                elif n.startswith("UNVAN"):
                    kolon["unvan"] = j
                elif n == "DURUM":
                    kolon["durum"] = j
                elif n == "MATRAH":
                    kolon["matrah"] = j
                elif n == "KDV":
                    kolon["kdv"] = j
                elif n == "GENEL TOPLAM":
                    kolon["toplam"] = j
                elif n == "KDV ORANLAR":
                    kolon["oranlar"] = j
                elif n == "PARA":
                    kolon["para"] = j
            break
    if baslik_i is None:
        return None

    oran_parca = re.compile(
        r"(\d+(?:[.,]\d+)?)\s*%\s*:\s*(-?[\d.]+)\s*/\s*(-?[\d.]+)")
    sonuc = []
    for i in range(baslik_i + 1, len(satirlar)):
        satir = satirlar[i]
        if not any(c is not None and str(c).strip() for c in satir):
            continue
        belge_ham = satir[kolon["belge"]] \
            if kolon.get("belge") is not None and kolon["belge"] < len(satir) \
            else None
        if belge_ham is None or not str(belge_ham).strip():
            continue

        def hucre(anahtar):
            j = kolon.get(anahtar)
            if j is None or j >= len(satir):
                return None
            return satir[j]

        durum_metni = str(hucre("durum") or "").strip()
        durum_kucuk = (durum_metni.replace("İ", "i").replace("I", "i")
                       .replace("ı", "i").lower())
        if (durum_kucuk and "onay" not in durum_kucuk) or \
                "red" in durum_kucuk or "iptal" in durum_kucuk:
            continue

        tarih_deger = hucre("tarih")
        t = tarih_parse(str(tarih_deger).strip()) if tarih_deger else None
        kayit = {
            "dosya": dosya_yolu, "tip": "excel", "satir": i + 1,
            "belge_no": fatura_no_temizle(str(belge_ham)),
            "tarih": str(t) if t else None,
            "satici_vkn": vkn_temizle(str(hucre("vkn") or "")),
            "alici_vkn": None,
            "matrah": tutar_parse(hucre("matrah")),
            "kdv": tutar_parse(hucre("kdv")),
            "toplam": tutar_parse(hucre("toplam")),
            "oranlar": [], "notlar": [],
            "unvan": str(hucre("unvan") or "").strip()[:80] or None,
            "oran": None,
            "oran_kalemleri": [],
        }
        # oran_kalemleri: uygulama genelindeki oranlar=[18, 8] listesinden
        # farkli, Luca ozetinde oran bazina acilmis {"oran", "matrah",
        # "kdv"} sozlukleridir.
        oran_ham = str(hucre("oranlar") or "")
        for eslesme in oran_parca.finditer(oran_ham):
            yuzde = float(eslesme.group(1).replace(",", "."))
            kayit["oran_kalemleri"].append({
                "oran": round(yuzde, 2),
                "matrah": round(float(eslesme.group(2)), 2),
                "kdv": round(float(eslesme.group(3)), 2)})
        para = str(hucre("para") or "").strip().upper()
        if para and para not in ("TRY", "TL"):
            kayit["notlar"].append(f"Para birimi TRY değil: {para}")
        if kayit["matrah"] is None or kayit["kdv"] is None:
            kayit["notlar"].append(
                "Matrah/KDV bulunamadı, manuel kontrol edin")
        elif kayit["toplam"] is not None \
                and abs(kayit["matrah"] + kayit["kdv"]
                        - kayit["toplam"]) > Decimal("0.02"):
            kayit["notlar"].append("Matrah+KDV ≠ Toplam")
        # Luca özet tablosunda satıcı unvanı 'unvan' kolonunda gelir;
        # matcher ve raporlar 'satici_unvan' beklediği için eşle.
        kayit["satici_unvan"] = kayit.get("unvan")
        sonuc.append(kayit)
    if not sonuc:
        return None
    return sonuc


def fatura_gelen_parse(dosya_yolu):
    """Gelen faturalar Excel formatı (e-fatura portalinden indirilen gönderici faturaları listesi).

    Başlıklar: FATURA TARİHİ, FATURA NUMARASI, FATURA TÜRÜ, GÖNDERİCİ UNVANI,
    GÖNDERİCİ VKN, ÖDENECEK TUTAR, TOPLAM KDV %1 MATRAH/TUTAR, %10, %20.
    Her satır bir faturadır. Matrah = KDV matrah kolonları toplamı,
    KDV = KDV tutar kolonları toplamı.

    Format tanınmazsa None döner.
    """
    satirlar = excel_satirlar(dosya_yolu)
    baslik_i = None
    kolon = {}
    for i, satir in enumerate(satirlar):
        normlar = [_norm_baslik(c) for c in satir]
        if ("FATURA NUMARASI" in normlar and "GONDERICI VKN" in normlar
                and any(n.startswith("TOPLAM KDV") and n.endswith("MATRAH") for n in normlar)):
            baslik_i = i
            kolon = {
                "tarih": normlar.index("FATURA TARIHI") if "FATURA TARIHI" in normlar else None,
                "belge": normlar.index("FATURA NUMARASI"),
                "unvan": normlar.index("GONDERICI UNVANI") if "GONDERICI UNVANI" in normlar else None,
                "vkn": normlar.index("GONDERICI VKN"),
                "toplam": normlar.index("ODENECEK TUTAR") if "ODENECEK TUTAR" in normlar else None,
            }
            for oran in ("1", "10", "20"):
                matrah_h = f"TOPLAM KDV {oran} MATRAH"
                tutar_h = f"TOPLAM KDV {oran} TUTAR"
                if matrah_h in normlar and tutar_h in normlar:
                    kolon[f"matrah_{oran}"] = normlar.index(matrah_h)
                    kolon[f"kdv_{oran}"] = normlar.index(tutar_h)
            break
    if baslik_i is None:
        return None

    sonuc = []
    for i in range(baslik_i + 1, len(satirlar)):
        satir = satirlar[i]
        if not any(c is not None and str(c).strip() for c in satir):
            continue
        belge_ham = satir[kolon["belge"]] if kolon["belge"] < len(satir) else None
        if belge_ham is None or not str(belge_ham).strip():
            continue
        kayit = {
            "dosya": dosya_yolu, "tip": "excel", "satir": i + 1,
            "belge_no": fatura_no_temizle(str(belge_ham)),
            "tarih": None, "satici_vkn": None, "alici_vkn": None,
            "matrah": None, "kdv": None, "toplam": None,
            "oranlar": [], "notlar": [], "unvan": None,
        }
        if kolon["tarih"] is not None and kolon["tarih"] < len(satir):
            tv = satir[kolon["tarih"]]
            if tv is not None:
                t = tarih_parse(str(tv).strip()) or _excel_seri_tarih(tv)
                kayit["tarih"] = str(t) if t else None
        if kolon["vkn"] < len(satir):
            kayit["satici_vkn"] = vkn_temizle(str(satir[kolon["vkn"]] or ""))
        if kolon["unvan"] is not None and kolon["unvan"] < len(satir):
            kayit["unvan"] = str(satir[kolon["unvan"]] or "").strip()[:80] or None
        if kolon["toplam"] is not None and kolon["toplam"] < len(satir):
            kayit["toplam"] = _gelen_tutar(satir[kolon["toplam"]])

        matrah = Decimal("0")
        kdv = Decimal("0")
        oranlar = []
        for oran in ("1", "10", "20"):
            mkey = f"matrah_{oran}"
            kkey = f"kdv_{oran}"
            if mkey not in kolon or kkey not in kolon:
                continue
            m = _gelen_tutar(satir[kolon[mkey]]) if kolon[mkey] < len(satir) else None
            k = _gelen_tutar(satir[kolon[kkey]]) if kolon[kkey] < len(satir) else None
            if m is not None and k is not None:
                matrah += m
                kdv += k
                if m:
                    oranlar.append(int(oran))
        kayit["matrah"] = matrah if oranlar else None
        kayit["kdv"] = kdv if oranlar else None
        kayit["oranlar"] = oranlar

        if kayit["matrah"] is None or kayit["kdv"] is None:
            kayit["notlar"].append("Matrah/KDV bulunamadı, manuel kontrol edin")
        elif kayit["toplam"] is not None and abs(kayit["matrah"] + kayit["kdv"] - kayit["toplam"]) > 0.02:
            kayit["notlar"].append("Matrah+KDV ≠ Toplam")
        sonuc.append(kayit)

    if not sonuc:
        sonuc.append({
            "dosya": dosya_yolu, "tip": "excel", "satir": 1,
            "belge_no": None, "tarih": None, "satici_vkn": None, "alici_vkn": None,
            "matrah": None, "kdv": None, "toplam": None, "oranlar": [],
            "notlar": ["Excel'de veri satırı bulunamadı (gelen faturalar formatı)"], "unvan": None,
        })
    return sonuc


def cetvel_excel_parse(dosya_yolu):
    satirlar = excel_satirlar(dosya_yolu)
    baslik_i = _baslik_satiri_bul(satirlar)
    sonuc = {"dosya": dosya_yolu, "kayitlar": [], "notlar": []}
    if baslik_i is None:
        sonuc["notlar"].append("Excel başlık satırı tanınamadı (VKN/Fatura No/Matrah/KDV sütunları aranıyor)")
        return sonuc
    kolonlar = _kolon_haritasi(satirlar, baslik_i)
    for i in range(baslik_i + 1, len(satirlar)):
        satir = satirlar[i]
        if not any(c is not None and str(c).strip() for c in satir):
            continue
        if _toplam_satiri_mi(satir, kolonlar):
            continue
        kayit = {
            "vkn": None, "belge_no": None, "tarih": None,
            "matrah": None, "kdv": None, "unvan": None, "notlar": [],
        }
        _satir_veri(satir, kolonlar, kayit, {
            "belge_no": ("belge_no", "belge"), "tarih": ("tarih", "tarih"),
            "vkn": ("vkn", "vkn"), "matrah": ("matrah", "tutar"),
            "kdv": ("kdv", "tutar"), "unvan": ("unvan", "metin"),
        })
        if not kayit["vkn"] and not kayit["belge_no"] and kayit["matrah"] is None:
            continue
        if kayit["vkn"] is None:
            kayit["notlar"].append("VKN bulunamadı")
        sonuc["kayitlar"].append(kayit)
    if not sonuc["kayitlar"]:
        sonuc["notlar"].append("Excel'de veri satırı bulunamadı")
    return sonuc


def _muavin_baslik_indexleri(satirlar):
    for i, satir in enumerate(satirlar):
        normlar = [_norm_baslik(c) for c in satir]
        if "TARIH" in normlar and "ACIKLAMA" in normlar and ("BORC" in normlar or "BORC" in normlar):
            if "FIS NO" in normlar or "TUP" in normlar:
                return i, {
                    "tarih": normlar.index("TARIH"),
                    "aciklama": normlar.index("ACIKLAMA"),
                    "borc": normlar.index("BORC"),
                    "alacak": normlar.index("ALACAK") if "ALACAK" in normlar else None,
                }
    return None, None


def muavin_excel_parse(dosya_yolu):
    satirlar = excel_satirlar(dosya_yolu)
    sonuc = {"dosya": dosya_yolu, "kayitlar": [], "notlar": []}
    baslik_i, kolonlar = _muavin_baslik_indexleri(satirlar)
    if baslik_i is None:
        sonuc["notlar"].append("Muavin formu tanınamadı (TARİH/TÜP/FİŞ NO/AÇIKLAMA/BORÇ sütunları aranıyor)")
        return sonuc
    aktif_hesap = ""
    import re as _re
    for i, satir in enumerate(satirlar):
        if not any(c is not None and str(c).strip() for c in satir):
            continue
        ilk_ham = str(satir[0]).strip() if satir and satir[0] is not None else ""
        if _re.match(r"^\d{3}\.\d{1,2}\.\d{1,3}", ilk_ham):
            aktif_hesap = ilk_ham
            continue
        if i < baslik_i:
            continue
        if not ("KDV" in aktif_hesap.upper() or "INDIRILECEK" in aktif_hesap.upper() or "HESAPLANAN" in aktif_hesap.upper()):
            continue
        if "TARIH" in [_norm_baslik(c) for c in satir] and "ACIKLAMA" in [_norm_baslik(c) for c in satir]:
            continue
        a_idx = kolonlar["aciklama"]
        if a_idx is None or a_idx >= len(satir):
            continue
        aciklama = satir[a_idx]
        if aciklama is None:
            continue
        aciklama = str(aciklama).strip()
        if not aciklama or not aciklama[0].isdigit():
            continue
        if "Yekun" in aciklama or "TOPLAM" in _norm_baslik(aciklama):
            continue
        import re as _re2
        m = _re2.search(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})\s*-\s*([A-Za-z0-9]+)", aciklama)
        if not m:
            continue
        gun, ay, yil = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if ay < 1 or ay > 12 or gun < 1 or gun > 31:
            continue
        tarih = f"{yil:04d}-{ay:02d}-{gun:02d}"
        belge = fatura_no_temizle(m.group(4))
        kalan = aciklama[m.end():].strip(" -")
        borc = tutar_parse(satir[kolonlar["borc"]]) if kolonlar["borc"] is not None and kolonlar["borc"] < len(satir) else None
        alacak = tutar_parse(satir[kolonlar["alacak"]]) if kolonlar["alacak"] is not None and kolonlar["alacak"] < len(satir) else None
        kdv = borc if borc else alacak
        kayit = {
            "vkn": "", "belge_no": belge, "tarih": tarih,
            "matrah": None, "kdv": kdv, "unvan": kalan[:80],
            "notlar": [f"Hesap: {aktif_hesap}"] if aktif_hesap else [],
        }
        sonuc["kayitlar"].append(kayit)
    sonuc["kayitlar"] = _muavin_birlestir(sonuc["kayitlar"])
    if not sonuc["kayitlar"]:
        sonuc["notlar"].append("Muavin'de fatura satırı bulunamadı (Tarih-Belge No-Açıklama formatı aranıyor)")
    else:
        sonuc["notlar"].append("Muavin formu olarak okundu")
    return sonuc


def muavin_191_parse(dosya_yolu):
    """KDV 191 hesap (alım fatura) defteri okur (örn. 19112356.xlsx veya 191.xlsx).

    İki varyant desteklenir:
      - eski: 'Hesap Kodu 191 01 001' başlığı altında
              TARİH / FİŞ TİP / BELGE NO / İSL. KOD / AÇIKLAMA / DETAY NO /
              KATEGORİ DETAYI / BORÇ BEDELİ / ALACAK BEDELİ sütunları.
      - yeni (391 ile aynı): 'Hesap Kodu 191-xx-xxx' başlığı altında
              TARİH / FİŞ NO / SR / AÇIKLAMA / BORÇ TUT. / ALACAK TUT. /
              REFERANS KODU / REFERANS İSMİ / İŞLEM TİPİ sütunları,
              açıklama '...FT.NIZ NO:XXXX KDVSI' içerir, KDV Borç kolonundadır.

    Dönen kayıt (capraz_kontrol cetvel format): {vkn, belge_no, tarih,
    matrah, kdv, unvan, notlar}
    """
    import re as _re

    satirlar = excel_satirlar(dosya_yolu)
    sonuc = {"dosya": dosya_yolu, "kayitlar": [], "notlar": []}

    baslik_i = None
    kolonlar = None
    yeni_format = False
    for i, satir in enumerate(satirlar):
        normlar = [_norm_baslik(c) for c in satir]
        if "TARIH" in normlar and "DETAY NO" in normlar and "BORC BEDELI" in normlar:
            baslik_i = i
            kolonlar = {
                "tarih": normlar.index("TARIH"),
                "detay": normlar.index("DETAY NO"),
                "borc": normlar.index("BORC BEDELI"),
                "alacak": normlar.index("ALACAK BEDELI") if "ALACAK BEDELI" in normlar else None,
                "aciklama": normlar.index("ACIKLAMA") if "ACIKLAMA" in normlar else None,
            }
            break
        if "TARIH" in normlar and "FIS NO" in normlar \
                and "ACIKLAMA" in normlar and "BORC TUT" in normlar and "ALACAK TUT" in normlar:
            baslik_i = i
            yeni_format = True
            kolonlar = {
                "tarih": normlar.index("TARIH"),
                "fis": normlar.index("FIS NO"),
                "aciklama": normlar.index("ACIKLAMA"),
                "borc": normlar.index("BORC TUT"),
                "alacak": normlar.index("ALACAK TUT"),
            }
            break
    if baslik_i is None:
        sonuc["notlar"].append("191 hesap defteri tanınamadı (TARİH/DETAY NO/BORÇ BEDELİ veya TARİH/FİŞ NO/BORÇ TUT./ALACAK TUT. sütunları aranıyor)")
        return sonuc

    aktif_hesap = ""
    for i in range(len(satirlar)):
        satir = satirlar[i]
        if not any(c is not None and str(c).strip() for c in satir):
            continue
        normlar = [_norm_baslik(c) for c in satir]
        if i < baslik_i:
            ilk = str(satir[0] or "").strip() if satir else ""
            if _re.match(r"^19\d-", ilk):
                aktif_hesap = ilk
            continue
        if i == baslik_i:
            continue
        if "HESAP KODU" in normlar[0]:
            continue
        if "TARIH" in normlar and "BORC BEDELI" in normlar:
            continue
        if "TARIH" in normlar and "FIS NO" in normlar:
            continue
        if yeni_format:
            ilk = str(satir[0] or "").strip() if satir and satir[0] is not None else ""
            if _re.match(r"^19\d-", ilk):
                aktif_hesap = ilk
                continue
            if not aktif_hesap.startswith("191"):
                continue
            aciklama_txt = str(satir[kolonlar["aciklama"]] or "").strip() if kolonlar["aciklama"] < len(satir) else ""
            if any(k in aciklama_txt.upper() for k in ("TOPLAM", "GENEL TOPLAM", "BAKIYE", "YEKUN")):
                continue
            if not _re.match(r"^\d{1,2}[./]\d{1,2}[./]\d{4}", ilk):
                continue
            tarih = tarih_parse(ilk)
            borc = (tutar_parse(satir[kolonlar["borc"]])
                    if kolonlar["borc"] < len(satir) else None)
            alacak = (tutar_parse(satir[kolonlar["alacak"]])
                      if kolonlar["alacak"] < len(satir) else None)
            kdv = borc if borc is not None and borc else alacak
            if kdv is None:
                continue
            m = _re.search(r"FT\.?\s*[NM]IZ\s*NO\s*[:#]?\s*([A-Za-z0-9\-/]+)", aciklama_txt)
            if m:
                belge = fatura_no_temizle(m.group(1))
            else:
                kalan = _re.findall(r"[A-Z][A-Z0-9]{2}\d{4}\d{4,}", aciklama_txt.upper())
                belge = fatura_no_temizle(kalan[-1]) if kalan else None
            if not belge:
                continue
            unvan = aciklama_txt.split("FT.")[0].strip(" .")[:80]
            kayit = {
                "vkn": "", "belge_no": belge, "tarih": str(tarih) if tarih else None,
                "matrah": None, "kdv": kdv, "unvan": unvan,
                "notlar": [f"Hesap: {aktif_hesap}"] if aktif_hesap else [],
            }
            sonuc["kayitlar"].append(kayit)
            continue
        tarih = satir[kolonlar["tarih"]] if kolonlar["tarih"] < len(satir) else None
        tarih_str = None
        if tarih is not None:
            ts = tarih_parse(str(tarih).strip())
            if ts:
                tarih_str = str(ts)
            else:
                from excel_oku import _excel_seri_tarih
                tarih_str = _excel_seri_tarih(tarih) if isinstance(tarih, (int, float)) else None
        belge_raw = satir[kolonlar["detay"]] if kolonlar["detay"] < len(satir) else None
        if belge_raw is None:
            continue
        belge = str(belge_raw).strip()
        if not belge:
            continue
        borc = (tutar_parse(satir[kolonlar["borc"]])
                if kolonlar["borc"] is not None and kolonlar["borc"] < len(satir) else None)
        alacak = (tutar_parse(satir[kolonlar["alacak"]])
                  if kolonlar["alacak"] is not None and kolonlar["alacak"] < len(satir) else None)
        if borc is None and alacak is None:
            continue
        kdv = borc if borc is not None else alacak
        unvan = ""
        if kolonlar["aciklama"] is not None and kolonlar["aciklama"] < len(satir):
            unvan = str(satir[kolonlar["aciklama"]] or "").strip()[:80]
        kayit = {
            "vkn": "", "belge_no": fatura_no_temizle(belge),
            "tarih": tarih_str, "matrah": None, "kdv": kdv,
            "unvan": unvan, "notlar": [],
        }
        sonuc["kayitlar"].append(kayit)
    sonuc["kayitlar"] = _muavin_birlestir(sonuc["kayitlar"])
    if not sonuc["kayitlar"]:
        sonuc["notlar"].append("191 hesap'de fatura satırı bulunamadı")
    else:
        sonuc["notlar"].append("KDV 191 hesap listesi olarak okundu")
    return sonuc


def muavin_391_parse(dosya_yolu):
    """KDV 391 hesap (satış fatura) defteri okur (örn. 391.xlsx).

    Format: her hesap grubu 'Hesap Kodu 391-xx-xxx' başlığı altında
    TARİH / FİŞ NO / SR / AÇIKLAMA / BORÇ TUT. / ALACAK TUT. /
    REFERANS KODU / REFERANS İSMİ / İŞLEM TİPİ sütunları.
    Açıklama '...FT.MIZ NO:XXXX KDVSI' biçiminde belge numarası içerir,
    KDV tutarı Alacak kolonundadır. Toplam/Genel Toplam/Bakiye satırları
    atlanır.

    Dönen kayıt (capraz_kontrol cetvel format): {vkn, belge_no, tarih,
    matrah, kdv, unvan, notlar}
    """
    import re as _re

    satirlar = excel_satirlar(dosya_yolu)
    sonuc = {"dosya": dosya_yolu, "kayitlar": [], "notlar": []}

    baslik_i = None
    kolonlar = None
    for i, satir in enumerate(satirlar):
        normlar = [_norm_baslik(c) for c in satir]
        if "TARIH" in normlar and "FIS NO" in normlar and "ACIKLAMA" in normlar \
                and "BORC TUT" in normlar and "ALACAK TUT" in normlar:
            baslik_i = i
            kolonlar = {
                "tarih": normlar.index("TARIH"),
                "fis": normlar.index("FIS NO"),
                "aciklama": normlar.index("ACIKLAMA"),
                "borc": normlar.index("BORC TUT"),
                "alacak": normlar.index("ALACAK TUT"),
            }
            break
    if baslik_i is None:
        sonuc["notlar"].append("391 hesap defteri tanınamadı (TARİH/FİŞ NO/AÇIKLAMA/BORÇ TUT./ALACAK TUT. sütunları aranıyor)")
        return sonuc

    aktif_hesap = ""
    for i, satir in enumerate(satirlar):
        if not any(c is not None and str(c).strip() for c in satir):
            continue
        normlar = [_norm_baslik(c) for c in satir]
        if i < baslik_i:
            ilk = str(satir[0] or "").strip() if satir else ""
            if ilk.startswith("391"):
                aktif_hesap = ilk
            continue
        if "HESAP KODU" in normlar[0]:
            continue
        ilk = str(satir[0] or "").strip() if satir and satir[0] is not None else ""
        if ilk.startswith("391"):
            aktif_hesap = ilk
            continue
        if "TARIH" in normlar and "FIS NO" in normlar:
            continue
        ilk = str(satir[0] or "").strip() if satir and satir[0] is not None else ""
        if not aktif_hesap.startswith("391"):
            continue
        # Toplam satırları atla
        aciklama_txt = str(satir[kolonlar["aciklama"]] or "").strip() if kolonlar["aciklama"] < len(satir) else ""
        if any(k in aciklama_txt.upper() for k in ("TOPLAM", "GENEL TOPLAM", "BAKIYE", "YEKUN")):
            continue
        if not _re.match(r"^\d{1,2}[./]\d{1,2}[./]\d{4}", ilk):
            continue

        tarih = tarih_parse(ilk)
        alacak = (tutar_parse(satir[kolonlar["alacak"]])
                  if kolonlar["alacak"] < len(satir) else None)
        borc = (tutar_parse(satir[kolonlar["borc"]])
                if kolonlar["borc"] < len(satir) else None)
        kdv = alacak if alacak is not None and alacak else borc
        if kdv is None:
            continue

        m = _re.search(r"FT\.?\s*[NM]IZ\s*NO\s*[:#]?\s*([A-Za-z0-9\-/]+)", aciklama_txt)
        if m:
            belge = fatura_no_temizle(m.group(1))
        else:
            # FT.MIZ NO: yokta, e-fatura belge pattern (kod+yıl+araç) çek.
            # TTNET/telekom açıklamalar 'TELEKOM A.Ş.GN/1111/A112026000000301' biçimindedir.
            kalan = _re.findall(r"[A-Z][A-Z0-9]{2}\d{4}\d{4,}", aciklama_txt.upper())
            belge = fatura_no_temizle(kalan[-1]) if kalan else None
        if not belge:
            continue
        unvan = aciklama_txt.split("FT.")[0].strip(" .")[:80]
        kayit = {
            "vkn": "", "belge_no": belge, "tarih": str(tarih) if tarih else None,
            "matrah": None, "kdv": kdv, "unvan": unvan,
            "notlar": [f"Hesap: {aktif_hesap}"] if aktif_hesap else [],
        }
        sonuc["kayitlar"].append(kayit)

    sonuc["kayitlar"] = _muavin_birlestir(sonuc["kayitlar"])
    if not sonuc["kayitlar"]:
        sonuc["notlar"].append("391 hesap'de fatura satırı bulunamadı (FT.MIZ NO içeren açıklama aranıyor)")
    else:
        sonuc["notlar"].append("KDV 391 hesap listesi olarak okundu")
    return sonuc


def muavin_satis_parse(dosya_yolu):
    """Hesap başlıklı satış muavinini (ör. muavin_gokkusagi.xlsx) okur.

    Format: her hesap başlığı (örn. '600.00.001 SİGARA SATIŞ') altında
    TARİH / TİP / FİŞ NO / AÇIKLAMA / BORÇ / ALACAK sütunları,
    açıklamalar '01/07/2026-2126-Z RAPORU' biçimindedir.

    Dönen kayıt: {belge, tarih, hesap, hesap_adi, borc, alacak}
    """
    from decimal import Decimal

    satirlar = excel_satirlar(dosya_yolu)
    sonuc = {"dosya": dosya_yolu, "kayitlar": [], "notlar": []}

    baslik_i = None
    kolonlar = None
    for i, satir in enumerate(satirlar):
        normlar = [_norm_baslik(c) for c in satir]
        if "TARIH" in normlar and "ACIKLAMA" in normlar and "BORC" in normlar and "ALACAK" in normlar:
            baslik_i = i
            kolonlar = {
                "tarih": normlar.index("TARIH"),
                "aciklama": normlar.index("ACIKLAMA"),
                "borc": normlar.index("BORC"),
                "alacak": normlar.index("ALACAK"),
            }
            break
    if baslik_i is None:
        sonuc["notlar"].append("Satış muavini tanınamadı (TARİH/AÇIKLAMA/BORÇ/ALACAK sütunları aranıyor)")
        return sonuc

    import re as _re
    aktif_hesap = ""
    aktif_hesap_adi = ""
    for i in range(len(satirlar)):
        satir = satirlar[i]
        if not any(c is not None and str(c).strip() for c in satir):
            continue
        ilk_ham = str(satir[0]).strip() if satir and satir[0] is not None else ""
        hm = _re.match(r"^(\d{3}\.\d{1,2}\.\d{3})", ilk_ham)
        if hm:
            aktif_hesap = hm.group(1)
            aktif_hesap_adi = ilk_ham
            continue
        if i <= baslik_i or not aktif_hesap:
            continue
        a_idx = kolonlar["aciklama"]
        if a_idx is None or a_idx >= len(satir):
            continue
        aciklama = satir[a_idx]
        if aciklama is None:
            continue
        aciklama = str(aciklama).strip()
        m = _re.search(
            r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})\s*[-–]\s*([A-Za-z0-9]+)\s*[-–]\s*(?:Z RAPORU|E[AF]A)",
            aciklama.upper(),
        )
        if not m:
            continue
        gun, ay, yil = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if ay < 1 or ay > 12 or gun < 1 or gun > 31:
            continue
        token = m.group(4)
        if token.isdigit():
            belge = "Z" + token
        else:
            belge = fatura_no_temizle(token)
        tarih = f"{yil:04d}-{ay:02d}-{gun:02d}"
        borc = (tutar_parse(satir[kolonlar["borc"]])
                if kolonlar["borc"] is not None and kolonlar["borc"] < len(satir) else None)
        alacak = (tutar_parse(satir[kolonlar["alacak"]])
                  if kolonlar["alacak"] is not None and kolonlar["alacak"] < len(satir) else None)
        if borc is None and alacak is None:
            continue
        sonuc["kayitlar"].append({
            "belge": belge,
            "tarih": tarih,
            "hesap": aktif_hesap,
            "hesap_adi": aktif_hesap_adi,
            "borc": borc if borc is not None else Decimal("0"),
            "alacak": alacak if alacak is not None else Decimal("0"),
        })
    if not sonuc["kayitlar"]:
        sonuc["notlar"].append("Muavin'de belge satırı bulunamadı")
    else:
        sonuc["notlar"].append("Satış muavini olarak okundu")
    return sonuc


def muavin_zenom_parse(dosya_yolu):
    """Zenom 'MUAVİN RAPORU' çıktısını okur (.xls görünümlü SpreadsheetML).

    Sütunları: R.No | Tarih | Fiş Açıklaması | E.Trh | E.No | E.Açıklama |
    Borç | Alacak | Bakiye. Hesap başlıkları '391.01.001 - 1Lİ HESAPLANAN KDV'
    biçimindedir. E.No belge numarası, E.Açıklama firma unvanı, Borç KDV
    tutarıdır; Tarih iki haneli yıl içerebilir (01.07.26).
    """
    sonuc = {"dosya": dosya_yolu, "kayitlar": [], "notlar": []}
    satirlar = excel_satirlar(dosya_yolu)

    baslik_i = None
    kolonlar = {}
    for i, satir in enumerate(satirlar):
        normlar = [_norm_baslik(c) for c in satir]
        if ("E NO" in normlar and "TARIH" in normlar
                and "BORC" in normlar and "E ACIKLAMA" in normlar):
            baslik_i = i
            for ad, anahtar in (("R NO", "rno"), ("TARIH", "tarih"),
                                ("E TRH", "etarih"), ("E NO", "belge"),
                                ("E ACIKLAMA", "unvan"), ("BORC", "borc"),
                                ("ALACAK", "alacak")):
                kolonlar[anahtar] = normlar.index(ad) if ad in normlar else None
            break
    if baslik_i is None:
        sonuc["notlar"].append("Zenom muavin başlığı yok (R.No/Tarih/E.No/E.Açıklama/Borç)")
        return sonuc

    hesap_deseni = re.compile(r"^\d{3}\.\d{1,2}\.\d{1,3}\b")
    aktif_hesap = ""
    for i in range(baslik_i + 1, len(satirlar)):
        satir = satirlar[i]
        if not any(c is not None and str(c).strip() for c in satir):
            continue
        ilk = next((str(c).strip() for c in satir
                    if c is not None and str(c).strip()), "")
        if hesap_deseni.match(ilk):
            aktif_hesap = ilk
            continue

        def hucre(ad, _satir=satir):
            j = kolonlar.get(ad)
            return _satir[j] if j is not None and j < len(_satir) else None

        belge = fatura_no_temizle(str(hucre("belge") or "").strip())
        unvan = str(hucre("unvan") or "").strip()
        tarih_metin = str(hucre("tarih") or "").strip()
        borc = tutar_parse(hucre("borc"))
        if borc is None:
            borc = tutar_parse(hucre("alacak"))
        if not belge or borc is None:
            continue

        m = re.match(r"^(\d{1,2})[./](\d{1,2})[./](\d{2}|\d{4})$", tarih_metin)
        if m:
            gun, ay, yil = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if yil < 100:
                yil += 2000
            tarih = ""
            if 1 <= ay <= 12 and 1 <= gun <= 31:
                tarih = f"{yil:04d}-{ay:02d}-{gun:02d}"
        else:
            tarih = tarih_parse(tarih_metin) or ""

        kayit = {
            "vkn": "", "belge_no": belge, "tarih": tarih,
            "matrah": None, "kdv": borc, "unvan": unvan[:80],
            "notlar": [f"Hesap: {aktif_hesap}"] if aktif_hesap else [],
        }
        sonuc["kayitlar"].append(kayit)

    sonuc["kayitlar"] = _muavin_birlestir(sonuc["kayitlar"])
    if not sonuc["kayitlar"]:
        sonuc["notlar"].append("Zenom raporunda belge satırı bulunamadı")
    else:
        sonuc["notlar"].append("Zenom Muavin Raporu olarak okundu")
    return sonuc


def muavin_luca_fis_parse(dosya_yolu):
    """Luca/Türmob fiş dökümü çıktısını okur.

    Sütunları: Fiş No | Fiş Tarihi | Fiş Açıklama | Hesap Kodu | Evrak No |
    Evrak Tarihi | Detay Açıklama | Borç | Alacak | Miktar | Belge Türü |
    Para Birimi. Yalnız 191/391 KDV hesap satırları kaydedilir; 191'de Borç,
    391'de Alacak tutarı KDV'dir.
    """
    sonuc = {"dosya": dosya_yolu, "kayitlar": [], "notlar": []}
    satirlar = excel_satirlar(dosya_yolu)

    baslik_i = None
    kolonlar = {}
    for i, satir in enumerate(satirlar):
        normlar = [_norm_baslik(c) for c in satir]
        if ("FIS NO" in normlar and "HESAP KODU" in normlar
                and "BORC" in normlar and "ALACAK" in normlar):
            baslik_i = i
            for ad, anahtar in (("FIS NO", "fis"), ("FIS TARIHI", "ftarih"),
                                ("HESAP KODU", "hesap"), ("EVRAK NO", "belge"),
                                ("EVRAK TARIHI", "etarih"),
                                ("DETAY ACIKLAMA", "detay"),
                                ("BELGE TURU", "bturu"),
                                ("BORC", "borc"), ("ALACAK", "alacak")):
                kolonlar[anahtar] = normlar.index(ad) if ad in normlar else None
            break
    if baslik_i is None:
        sonuc["notlar"].append(
            "Luca fiş dökümü başlığı yok (Fiş No/Hesap Kodu/Borç/Alacak)")
        return sonuc

    for i in range(baslik_i + 1, len(satirlar)):
        satir = satirlar[i]
        if not any(c is not None and str(c).strip() for c in satir):
            continue

        def hucre(ad, _satir=satir):
            j = kolonlar.get(ad)
            return _satir[j] if j is not None and j < len(_satir) else None

        hesap = str(hucre("hesap") or "").strip()
        if not (hesap.startswith("191") or hesap.startswith("391")):
            continue

        belge = fatura_no_temizle(str(hucre("belge") or "").strip())
        detay = str(hucre("detay") or "").strip()
        borc = _huc_tutar(hucre("borc"))
        alacak = _huc_tutar(hucre("alacak"))
        kdv = borc if borc else alacak
        tarih_ham = hucre("ftarih") or hucre("etarih")
        if hasattr(tarih_ham, "strftime"):
            tarih = tarih_ham.strftime("%Y-%m-%d")
        else:
            tarih = tarih_parse(str(tarih_ham or "")) or ""
        if not belge or kdv is None:
            continue

        notlar = []
        if hesap:
            notlar.append(f"Hesap: {hesap}")
        bturu = str(hucre("bturu") or "").strip()
        if bturu:
            notlar.append(f"Belge Türü: {bturu}")
        kayit = {
            "vkn": "", "belge_no": belge, "tarih": tarih,
            "matrah": None, "kdv": kdv, "unvan": detay[:80],
            "notlar": notlar,
        }
        sonuc["kayitlar"].append(kayit)

    sonuc["kayitlar"] = _muavin_birlestir(sonuc["kayitlar"])
    if not sonuc["kayitlar"]:
        sonuc["notlar"].append("Luca fiş dökümünde 191/391 satırı bulunamadı")
    else:
        sonuc["notlar"].append("Luca fiş dökümü olarak okundu")
    return sonuc


def _muavin_birlestir(kayitlar):
    """Aynı faturanın hesap defterindeki parça satırlarını tek kayıtta toplar.

    Birleştirme anahtarı belge_no + tarih + unvan'dır: aynı faturanın
    bölünmüş KDV satırları (örn. 191-01 indirilecek + 191-03 tevkifat)
    aynı tarih ve unvanla geçer. Aynı belge numarasını farklı tarih veya
    unvanda kullanan FARKLI faturalar (belge numarası çakışması) ise ayrı
    kayıt olarak kalır; toplansalardı yanlış eşleşme oluşuyordu.
    """
    from decimal import Decimal
    gruplar = {}
    for k in kayitlar:
        anahtar = (
            k["belge_no"] or "",
            str(k.get("tarih") or ""),
            str(k.get("unvan") or ""),
        )
        if anahtar in gruplar:
            g = gruplar[anahtar]
            g["kdv"] = (g["kdv"] or Decimal("0")) + (k["kdv"] or Decimal("0"))
            for n in k["notlar"]:
                if n not in g["notlar"]:
                    g["notlar"].append(n)
        else:
            g = dict(k)
            g["notlar"] = list(k["notlar"])
            g["kdv"] = k["kdv"]
            gruplar[anahtar] = g
    sonuc = []
    for g in gruplar.values():
        if g["kdv"] is not None:
            g["kdv"] = g["kdv"].quantize(Decimal("0.01"))
        sonuc.append(g)
    return sonuc


# ============================================================================
# GENEL (OTOMATİK TANIMA) MUAVİN OKUYUCU
# ============================================================================

_GENEL_ETIKET_DESENLERI = [
    r"FT\.?\s*[NM]IZ\s*NO\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9\-/]{3,})",
    r"(?:FATURA|BELGE|EVRAK|FIS|FIŞ|DETAY)\s*NO\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9\-/]{3,})",
    r"\bNO\s*[:#.]\s*([A-Z0-9][A-Z0-9\-/]{6,})",
]
_GENEL_EBELGE_DESENI = re.compile(r"\b([A-Z0-9]{2,5}\d{9,})\b")
_GENEL_UZUN_RAKAM = re.compile(r"^\d{12,17}$")
_GENEL_ATLANIR = ("TOPLAM", "GENEL TOPLAM", "BAKIYE", "YEKUN", "DEVIR", "DEVİR",
                  "SAYFA", "ÖNCEKİ SAYFA", "ONCEKI SAYFA")
_GENEL_HESAP_DESENI = re.compile(r"^(?:\d{3}[-.\s]\d{1,2}[-.\s]\d{1,3}|(?:19|39)\d[-.]\d{1,2}(?:[-.]\d{1,3})?)$")


def _genel_baslik_puanla(satir_norm):
    """Bir satırın başlık olma puanı: tanınan sütun adı sayısı."""
    puan = 0
    for hucre in satir_norm:
        if not hucre:
            continue
        for sinonimler in KOLON_SINONIMLERI.values():
            for s in sinonimler:
                ns = _norm_baslik(s)
                if ns and (ns in hucre or hucre in ns) and abs(len(ns) - len(hucre)) < 15:
                    puan += 1
                    break
        for ekstra in ("BORC", "ALACAK", "ACIKLAMA", "DETAY NO", "FIS NO", "REFERANS"):
            if ekstra in hucre:
                puan += 1
                break
    return puan


def _genel_tarih_cikar(deger):
    if deger is None:
        return None
    if isinstance(deger, datetime):
        return deger.strftime("%Y-%m-%d")
    if isinstance(deger, date):
        return deger.strftime("%Y-%m-%d")
    metin = str(deger).strip()
    t = tarih_parse(metin)
    if t:
        return str(t)
    try:
        seri = _excel_seri_tarih(float(metin.replace(",", ".")))
        if seri:
            return seri
    except (ValueError, AttributeError):
        pass
    return None


def _genel_belge_cikar(hucreler):
    """Hücre listesinden fatura/belge numarasını çıkarır.

    Sıra: etiketli desen (FT.MIZ NO: vb.) → e-belge deseni → uzun saf rakam.
    """
    metinler = [h for h in hucreler if isinstance(h, str)]
    for desen in _GENEL_ETIKET_DESENLERI:
        m = re.search(desen, " || ".join(metinler), re.I)
        if m:
            belge = fatura_no_temizle(m.group(1))
            if len(belge) >= 4 and not belge.isdigit() or len(belge) >= 12:
                return belge
    for h in metinler:
        m = _GENEL_EBELGE_DESENI.search(h.upper())
        if m:
            return fatura_no_temizle(m.group(1))
    for h in metinler:
        rakam = re.sub(r"\D", "", h)
        if _GENEL_UZUN_RAKAM.match(rakam):
            return rakam
    return None


def _genel_unvan_cikar(hucreler, belge, aciklama_metni=None):
    adaylar = []
    for h in hucreler:
        if isinstance(h, str):
            metin = h.strip()
            if not metin or len(metin) < 3:
                continue
            if belge and belge.upper() in metin.upper():
                metin = metin.upper().replace(belge.upper(), " ").strip()
            metin = re.split(r"FT\.?\s*[NM]IZ", metin, flags=re.I)[0].strip(" .,-")
            metin = re.sub(r"(?i)\b(KDVSI|KDV|ALIM FATURA|SATIS FATURA|SATIŞ FATURA)\b.*$", "", metin).strip(" .,-")
            if len(metin) >= 3 and not metin.replace(".", "").replace(",", "").isdigit():
                adaylar.append(metin)
    if not adaylar:
        return ""
    en_uzun = max(adaylar, key=len)
    return en_uzun[:80]


def _vkn_kontrol_hanesi(no):
    """10 haneli VKN kontrol hanesini doğrular; 11 haneli TCKN'de ilk
    hane sıfır olmamalı. Yanlış okumayı elemek için kullanılır."""
    no = (no or "").strip()
    if len(no) == 11:
        return no.isdigit() and no[0] != "0"
    if len(no) != 10 or not no.isdigit():
        return False
    d = [int(c) for c in no]
    s = 0
    for i in range(9):
        t = (d[i] + 10 - (i + 1)) % 10
        s = (s * ((t * 2) % 9 + 1)) % 10
    return (10 - (s + d[9]) % 10) % 10 == d[9]


def muavin_genel_parse(dosya_yolu):
    """Bilinmeyen Excel muavin/hesap defteri formatlarını otomatik tanıyıp okur.

    Yeni bir cetvel türü geldiğinde özel parser'lar tanımazsa devreye girer.
    Başlık satırı varsa sütunları eş anlamlı sözlükten eşler (sıra fark etmez);
    başlık yoksa her satırdan tarih/belge/tutar hücrelerini kendi çıkarır.
    Belge numarası etiketli desen (FT.MIZ NO:), e-belge deseni veya uzun
    rakam olarak herhangi bir hücrede aranır.
    """
    import re as _re

    satirlar = excel_satirlar(dosya_yolu)
    sonuc = {"dosya": dosya_yolu, "kayitlar": [], "notlar": []}

    # 1) En iyi başlık satırını bul
    baslik_i = None
    kolonlar = {}
    en_iyi_puan = 0
    for i, satir in enumerate(satirlar[:60]):
        normlar = [_norm_baslik(c) for c in satir]
        puan = _genel_baslik_puanla(normlar)
        if puan > en_iyi_puan:
            en_iyi_puan = puan
    if en_iyi_puan >= 2:
        for i, satir in enumerate(satirlar[:60]):
            normlar = [_norm_baslik(c) for c in satir]
            if _genel_baslik_puanla(normlar) == en_iyi_puan:
                baslik_i = i
                break

    aktif_hesap = ""
    kayit_sayisi = 0
    if baslik_i is not None:
        # Sütunları başlıklardan eşle
        baslik_normlari = [_norm_baslik(c) for c in satirlar[baslik_i]]
        for alan in ("tarih", "belge_no", "kdv", "matrah", "vkn", "unvan"):
            kolonlar[alan] = _kolon_bul(baslik_normlari, alan)
        for alan in ("aciklama", "borc", "alacak"):
            kolonlar[alan] = None
        # Ek eş anlamlılar
        for j, n in enumerate(baslik_normlari):
            if kolonlar["borc"] is None and "BORC" in n:
                kolonlar["borc"] = j
            if kolonlar["alacak"] is None and "ALACAK" in n:
                kolonlar["alacak"] = j
            if kolonlar["aciklama"] is None and ("ACIKLAMA" in n or "DETAY" in n or "ISLEM" in n or "YAPILAN" in n):
                kolonlar["aciklama"] = j

    for i, satir in enumerate(satirlar):
        if not any(c is not None and str(c).strip() for c in satir):
            continue
        ilk = str(satir[0]).strip() if satir and satir[0] is not None else ""
        ilk_tarih = _genel_tarih_cikar(satir[0]) if satir else None
        if ilk_tarih is None and (_GENEL_HESAP_DESENI.match(ilk)
                                  or _GENEL_HESAP_DESENI.match(_norm_baslik(ilk))):
            aktif_hesap = ilk
            continue
        if baslik_i is not None and i <= baslik_i:
            continue

        tarih = None
        if baslik_i is not None and kolonlar.get("tarih") is not None and kolonlar["tarih"] < len(satir):
            tarih = _genel_tarih_cikar(satir[kolonlar["tarih"]])
        if tarih is None:
            for c in satir:
                tarih = _genel_tarih_cikar(c)
                if tarih:
                    break

        belge = _genel_belge_cikar(list(satir))
        if belge is None:
            continue

        ust_metin = " ".join(str(c) for c in satir if c is not None)
        if any(k in ust_metin.upper() for k in _GENEL_ATLANIR):
            continue

        kdv = None
        if baslik_i is not None:
            b = a = None
            if kolonlar.get("borc") is not None and kolonlar["borc"] < len(satir):
                b = _huc_tutar(satir[kolonlar["borc"]])
            if kolonlar.get("alacak") is not None and kolonlar["alacak"] < len(satir):
                a = _huc_tutar(satir[kolonlar["alacak"]])
            if kolonlar.get("kdv") is not None and kolonlar["kdv"] < len(satir):
                kdv = _huc_tutar(satir[kolonlar["kdv"]])
            kdv = kdv or (b if b else a)
        if kdv is None:
            # Başlıksız mod: tarih/belge hücrelerini atlayıp en sağdaki sayıyı al.
            belge_rakam = re.sub(r"\D", "", belge)
            adaylar = []
            for c in satir:
                if _genel_tarih_cikar(c):
                    continue
                if isinstance(c, (int, float)):
                    adaylar.append(_huc_tutar(c))
                elif isinstance(c, str):
                    if re.sub(r"\D", "", c) == belge_rakam:
                        continue
                    adaylar.append(_huc_tutar(c))
            adaylar = [v for v in adaylar if v and v != 0]
            if adaylar:
                kdv = adaylar[-1]
        if kdv is None or kdv == 0:
            continue

        unvan = ""
        if kolonlar.get("unvan") is not None and kolonlar["unvan"] < len(satir):
            unvan = str(satir[kolonlar["unvan"]] or "")[:80]
        if not unvan:
            unvan = _genel_unvan_cikar(list(satir), belge)

        notlar = []
        if aktif_hesap:
            notlar.append(f"Hesap: {aktif_hesap}")
        # Açıklamadan VKN/TCKN çıkar ('VKN:1234567890' veya 10-11 haneli
        # sayı). Böylece çapraz kontrolde VKN doğrulaması gerçek olur.
        cikarilan_vkn = ""
        m_vkn = re.search(r"VKN\s*[:=)]*\s*(\d{10,11})", unvan or "",
                          re.IGNORECASE)
        if m_vkn:
            cikarilan_vkn = m_vkn.group(1)
        else:
            for m_rakam in re.finditer(r"(?<!\d)(\d{10,11})(?!\d)",
                                       unvan or ""):
                aday = m_rakam.group(1)
                if _vkn_kontrol_hanesi(aday):
                    cikarilan_vkn = aday
                    break
        sonuc["kayitlar"].append({
            "vkn": cikarilan_vkn, "belge_no": belge,
            "tarih": tarih if tarih else None,
            "matrah": None, "kdv": kdv, "unvan": unvan,
            "notlar": notlar,
        })
        kayit_sayisi += 1

    sonuc["kayitlar"] = _muavin_birlestir(sonuc["kayitlar"])
    if not sonuc["kayitlar"]:
        sonuc["notlar"].append("Genel otomatik tanıma da satır bulamadı")
    else:
        mod = "başlıklı" if baslik_i is not None else "başlıksız"
        sonuc["notlar"].append(
            f"Genel format otomatik tanındı ({mod}, {len(sonuc['kayitlar'])} kayıt)")
    return sonuc
