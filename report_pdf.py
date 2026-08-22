import os
from datetime import datetime

from fpdf import FPDF
from fpdf.fonts import FontFace

from matcher import (DURUM_CETVELDE_YOK, DURUM_FATURADA_YOK, DURUM_MUKERRER,
                     DURUM_OK, DURUM_PARSE_SORUNU, DURUM_TUTAR_FARKI,
                     DURUM_VKN_FARKI)
from ozetler import ba_formu, kdv_dagilim_fatura, kdv_dagilim_muavin
from utils import tl_format

FONT_DIZINI = r"C:\Windows\Fonts"
FONT_TERCIHLERI = [
    ("calibri.ttf", "calibrib.ttf"),
    ("segoeui.ttf", "segoeuib.ttf"),
    ("tahoma.ttf", "tahomabd.ttf"),
    ("arial.ttf", "arialbd.ttf"),
    ("carlito.ttf", "carlitob.ttf"),
    ("dejavusans.ttf", "dejavusans-bold.ttf"),
    ("liberationsans.ttf", "liberationsans-bold.ttf"),
]

MAVI = (68, 114, 196)
YESIL = (198, 239, 206)
KIRMIZI = (255, 199, 206)
SARI = (255, 235, 156)
MAVI_ACIK = (217, 225, 242)
SIRALAMA_GRISI = (242, 242, 242)

DURUM_RENK = {
    DURUM_OK: YESIL,
    DURUM_TUTAR_FARKI: KIRMIZI,
    DURUM_VKN_FARKI: SARI,
    DURUM_MUKERRER: SARI,
    DURUM_CETVELDE_YOK: KIRMIZI,
    DURUM_FATURADA_YOK: KIRMIZI,
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


def _font_bul():
    for normal, kalin in FONT_TERCIHLERI:
        n_yol = os.path.join(FONT_DIZINI, normal)
        if os.path.exists(n_yol):
            k_yol = os.path.join(FONT_DIZINI, kalin)
            return n_yol, k_yol if os.path.exists(k_yol) else None
    return None, None


class KdvRaporPDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_auto_page_break(auto=True, margin=10)

    def baslik_koy(self, metin):
        self.set_font("tr", "B", 15)
        self.set_text_color(*MAVI)
        self.cell(0, 9, metin, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def ust_bilgi(self, tarih_araligi):
        self.set_font("tr", "", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 5, f"Üretim zamanı: {datetime.now().strftime('%d.%m.%Y %H:%M')}   |   Belge dönemi: {tarih_araligi}", new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(3)


def _tarih_araligi(faturalar, cetvel_kayitlari):
    tarihler = [f["tarih"] for f in faturalar if f.get("tarih")]
    tarihler += [c["tarih"] for c in cetvel_kayitlari if c.get("tarih")]
    if not tarihler:
        return "-"
    return f"{min(tarihler)} - {max(tarihler)}"


def _satir_kdv_tl(r):
    return tl_format(r["kdv"]) if r.get("kdv") is not None else ""


def rapor_pdf_olustur(sonuc_satirlari, ozet, faturalar, cetvel_kayitlari, hedef_yol, gecmis_bilgi=None):
    from report import _ozet_tamamla
    ozet = _ozet_tamamla(ozet)
    normal_yol, kalin_yol = _font_bul()
    pdf = KdvRaporPDF(orientation="P", unit="mm", format="A4")
    pdf.set_left_margin(12)
    pdf.set_right_margin(12)
    aile = "tr"
    if normal_yol:
        pdf.add_font("tr", "", normal_yol)
        if kalin_yol:
            pdf.add_font("tr", "B", kalin_yol)
    else:
        aile = "helvetica"

    def f_tablo(basliklar, satirlar, genislikler, renkler=None, yazi_boyutu=8, toplam_satir_idx=None, sola_kolonlar=None):
        sola_kolonlar = sola_kolonlar or set()
        baslik_yuz = FontFace(family=aile, emphasis="B", size_pt=8.5, color=(255, 255, 255), fill_color=MAVI)
        with pdf.table(
            col_widths=genislikler,
            align="CENTER",
            text_align="CENTER",
            borders_layout="ALL",
            headings_style=baslik_yuz,
            line_height=5,
            padding=1.2,
            width=pdf.w - 24,
        ) as tablo:
            tablo.row(basliklar)
            for i, veri in enumerate(satirlar):
                satir = tablo.row()
                for j, deger in enumerate(veri):
                    dolgu = None
                    kalin = False
                    if i == toplam_satir_idx:
                        dolgu = MAVI_ACIK
                        kalin = True
                    elif renkler and isinstance(renkler.get(j), dict):
                        dolgu = renkler[j].get(i)
                    elif renkler and isinstance(renkler.get(j), tuple):
                        dolgu = renkler[j]
                    elif renkler and renkler.get("_satir", {}).get(i):
                        dolgu = renkler["_satir"][i]
                    yuz = None
                    if dolgu is not None:
                        yuz = FontFace(family=aile, emphasis="B" if kalin else "", size_pt=yazi_boyutu, fill_color=dolgu)
                    satir.cell(
                        "" if deger is None else str(deger),
                        style=yuz,
                        align="LEFT" if j in sola_kolonlar else "CENTER",
                    )

    def yeni_sayfa(manzara=False):
        pdf.add_page(orientation="L" if manzara else "P")
        pdf.ust_bilgi(_tarih_araligi(faturalar, cetvel_kayitlari))

    # ---------- Sayfa 1: Özet ----------
    pdf.add_page()
    pdf.baslik_koy("KDV ÇAPRAZ KONTROL RAPORU")
    pdf.ust_bilgi(_tarih_araligi(faturalar, cetvel_kayitlari))

    pdf.set_font("tr", "B", 11)
    pdf.cell(0, 7, "KAPSAM", new_x="LMARGIN", new_y="NEXT")
    f_tablo(
        ["Açıklama", "Değer"],
        [
            ["XML/PDF Fatura Sayısı", ozet["fatura_adet"]],
            ["Muavin Kayıt Sayısı", ozet["cetvel_adet"]],
        ],
        [70, 30],
    )
    pdf.ln(4)

    pdf.set_font("tr", "B", 11)
    pdf.cell(0, 7, "EŞLEŞME SONUÇLARI", new_x="LMARGIN", new_y="NEXT")
    durum_satirlari = [
        ["Eşleşen (tutar uyumlu)", ozet["eslesen"], YESIL],
        ["Tutar Farkı Olan", ozet["tutar_farki"], KIRMIZI],
        ["VKN Farkı Olan", ozet["vkn_farki"], SARI],
        ["Muavinde Kaydı Olmayan Fatura", ozet["cetvelde_yok"], KIRMIZI],
        ["Faturalarda Olmayan Muavin Kaydı", ozet["faturada_yok"], KIRMIZI],
        ["Mükerrer Kayıt", ozet["mukerrer"], SARI],
        ["Okunamayan Fatura", ozet["parse_sorunu"], KIRMIZI],
    ]
    f_tablo(
        ["Açıklama", "Değer"],
        [[a, v] for a, v, _ in durum_satirlari],
        [80, 30],
        renkler={1: {i: r for i, (_, _, r) in enumerate(durum_satirlari)}},
        yazi_boyutu=9,
    )
    pdf.ln(4)

    genel_kdv = sum((f["kdv"] or 0) for f in faturalar)
    eksik_kdv = sum((r["kdv"] or 0) for r in sonuc_satirlari if r["durum"] == DURUM_CETVELDE_YOK)
    fazla_kdv = sum((r["kdv"] or 0) for r in sonuc_satirlari if r["durum"] == DURUM_FATURADA_YOK)
    fark_kdv = sum((r["kdv"] or 0) for r in sonuc_satirlari if r["durum"] == DURUM_TUTAR_FARKI)
    eslesen_kdv = sum((r["kdv"] or 0) for r in sonuc_satirlari if r["durum"] == DURUM_OK)

    pdf.set_font("tr", "B", 11)
    pdf.cell(0, 7, "KDV TUTARLARI (TL)", new_x="LMARGIN", new_y="NEXT")
    kdv_satirlari = [
        ["Tüm faturaların toplam KDV'si", tl_format(genel_kdv), None],
        ["Eşleşen faturaların toplam KDV'si", tl_format(eslesen_kdv), YESIL],
        ["Muavinde olmayan faturaların KDV'si (EKSİK)", tl_format(eksik_kdv), KIRMIZI],
        ["XML'de olmayan muavin KDV'si (FAZLA)", tl_format(fazla_kdv), KIRMIZI],
        ["Tutar farkı olan kayıtların KDV'si", tl_format(fark_kdv), SARI],
    ]
    f_tablo(
        ["Açıklama", "KDV (TL)"],
        [[a, v] for a, v, _ in kdv_satirlari],
        [80, 30],
        renkler={1: {i: r for i, (_, _, r) in enumerate(kdv_satirlari) if r}},
        yazi_boyutu=9,
    )
    pdf.ln(4)

    pdf.set_font("tr", "B", 11)
    pdf.cell(0, 7, "SATICI BAZINDA MUAVİNDE OLMAYAN KDV (EKSİK)", new_x="LMARGIN", new_y="NEXT")
    eksik_satici = {}
    for r in sonuc_satirlari:
        if r["durum"] == DURUM_CETVELDE_YOK and r.get("kdv"):
            g = eksik_satici.setdefault((r["vkn"], r["unvan"]), {"adet": 0, "kdv": 0})
            g["adet"] += 1
            g["kdv"] += r["kdv"]
    satici_satirlari = []
    for (vkn, unvan), g in sorted(eksik_satici.items(), key=lambda x: -x[1]["kdv"]):
        if not vkn and not unvan:
            continue
        satici_satirlari.append([
            unvan or vkn, vkn or "-", g["adet"], tl_format(g["kdv"]),
        ])
    if satici_satirlari:
        f_tablo(
            ["Satıcı Ünvanı", "VKN", "Fatura Adedi", "Eksik KDV (TL)"],
            satici_satirlari,
            [70, 30, 18, 25],
            yazi_boyutu=8.5,
        )
    else:
        pdf.set_font("tr", "", 9)
        pdf.cell(0, 6, "Yok", new_x="LMARGIN", new_y="NEXT")

    # Son kontrole göre değişim
    if gecmis_bilgi:
        pdf.ln(4)
        pdf.set_font("tr", "B", 11)
        pdf.cell(0, 7, "SON KONTROLE GÖRE DEĞİŞİM", new_x="LMARGIN", new_y="NEXT")
        degisim_satirlari = []
        if gecmis_bilgi.get("kapanan"):
            degisim_satirlari.append([
                "Bu ay muavine eklenen belgeler (çözüldü)", f"{len(gecmis_bilgi['kapanan'])} adet", YESIL,
            ])
        if gecmis_bilgi.get("yeni"):
            degisim_satirlari.append([
                "Bu ay yeni ortaya çıkan eksikler", f"{len(gecmis_bilgi['yeni'])} adet", KIRMIZI,
            ])
        if gecmis_bilgi.get("onceki_eslesen") is not None:
            degisim_satirlari.append(["Önceki eşleşen adedi", gecmis_bilgi["onceki_eslesen"], None])
        if gecmis_bilgi.get("zaman"):
            degisim_satirlari.append(["Önceki kontrol zamanı", gecmis_bilgi["zaman"], None])
        if degisim_satirlari:
            f_tablo(
                ["Açıklama", "Değer"],
                [[a, v] for a, v, _ in degisim_satirlari],
                [80, 30],
                renkler={1: {i: r for i, (_, _, r) in enumerate(degisim_satirlari) if r}},
                yazi_boyutu=9,
            )

    # ---------- Sayfa 2+: Eksik Faturalar ----------
    eksik = [r for r in sonuc_satirlari if r["durum"] == DURUM_CETVELDE_YOK]
    if eksik:
        yeni_sayfa(manzara=True)
        pdf.baslik_koy("EKSİK FATURALAR (MUAVİNDE KAYDI YOK)")
        satirlar = []
        for r in sorted(eksik, key=lambda x: (str(x.get("tarih") or ""), str(x["belge_no"]))):
            satirlar.append([
                r.get("tarih") or "", r["belge_no"] or "", r.get("tip") or "",
                r["vkn"] or "", r["unvan"] or "",
                tl_format(r.get("matrah")), tl_format(r.get("kdv")),
                tl_format(r.get("toplam")),
                ", ".join(f"%{o}%" for o in r.get("oranlar") or []),
            ])
        toplam_matrah = sum((r["matrah"] or 0) for r in eksik)
        toplam_kdv = sum((r["kdv"] or 0) for r in eksik)
        satirlar.append(["", "TOPLAM", "", "", "", tl_format(toplam_matrah), tl_format(toplam_kdv), "", ""])
        f_tablo(
            ["Tarih", "Belge No", "Tip", "VKN", "Satıcı Ünvanı", "Matrah", "KDV", "Toplam", "Oran"],
            satirlar,
            [18, 34, 22, 22, 50, 22, 22, 22, 16],
            yazi_boyutu=7.5,
            toplam_satir_idx=len(satirlar) - 1,
            sola_kolonlar={4},
        )

    # ---------- Sayfa 3+: Sonuçlar ----------
    yeni_sayfa(manzara=True)
    pdf.baslik_koy("SONUÇLAR (TÜM KAYITLAR)")
    satirlar = []
    satir_renkleri = {}
    for i, r in enumerate(sonuc_satirlari):
        satirlar.append([
            DURUM_ADLARI.get(r["durum"], r["durum"]),
            r["belge_no"] or "", r["vkn"] or "", r["unvan"] or "",
            r["tarih"] or "", r.get("tip") or "",
            tl_format(r.get("matrah")), tl_format(r.get("kdv")),
            ", ".join(f"%{o}%" for o in r.get("oranlar") or []),
            r.get("oran_kontrol") or "",
        ])
        satir_renkleri[i] = DURUM_RENK.get(r["durum"])
    f_tablo(
        ["Durum", "Belge No", "VKN", "Satıcı/Ünvan", "Tarih", "Tip", "Matrah", "KDV", "Oran", "Oran Kontrol"],
        satirlar,
        [22, 32, 20, 50, 16, 20, 20, 20, 15, 15],
        renkler={"_satir": satir_renkleri},
        yazi_boyutu=7,
        sola_kolonlar={3},
    )

    # ---------- Sayfa 4+: Fazla Muavin ----------
    fazla = [r for r in sonuc_satirlari if r["durum"] == DURUM_FATURADA_YOK]
    if fazla:
        yeni_sayfa(manzara=True)
        pdf.baslik_koy("FAZLA MUAVİN KAYITLARI (FATURALARDA YOK)")
        satirlar = []
        for r in sorted(fazla, key=lambda x: (str(x.get("tarih") or ""), str(x["belge_no"]))):
            satirlar.append([
                r.get("tarih") or "", r["belge_no"] or "", r["unvan"] or "",
                tl_format(r.get("kdv")),
            ])
        satirlar.append(["", "TOPLAM", "", tl_format(sum((r["kdv"] or 0) for r in fazla))])
        f_tablo(
            ["Tarih", "Belge No", "Ünvan", "KDV"],
            satirlar,
            [22, 40, 90, 24],
            yazi_boyutu=8,
            toplam_satir_idx=len(satirlar) - 1,
            sola_kolonlar={2},
        )

    # ---------- Sayfa 5+: Tutar/VKN Farkları ----------
    farklar = [r for r in sonuc_satirlari if r["durum"] in (DURUM_TUTAR_FARKI, DURUM_VKN_FARKI, DURUM_MUKERRER)]
    if farklar:
        yeni_sayfa(manzara=True)
        pdf.baslik_koy("TUTAR / VKN FARKLARI VE MÜKERRERLER")
        satirlar = []
        for r in farklar:
            satirlar.append([
                DURUM_ADLARI.get(r["durum"], r["durum"]),
                r["belge_no"] or "", r["vkn"] or "", r["unvan"] or "",
                r["tarih"] or "", tl_format(r.get("kdv")),
                (r["detay"] or "")[:80],
            ])
        f_tablo(
            ["Durum", "Belge No", "VKN", "Ünvan", "Tarih", "KDV", "Detay"],
            satirlar,
            [24, 36, 22, 50, 18, 22, 65],
            yazi_boyutu=7.5,
            sola_kolonlar={3, 6},
        )

    # ---------- Sayfa 6+: Satıcı Özeti ----------
    yeni_sayfa(manzara=True)
    pdf.baslik_koy("SATICI ÖZETİ")
    saticilar = {}
    for f in faturalar:
        anahtar = (f.get("satici_vkn") or "", f.get("satici_unvan") or "")
        g = saticilar.setdefault(anahtar, {"adet": 0, "matrah": 0, "kdv": 0, "eslesen": 0, "eksik": 0, "eksik_kdv": 0})
        g["adet"] += 1
        g["matrah"] += f["matrah"] or 0
        g["kdv"] += f["kdv"] or 0
    eslesen_belge = {r["belge_no"] for r in sonuc_satirlari if r["durum"] == DURUM_OK}
    for f in faturalar:
        g = saticilar.get((f.get("satici_vkn") or "", f.get("satici_unvan") or ""))
        if g is None:
            continue
        if (f["belge_no"] or "") in eslesen_belge:
            g["eslesen"] += 1
        else:
            g["eksik"] += 1
            g["eksik_kdv"] += f["kdv"] or 0
    satirlar = []
    satir_renkleri = {}
    for i, ((vkn, unvan), g) in enumerate(sorted(saticilar.items(), key=lambda x: -x[1]["eksik_kdv"])):
        if not vkn and not unvan:
            continue
        satirlar.append([
            vkn or "", unvan or "", g["adet"], g["eslesen"], g["eksik"],
            tl_format(g["matrah"]), tl_format(g["kdv"]), tl_format(g["eksik_kdv"]),
        ])
        if g["eksik"]:
            satir_renkleri[i] = KIRMIZI
    f_tablo(
        ["VKN", "Satıcı Ünvanı", "Fatura Adedi", "Eşleşen", "Muavinde Yok", "Toplam Matrah", "Toplam KDV", "Eksik KDV (TL)"],
        satirlar,
        [24, 55, 16, 14, 18, 22, 22, 22],
        renkler={"_satir": satir_renkleri},
        yazi_boyutu=7.5,
        sola_kolonlar={1},
    )

    # ---------- Sayfa 7+: KDV Dağılımı ----------
    yeni_sayfa(manzara=True)
    pdf.baslik_koy("KDV DAĞILIMI")

    pdf.set_font("tr", "B", 10.5)
    pdf.cell(0, 7, "MUAVİN 191 HESAP KDV DAĞILIMI", new_x="LMARGIN", new_y="NEXT")
    muavin_dagilim = kdv_dagilim_muavin(cetvel_kayitlari)
    satirlar = []
    toplam = 0
    for hesap, g in sorted(muavin_dagilim.items(), key=lambda x: -x[1]["kdv"]):
        satirlar.append([hesap, g["adet"], tl_format(g["kdv"])])
        toplam += g["kdv"]
    if satirlar:
        satirlar.append(["TOPLAM", sum(x[1] for x in satirlar), tl_format(toplam)])
    f_tablo(
        ["Hesap", "Kayıt Adedi", "KDV Toplamı (TL)"],
        satirlar,
        [80, 30, 45],
        yazi_boyutu=8.5,
        toplam_satir_idx=len(satirlar) - 1,
        sola_kolonlar={0},
    )
    pdf.ln(5)

    pdf.set_font("tr", "B", 10.5)
    pdf.cell(0, 7, "XML/PDF FATURA KDV DAĞILIMI", new_x="LMARGIN", new_y="NEXT")
    fatura_dagilim = kdv_dagilim_fatura(faturalar)
    satirlar = []
    toplam = 0
    toplam_matrah = 0
    for oran, g in sorted(fatura_dagilim.items(), key=lambda x: x[0] if isinstance(x[0], int) else 999):
        oran_ad = f"%{oran}%" if isinstance(oran, int) else (oran or "Bilinmiyor")
        satirlar.append([oran_ad, g["adet"], tl_format(g["matrah"]), tl_format(g["kdv"])])
        toplam += g["kdv"]
        toplam_matrah += g["matrah"]
    if satirlar:
        satirlar.append(["TOPLAM", sum(x[1] for x in satirlar), tl_format(toplam_matrah), tl_format(toplam)])
    f_tablo(
        ["Oran", "Fatura Adedi", "Matrah Toplamı (TL)", "KDV Toplamı (TL)"],
        satirlar,
        [40, 25, 35, 35],
        yazi_boyutu=8.5,
        toplam_satir_idx=len(satirlar) - 1,
        sola_kolonlar={0},
    )

    # ---------- Sayfa 8+: Ba Formu ----------
    yeni_sayfa(manzara=True)
    pdf.baslik_koy("BA FORMU (MAL/HİZMET ALIŞ BİLDİRİMİ)")
    satirlar = []
    toplam_adet = 0
    toplam_matrah = 0
    toplam_kdv = 0
    for s in ba_formu(faturalar):
        satirlar.append([
            s["vkn"] or "", s["unvan"] or "", s["adet"],
            tl_format(s["matrah"]), tl_format(s["kdv"]),
        ])
        toplam_adet += s["adet"]
        toplam_matrah += s["matrah"]
        toplam_kdv += s["kdv"]
    if satirlar:
        satirlar.append(["", "TOPLAM", toplam_adet, tl_format(toplam_matrah), tl_format(toplam_kdv)])
    f_tablo(
        ["VKN", "Satıcı Ünvanı", "Fatura Adedi", "Matrah Toplamı (TL)", "KDV Toplamı (TL)"],
        satirlar,
        [30, 70, 22, 32, 32],
        yazi_boyutu=8.5,
        toplam_satir_idx=len(satirlar) - 1,
        sola_kolonlar={1},
    )

    pdf.output(hedef_yol)
    return hedef_yol
