import os
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from matcher import (DURUM_CETVELDE_YOK, DURUM_FATURADA_YOK, DURUM_MUKERRER,
                     DURUM_OK, DURUM_PARSE_SORUNU, DURUM_TUTAR_FARKI,
                     DURUM_VKN_FARKI, SORUNLU_DURUMLAR)
from ozetler import ba_formu, kdv_dagilim_fatura, kdv_dagilim_muavin
from utils import tl_format

BASLIK_FONT = Font(bold=True, color="FFFFFF", size=11)
BASLIK_DOLGU = PatternFill("solid", fgColor="4472C4")
OK_DOLGU = PatternFill("solid", fgColor="C6EFCE")
SORUN_DOLGU = PatternFill("solid", fgColor="FFC7CE")
UYARI_DOLGU = PatternFill("solid", fgColor="FFEB9C")
TOPLAM_DOLGU = PatternFill("solid", fgColor="D9E1F2")
INCE_KENAR = Border(
    left=Side(style="thin"), right=Side(style="thin"),
    top=Side(style="thin"), bottom=Side(style="thin"),
)

DURUM_RENK = {
    DURUM_OK: OK_DOLGU,
    DURUM_TUTAR_FARKI: SORUN_DOLGU,
    DURUM_VKN_FARKI: UYARI_DOLGU,
    DURUM_MUKERRER: UYARI_DOLGU,
    DURUM_CETVELDE_YOK: SORUN_DOLGU,
    DURUM_FATURADA_YOK: SORUN_DOLGU,
}

DURUM_ADLARI = {
    DURUM_OK: "Eşleşti",
    DURUM_TUTAR_FARKI: "Tutar Farkı",
    DURUM_VKN_FARKI: "VKN Farkı",
    DURUM_CETVELDE_YOK: "Muavinde Yok",
    DURUM_FATURADA_YOK: "Faturalarda Yok",
    DURUM_MUKERRER: "Mükerrer",
    DURUM_PARSE_SORUNU: "Okunamadı",
}


def tablo_yaz(sayfa, basliklar, satirlar, genislikler=None, renk_kurali=None, sayi_kolonlari=None):
    for j, b in enumerate(basliklar, start=1):
        hucre = sayfa.cell(row=1, column=j, value=b)
        hucre.font = BASLIK_FONT
        hucre.fill = BASLIK_DOLGU
        hucre.alignment = Alignment(horizontal="center", vertical="center")
        hucre.border = INCE_KENAR
    for i, satir in enumerate(satirlar, start=2):
        for j, deger in enumerate(satir, start=1):
            hucre = sayfa.cell(row=i, column=j, value=deger)
            hucre.border = INCE_KENAR
            if sayi_kolonlari and j in sayi_kolonlari:
                hucre.number_format = "#,##0.00"
                hucre.alignment = Alignment(horizontal="right")
            if renk_kurali:
                dolgu = renk_kurali(satir)
                if dolgu:
                    hucre.fill = dolgu
    if genislikler:
        for j, g in enumerate(genislikler, start=1):
            sayfa.column_dimensions[get_column_letter(j)].width = g
    sayfa.freeze_panes = "A2"


def _tutar(deger):
    return deger if deger is not None else ""


def _oranlar_str(oranlar):
    if not oranlar:
        return ""
    return ", ".join(f"%{o}%" for o in oranlar)


def _tarih_araligi(faturalar, cetvel_kayitlari):
    tarihler = [f["tarih"] for f in faturalar if f.get("tarih")]
    tarihler += [c["tarih"] for c in cetvel_kayitlari if c.get("tarih")]
    if not tarihler:
        return "-"
    return f"{min(tarihler)} - {max(tarihler)}"


def rapor_olustur(sonuc_satirlari, ozet, faturalar, cetvel_kayitlari, hedef_yol, gecmis_bilgi=None):
    wb = Workbook()

    def durum_toplamlar():
        toplamlar = {}
        for d in DURUM_ADLARI:
            toplamlar[d] = {"adet": 0, "matrah": 0, "kdv": 0}
        for r in sonuc_satirlari:
            d = r["durum"]
            toplamlar.setdefault(d, {"adet": 0, "matrah": 0, "kdv": 0})
            t = toplamlar[d]
            t["adet"] += 1
            if r["matrah"] is not None:
                t["matrah"] += r["matrah"]
            if r["kdv"] is not None:
                t["kdv"] += r["kdv"]
        return toplamlar

    # ---------- 1) Özet ----------
    ws = wb.active
    ws.title = "Ozet"
    toplamlar = durum_toplamlar()
    genel_kdv = sum((f["kdv"] or 0) for f in faturalar)
    eksik_kdv = toplamlar[DURUM_CETVELDE_YOK]["kdv"]
    fazla_kdv = toplamlar[DURUM_FATURADA_YOK]["kdv"]
    fark_kdv = toplamlar[DURUM_TUTAR_FARKI]["kdv"]
    durum_kdv = sum((r["kdv"] or 0) for r in sonuc_satirlari if r["durum"] == DURUM_OK)

    baslik = ws.cell(row=1, column=1, value="KDV ÇAPRAZ KONTROL RAPORU")
    baslik.font = Font(bold=True, size=14)
    ws.cell(row=2, column=1, value=f"Üretim zamanı: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    ws.cell(row=3, column=1, value=f"Belge dönemi: {_tarih_araligi(faturalar, cetvel_kayitlari)}")

    ozet_metinler = [
        ("", ""),
        ("KAPSAM", ""),
        ("XML/PDF Fatura Sayısı", ozet["fatura_adet"]),
        ("Muavin Kayıt Sayısı", ozet["cetvel_adet"]),
        ("", ""),
        ("EŞLEŞME SONUÇLARI", ""),
        ("Eşleşen (tutar uyumlu)", ozet["eslesen"]),
        ("Tutar Farkı Olan", ozet["tutar_farki"]),
        ("VKN Farkı Olan", ozet["vkn_farki"]),
        ("Muavinde Kaydı Olmayan Fatura", ozet["cetvelde_yok"]),
        ("Faturalarda Olmayan Muavin Kaydı", ozet["faturada_yok"]),
        ("Mükerrer Kayıt", ozet["mukerrer"]),
        ("Okunamayan Fatura", ozet["parse_sorunu"]),
        ("", ""),
        ("KDV TUTARLARI (TL)", ""),
        ("Tüm faturaların toplam KDV'si", genel_kdv),
        ("Eşleşen faturaların toplam KDV'si", durum_kdv),
        ("Muavinde olmayan faturaların KDV'si (EKSİK)", eksik_kdv),
        ("XML'de olmayan muavin KDV'si (FAZLA)", fazla_kdv),
        ("Tutar farkı olan kayıtların KDV'si", fark_kdv),
        ("", ""),
        ("SATICI BAZINDA MUAVİNDE OLMAYAN KDV (EKSİK)", ""),
    ]
    satir_ozet = len(ozet_metinler) + 2
    ws.column_dimensions["A"].width = 52
    ws.column_dimensions["B"].width = 18

    # Satıcı bazlı eksik özeti
    eksik_satici = {}
    for r in sonuc_satirlari:
        if r["durum"] == DURUM_CETVELDE_YOK and r["kdv"] is not None and r["kdv"]:
            anahtar = (r["vkn"], r["unvan"])
            g = eksik_satici.setdefault(anahtar, {"adet": 0, "kdv": 0})
            g["adet"] += 1
            g["kdv"] += r["kdv"]
    for (vkn, unvan), g in sorted(eksik_satici.items(), key=lambda x: -x[1]["kdv"]):
        if not vkn and not unvan:
            continue
        ad = unvan or vkn
        ozet_metinler.append((f"  {ad}  (VKN: {vkn or '-'})", f"{g['adet']} fatura / {tl_format(g['kdv'])} KDV"))

    for i, (a, v) in enumerate(ozet_metinler, start=1):
        ws.cell(row=i, column=1, value=a)
        if v != "":
            h = ws.cell(row=i, column=2, value=v)
            h.border = INCE_KENAR
            if a.startswith("  "):
                h.fill = UYARI_DOLGU
            elif a.startswith(("EŞLEŞME", "KDV TUTARLARI", "SATICI", "KAPSAM")):
                ws.cell(row=i, column=1).font = Font(bold=True)
                h.fill = TOPLAM_DOLGU
            else:
                if isinstance(v, int):
                    h.number_format = "#,##0.00"
                    h.alignment = Alignment(horizontal="right")
                    h.fill = OK_DOLGU if v == 0 else SORUN_DOLGU
    ws.cell(row=satir_ozet - 1, column=1).border = INCE_KENAR

    # Geçmiş kontrol karşılaştırması
    if gecmis_bilgi:
        baslangic = len(ozet_metinler) + 2
        ws.cell(row=baslangic + 1, column=1, value="SON KONTROLE GÖRE DEĞİŞİM").font = Font(bold=True)
        ozet_metinler.append(("SON KONTROLE GÖRE DEĞİŞİM", ""))
        if gecmis_bilgi.get("kapanan"):
            ozet_metinler.append(("  Bu ay muavine eklenen belgeler (çözüldü)", str(len(gecmis_bilgi["kapanan"])) + " adet"))
        if gecmis_bilgi.get("yeni"):
            ozet_metinler.append(("  Bu ay yeni ortaya çıkan eksikler", str(len(gecmis_bilgi["yeni"])) + " adet"))
        if gecmis_bilgi.get("onceki_eslesen") is not None:
            ozet_metinler.append(("  Önceki eşleşen adedi", gecmis_bilgi["onceki_eslesen"]))
        if gecmis_bilgi.get("zaman"):
            ozet_metinler.append(("  Önceki kontrol zamanı", gecmis_bilgi["zaman"]))
        for i, (a, v) in enumerate(ozet_metinler, start=1):
            ws.cell(row=i, column=1, value=a)
            if v != "":
                h = ws.cell(row=i, column=2, value=v)
                h.border = INCE_KENAR
                if a.startswith("  "):
                    h.fill = OK_DOLGU if "çözüldü" in a else UYARI_DOLGU
                elif a == "SON KONTROLE GÖRE DEĞİŞİM":
                    h.fill = TOPLAM_DOLGU

    # ---------- 2) Sonuçlar ----------
    ws2 = wb.create_sheet("Sonuclar")
    basliklar = ["Durum", "Belge No", "VKN", "Satıcı/Ünvan", "Tarih", "Tip", "Matrah", "KDV", "Toplam", "Oranlar", "Oran Kontrol", "Kaynak", "Detay"]
    satirlar = []
    for r in sonuc_satirlari:
        satirlar.append([
            DURUM_ADLARI.get(r["durum"], r["durum"]),
            r["belge_no"] or "",
            r["vkn"] or "",
            r["unvan"] or "",
            r["tarih"] or "",
            r.get("tip") or "",
            _tutar(r["matrah"]),
            _tutar(r["kdv"]),
            _tutar(r.get("toplam")),
            _oranlar_str(r.get("oranlar")),
            r.get("oran_kontrol") or "",
            r["kaynak"] or "",
            r["detay"] or "",
        ])
    tablo_yaz(
        ws2, basliklar, satirlar,
        genislikler=[18, 22, 13, 30, 12, 14, 14, 14, 14, 10, 14, 10, 60],
        renk_kurali=lambda s: DURUM_RENK.get(next(k for k in DURUM_RENK if DURUM_ADLARI.get(k) == s[0]), None),
        sayi_kolonlari={7, 8, 9},
    )

    # ---------- 3) Muavinde Olmayan Faturalar (EKSİK) ----------
    ws3 = wb.create_sheet("EksikFaturalar")
    basliklar = ["Tarih", "Belge No", "Tip", "Satıcı VKN", "Satıcı Ünvanı", "Matrah", "KDV", "Toplam", "Oranlar", "Detay"]
    satirlar = []
    for r in sonuc_satirlari:
        if r["durum"] != DURUM_CETVELDE_YOK:
            continue
        satirlar.append([
            r["tarih"] or "", r["belge_no"] or "", r.get("tip") or "",
            r["vkn"] or "", r["unvan"] or "",
            _tutar(r["matrah"]), _tutar(r["kdv"]), _tutar(r.get("toplam")),
            _oranlar_str(r.get("oranlar")), r["detay"] or "",
        ])
    toplam_matrah = sum((r["matrah"] or 0) for r in sonuc_satirlari if r["durum"] == DURUM_CETVELDE_YOK)
    toplam_kdv = sum((r["kdv"] or 0) for r in sonuc_satirlari if r["durum"] == DURUM_CETVELDE_YOK)
    if satirlar:
        satirlar.append(["", "TOPLAM", "", "", "", toplam_matrah, toplam_kdv, "", "", ""])
    tablo_yaz(
        ws3, basliklar, satirlar,
        genislikler=[12, 22, 14, 13, 30, 14, 14, 14, 10, 60],
        sayi_kolonlari={6, 7, 8},
    )
    if satirlar:
        for j in range(1, len(basliklar) + 1):
            ws3.cell(row=len(satirlar) + 1, column=j).fill = TOPLAM_DOLGU

    # ---------- 4) Faturalarda Olmayan Muavin Kayıtları (FAZLA) ----------
    ws4 = wb.create_sheet("FazlaMuavin")
    basliklar = ["Tarih", "Belge No", "Ünvan", "KDV", "Notlar"]
    satirlar = []
    for r in sonuc_satirlari:
        if r["durum"] != DURUM_FATURADA_YOK:
            continue
        satirlar.append([
            r["tarih"] or "", r["belge_no"] or "", r["unvan"] or "",
            _tutar(r["kdv"]), r["detay"] or "",
        ])
    toplam_kdv = sum((r["kdv"] or 0) for r in sonuc_satirlari if r["durum"] == DURUM_FATURADA_YOK)
    if satirlar:
        satirlar.append(["", "TOPLAM", "", toplam_kdv, ""])
    tablo_yaz(
        ws4, basliklar, satirlar,
        genislikler=[12, 22, 40, 14, 50],
        sayi_kolonlari={4},
    )
    if satirlar:
        for j in range(1, len(basliklar) + 1):
            ws4.cell(row=len(satirlar) + 1, column=j).fill = TOPLAM_DOLGU

    # ---------- 5) Tutar/VKN Farkları ----------
    ws5 = wb.create_sheet("TutarFarklari")
    basliklar = ["Durum", "Belge No", "VKN", "Ünvan", "Tarih", "Matrah", "KDV", "Detay"]
    satirlar = []
    for r in sonuc_satirlari:
        if r["durum"] not in (DURUM_TUTAR_FARKI, DURUM_VKN_FARKI, DURUM_MUKERRER):
            continue
        satirlar.append([
            DURUM_ADLARI.get(r["durum"], r["durum"]),
            r["belge_no"] or "", r["vkn"] or "", r["unvan"] or "",
            r["tarih"] or "", _tutar(r["matrah"]), _tutar(r["kdv"]), r["detay"] or "",
        ])
    tablo_yaz(
        ws5, basliklar, satirlar,
        genislikler=[14, 22, 13, 30, 12, 14, 14, 60],
        sayi_kolonlari={6, 7},
    )

    # ---------- 6) Satıcı Özeti ----------
    ws6 = wb.create_sheet("SaticiOzeti")
    saticilar = {}
    for f in faturalar:
        anahtar = (f.get("satici_vkn") or "", f.get("satici_unvan") or "")
        g = saticilar.setdefault(anahtar, {"adet": 0, "matrah": 0, "kdv": 0, "eslesen": 0, "eksik": 0, "eksik_kdv": 0})
        g["adet"] += 1
        g["matrah"] += f["matrah"] or 0
        g["kdv"] += f["kdv"] or 0
    eslesen_belge = {}
    for r in sonuc_satirlari:
        if r["durum"] == DURUM_OK:
            eslesen_belge[r["belge_no"]] = True
    for f in faturalar:
        anahtar = (f.get("satici_vkn") or "", f.get("satici_unvan") or "")
        g = saticilar.get(anahtar)
        if g is None:
            continue
        if (f["belge_no"] or "") in eslesen_belge:
            g["eslesen"] += 1
        else:
            g["eksik"] += 1
            g["eksik_kdv"] += f["kdv"] or 0
    basliklar = ["VKN", "Satıcı Ünvanı", "Fatura Adedi", "Eşleşen", "Muavinde Yok", "Toplam Matrah", "Toplam KDV", "Eksik KDV (TL)"]
    satirlar = []
    for (vkn, unvan), g in sorted(saticilar.items(), key=lambda x: -x[1]["eksik_kdv"]):
        if not vkn and not unvan:
            continue
        satirlar.append([
            vkn or "", unvan or "", g["adet"], g["eslesen"], g["eksik"],
            g["matrah"], g["kdv"], g["eksik_kdv"],
        ])
    tablo_yaz(
        ws6, basliklar, satirlar,
        genislikler=[14, 40, 13, 10, 14, 14, 14, 14],
        renk_kurali=lambda s: SORUN_DOLGU if (s[4] if isinstance(s[4], int) else 0) else None,
        sayi_kolonlari={6, 7, 8},
    )

    # ---------- 7) Faturalar (tümü) ----------
    ws7 = wb.create_sheet("Faturalar")
    satirlar = []
    for f in faturalar:
        konum = f.get("satir", 1) if f.get("tip") == "excel" else f.get("sayfa", 1)
        satirlar.append([
            os.path.basename(f["dosya"]),
            konum,
            f["belge_no"] or "",
            f["tarih"] or "",
            f.get("satici_unvan") or "",
            f.get("satici_vkn") or "",
            f.get("alici_vkn") or "",
            _tutar(f.get("matrah")),
            _tutar(f.get("kdv")),
            _tutar(f.get("toplam")),
            _oranlar_str(f.get("oranlar")),
            " / ".join(f["notlar"]) if f.get("notlar") else "",
        ])
    tablo_yaz(
        ws7, ["Dosya", "Sayfa/Satır", "Belge No", "Tarih", "Satıcı Ünvanı", "Satıcı VKN", "Alıcı VKN", "Matrah", "KDV", "Toplam", "Oranlar", "Notlar"],
        satirlar,
        genislikler=[30, 10, 22, 12, 30, 14, 14, 14, 14, 14, 10, 50],
        sayi_kolonlari={8, 9, 10},
    )

    # ---------- 8) Kontrol Cetveli (muavin) ----------
    ws8 = wb.create_sheet("KontrolCetveli")
    satirlar = []
    for c in cetvel_kayitlari:
        satirlar.append([
            c["vkn"] or "",
            c["belge_no"] or "",
            c["tarih"] or "",
            _tutar(c.get("matrah")),
            _tutar(c.get("kdv")),
            c.get("unvan") or "",
            " / ".join(c["notlar"]) if c.get("notlar") else "",
        ])
    tablo_yaz(
        ws8, ["VKN", "Belge No", "Tarih", "Matrah", "KDV", "Ünvan", "Notlar"],
        satirlar,
        genislikler=[14, 22, 12, 14, 14, 40, 40],
        sayi_kolonlari={4, 5},
    )
    oran_kontrol_sayfasi_ekle(wb, sonuc_satirlari, faturalar)


    wb.save(hedef_yol)
    return hedef_yol


# ============================================================================
# ORAN DOĞRULAMA SAYFASI (YENİ)
# ============================================================================

def oran_kontrol_sayfasi_ekle(wb, sonuc_satirlari, faturalar):
    """Matrah × oran = KDV doğrulaması raporu."""
    if "KDV Oran Kontrolü" in wb.sheetnames:
        return
    ws = wb.create_sheet("KDV Oran Kontrolü")

    basliklar = ["Belge No", "VKN", "Tarih", "Matrah", "KDV", "Oranlar", "Beklenen KDV", "Fark", "Uyum", "Mesaj"]
    INCE = Border(left=Side(style="thin"), right=Side(style="thin"),
                  top=Side(style="thin"), bottom=Side(style="thin"))
    BASLIK = Font(bold=True, color="FFFFFF", size=11)
    DOLGU = PatternFill("solid", fgColor="4472C4")
    for j, b in enumerate(basliklar, 1):
        h = ws.cell(row=1, column=j, value=b)
        h.font = BASLIK
        h.fill = DOLGU
        h.border = INCE

    fatura_haritasi = {f.get("belge_no"): f for f in faturalar if f.get("belge_no")}

    satir_no = 2
    for r in sonuc_satirlari:
        belge = r.get("belge_no")
        fatura = fatura_haritasi.get(belge)
        if not fatura:
            continue
        from oran_kontrol import oran_dogrula
        kontrol = oran_dogrula(fatura)

        ws.cell(row=satir_no, column=1, value=belge or "")
        ws.cell(row=satir_no, column=2, value=fatura.get("satici_vkn") or "")
        ws.cell(row=satir_no, column=3, value=fatura.get("tarih") or "")
        ws.cell(row=satir_no, column=4, value=float(fatura.get("matrah") or 0))
        ws.cell(row=satir_no, column=5, value=float(fatura.get("kdv") or 0))
        ws.cell(row=satir_no, column=6, value=", ".join(f"%{o}" for o in fatura.get("oranlar") or []))
        ws.cell(row=satir_no, column=7, value=float(kontrol["beklenen_kdv"]) if kontrol["beklenen_kdv"] is not None else "")
        ws.cell(row=satir_no, column=8, value=float(kontrol["fark"]) if kontrol["fark"] is not None else "")
        ws.cell(row=satir_no, column=9, value="✅" if kontrol["uyumlu"] else "❌")
        ws.cell(row=satir_no, column=10, value=kontrol["mesaj"])

        for j in range(1, 11):
            ws.cell(row=satir_no, column=j).border = INCE
            if j in (4, 5, 7, 8):
                ws.cell(row=satir_no, column=j).number_format = "#,##0.00"
            if j == 9:
                renk = PatternFill("solid", fgColor="C6EFCE") if kontrol["uyumlu"] else PatternFill("solid", fgColor="FFC7CE")
                ws.cell(row=satir_no, column=j).fill = renk
        satir_no += 1

    for j, w in enumerate([20, 13, 11, 14, 14, 14, 14, 12, 7, 35], 1):
        ws.column_dimensions[get_column_letter(j)].width = w
