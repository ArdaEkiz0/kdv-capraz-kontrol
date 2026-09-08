"""README icin uygulama ana penceresinin gorsel maketini uretir."""
import os
from PIL import Image, ImageDraw, ImageFont

YOL = os.path.dirname(os.path.abspath(__file__))
G = 1280
Y = 800

MAVI = (37, 99, 235)
MAVI_KOYU = (29, 78, 216)
MOR = (124, 58, 237)
BG = (245, 247, 251)
KART = (255, 255, 255)
BORDER = (219, 226, 239)
METIN = (30, 41, 59)
IKINCIL = (100, 116, 139)
YESIL_Z = (209, 250, 229)
YESIL_Y = (6, 95, 70)
KIRMIZI_Z = (254, 226, 226)
KIRMIZI_Y = (153, 27, 27)
MAVI_Z = (219, 234, 254)
MAVI_Y = (30, 64, 175)
GRİ_Z = (238, 242, 247)
SARI_Z = (255, 235, 156)


def font(boyut, kalin=False):
    ad = "segoeuib.ttf" if kalin else "segoeui.ttf"
    try:
        return ImageFont.truetype(os.path.join(r"C:\Windows\Fonts", ad), boyut)
    except OSError:
        return ImageFont.load_default()


def rct(ciz, kutu, r, **kw):
    ciz.rounded_rectangle(kutu, radius=r, **kw)


def uret():
    img = Image.new("RGB", (G, Y), BG)
    ciz = ImageDraw.Draw(img)

    baslik_f = font(21, True)
    f11 = font(11)
    f12 = font(12)
    f13 = font(13)
    f14b = font(14, True)
    f16b = font(16, True)

    # ---- Ust serit ----
    ciz.rectangle([0, 0, G, 54], fill=MAVI)
    logo = Image.open(os.path.join(YOL, "logo.png")).resize((36, 36))
    img.paste(logo, (14, 9), logo)
    ciz.text((62, 15), "KDV Çapraz Kontrol", font=baslik_f, fill=(255, 255, 255))
    rct(ciz, [288, 14, 372, 40], 6, fill=MOR)
    tw = ciz.textlength(" v2.8.2 ", font=f12)
    ciz.text((330 - tw / 2, 18), " v2.8.2 ", font=f12, fill=(255, 255, 255))
    akis = "Fatura seç  →  Cetvel seç  →  Kontrolü Başlat  →  Excel/PDF raporu"
    tw = ciz.textlength(akis, font=f12)
    ciz.text((G - tw - 16, 19), akis, font=f12, fill=(191, 219, 254))

    # ---- Islem karti ----
    rct(ciz, [10, 66, G - 10, 152], 10, fill=KART, outline=BORDER)
    for i, metin in enumerate(["Fatura Dosyaları Seç", "Fatura Klasörü Seç", "Kontrol Cetveli Seç"]):
        x1 = 24 + i * 200
        rct(ciz, [x1, 80, x1 + 188, 110], 6, fill=KART, outline=BORDER)
        tw = ciz.textlength(metin, font=f12)
        ciz.text((x1 + 94 - tw / 2, 88), metin, font=f12, fill=METIN)
    rct(ciz, [G - 262, 78, G - 24, 112], 8, fill=MAVI)
    tw = ciz.textlength("KONTROLÜ BAŞLAT", font=f14b)
    ciz.text((G - 143 - tw / 2, 86), "KONTROLÜ BAŞLAT", font=f14b, fill=(255, 255, 255))
    ciz.text((24, 122), "Fatura: faturalar klasörü (445 dosya)  |  Cetvel: cetvel1.xlsx + cetvel2.xlsx",
             font=f11, fill=IKINCIL)

    # ---- Arac cubugu ----
    araclar = ["🔧 Veri İncele", "📊 Dashboard", "🔎 Filtre", "|", "Beyanname", "📂 Klasör Cetvel",
               "|", "Ba/Bs Formu", "Excel Raporu", "PDF Raporu", "Mail"]
    x = 20
    for metin in araclar:
        if metin == "|":
            ciz.line([x, 168, x, 192], fill=BORDER)
            x += 12
            continue
        tw = ciz.textlength(metin, font=f12)
        rct(ciz, [x, 162, x + tw + 20, 198], 5, fill=KART, outline=BORDER)
        ciz.text((x + 10, 172), metin, font=f12, fill=METIN)
        x += int(tw) + 26

    # ---- Tablo karti ----
    rct(ciz, [10, 208, G - 10, 604], 10, fill=KART, outline=BORDER)
    ciz.text((24, 218), "Sonuçlar", font=f16b, fill=METIN)
    for i, (metin, secili) in enumerate([("Tümü", True), ("Sorunlu", False), ("Eşleşen", False)]):
        ox = 900 + i * 90
        ciz.ellipse([ox, 222, ox + 12, 234], outline=IKINCIL,
                    fill=MAVI if secili else KART)
        ciz.text((ox + 18, 220), metin, font=f12, fill=METIN)
    ciz.text((1180, 220), "Dönem:", font=f12, fill=IKINCIL)
    rct(ciz, [1236, 218, 1266, 238], 4, fill=GRİ_Z, outline=BORDER)

    kolonlar = [("Durum", 24), ("Belge No", 130), ("VKN", 320), ("Tarih", 450),
                ("Tip", 550), ("Matrah", 650), ("KDV", 790), ("Kaynak", 900), ("Detay", 1010)]
    ciz.rectangle([18, 246, G - 18, 276], fill=(238, 242, 255))
    for ad_, x_ in kolonlar:
        ciz.text((x_, 252), ad_, font=f13, fill=METIN)

    satir_renkleri = {
        "CETVELDE YOK": (KIRMIZI_Z, KIRMIZI_Y),
        "EŞLEŞTİ": (YESIL_Z, YESIL_Y),
        "TEVKİFATLI": (MAVI_Z, MAVI_Y),
        "TUTAR FARKI": (KIRMIZI_Z, KIRMIZI_Y),
    }
    veriler = [
        ("TUTAR FARKI", "FTR2026000001011", "1111111111", "2026-07-27", "SATIS", "90,00", "18,00", "Kdv: Fatura: 18,00 | Cetvel: 984,16"),
        ("CETVELDE YOK", "FTR2026000001022", "2222222222", "2026-08-15", "SATIS", "12.116,88", "2.423,38", "Cetvelde kaydı yok"),
        ("CETVELDE YOK", "FTR2026000001033", "3333333333", "2026-08-05", "SATIS", "31.250,00", "312,50", "Cetvelde kaydı yok"),
        ("EŞLEŞTİ", "FTR2026000001044", "4444444444", "2026-08-01", "SATIS", "30.000,00", "6.000,00", "Tam eşleşme"),
        ("EŞLEŞTİ", "FTR2026000001055", "5555555555", "2026-08-01", "SATIS", "93.600,00", "18.720,00", "Tam eşleşme"),
        ("TEVKİFATLI", "FTR2026000001066", "6666666666", "2026-08-09", "SATIS", "12.400,00", "2.480,00", "Muavin %70 tevkifat sonrası ≈ eşleşti"),
        ("TEVKİFATLI", "FTR2026000001077", "7777777777", "2026-08-11", "SATIS", "8.300,00", "1.660,00", "Muavin %70 tevkifat sonrası ≈ eşleşti"),
        ("EŞLEŞTİ", "FTR2026000001088", "8888888888", "2026-08-12", "SATIS", "5.105,10", "1.021,02", "Tam eşleşme"),
        ("EŞLEŞTİ", "FTR2026000001099", "9999999999", "2026-08-14", "IADE", "-1.200,00", "-240,00", "İade eşleşti"),
        ("EŞLEŞTİ", "FTR2026000001110", "1212121212", "2026-08-18", "SATIS", "760,40", "7,60", "Tam eşleşme"),
    ]
    y0 = 276
    for i, (durum, belge, vkn, tarih, tip, matrah, kdv, detay) in enumerate(veriler):
        zemin, yazı = satir_renkleri.get(durum, (KART, METIN))
        yy = y0 + i * 32
        ciz.rectangle([18, yy, G - 18, yy + 32], fill=zemin)
        ciz.text((24, yy + 8), durum, font=f12, fill=yazı)
        ciz.text((130, yy + 8), belge, font=f12, fill=METIN)
        ciz.text((320, yy + 8), vkn, font=f12, fill=METIN)
        ciz.text((450, yy + 8), tarih, font=f12, fill=METIN)
        ciz.text((550, yy + 8), tip, font=f12, fill=METIN)
        twm = ciz.textlength(matrah, font=f12)
        ciz.text((650 + 130 - twm, yy + 8), matrah, font=f12, fill=METIN)
        twk = ciz.textlength(kdv, font=f12)
        ciz.text((790 + 100 - twk, yy + 8), kdv, font=f12, fill=METIN)
        ciz.text((900, yy + 8), "Fatura", font=f12, fill=METIN)
        ciz.text((1010, yy + 8), detay, font=f12, fill=METIN)

    # ---- Ozet kartlari ----
    kartlar = [
        ("244", "EŞLEŞEN", YESIL_Z, YESIL_Y),
        ("159", "SORUNLU", KIRMIZI_Z, KIRMIZI_Y),
        ("1", "TUTAR FARKI", KIRMIZI_Z, KIRMIZI_Y),
        ("148", "CETVELDE YOK", KIRMIZI_Z, KIRMIZI_Y),
        ("10", "FATURADA YOK", KIRMIZI_Z, KIRMIZI_Y),
        ("0", "MÜKERRER", GRİ_Z, IKINCIL),
        ("39", "İNDİRİMLİ", MAVI_Z, MAVI_Y),
        ("23", "TEVKİFATLI", MAVI_Z, MAVI_Y),
        ("441", "FATURA", GRİ_Z, IKINCIL),
        ("290", "CETVEL", GRİ_Z, IKINCIL),
    ]
    x = 20
    for deger_, ad_, arka, yazi in kartlar:
        gen = 108
        rct(ciz, [x, 616, x + gen, 686], 8, fill=arka)
        twd = ciz.textlength(deger_, font=f16b)
        ciz.text((x + gen / 2 - twd / 2, 626), deger_, font=f16b, fill=yazi)
        twa = ciz.textlength(ad_, font=font(9))
        ciz.text((x + gen / 2 - twa / 2, 656), ad_, font=font(9), fill=yazi)
        x += gen + 8

    # ---- Gunluk ----
    rct(ciz, [10, 700, G - 10, 790], 10, fill=KART, outline=BORDER)
    ciz.text((24, 710), "[1/446] Fatura okunuyor: FTR2026000001011.xml", font=f12, fill=IKINCIL)
    ciz.text((24, 732), "[446/446] Cetvel okunuyor: cetvel2.xlsx", font=f12, fill=IKINCIL)
    ciz.text((24, 754), "Kontrol tamamlandı: 452 sonuç satırı.", font=f12, fill=YESIL_Y)

    img.save(os.path.join(YOL, "screenshot.png"))
    print("screenshot.png yenilendi:", img.size)


if __name__ == "__main__":
    uret()
