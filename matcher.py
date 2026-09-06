from decimal import Decimal
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher
import re

from utils import tl_format, vkn_gecerli_mi
from kurallar import beklenen_oran, kural_bul

TOLERANS = Decimal("0.02")

DURUM_OK = "EŞLEŞTİ"
DURUM_TUTAR_FARKI = "TUTAR FARKI"
DURUM_VKN_FARKI = "VKN FARKI"
DURUM_KDV_SIFIR = "KDV 0"
DURUM_CETVELDE_YOK = "CETVELDE YOK"
DURUM_FATURADA_YOK = "FATURALARDA YOK"
DURUM_MUKERRER = "MÜKERRER"
DURUM_PARSE_SORUNU = "PARSE SORUNU"
DURUM_TEVKIFATLI = "TEVKİFATLI"
DURUM_INDIRIMLI = "İNDİRİMLİ"
DURUM_ONAYLI = "ONAYLI FARK"

# Faturanın KDV/matrahının muavin defterine tevkifat sonrası düşülen oranları.
# Örn. %30 tevkifat -> muavinde %70 (0.70) kayıtlı; akaryakıt %5 -> 0.95.
# Gerçek uygulamada gördüğün oranları: 0.70 (otömotiv/şarj/akaryakıt %30 tevk),
# 0.95 (akaryakıt %5). Düşkün oranları (0.9/0.8/0.5 vb.) tutar farklıdan
# ayırt etmek için katılmamıştır.
# Muavin KDV'sinin fatura KDV'sine oranı (klasik yön: fatura tam KDV,
# muavinde tevkifat sonrası kalan kısım kayıtlı).
# %20 -> 0.80, %30 -> 0.70, %40 -> 0.60, %50 -> 0.50, %60 -> 0.40,
# %70 -> 0.30, %80 -> 0.20, %90 -> 0.10, %10 -> 0.90, %5 -> 0.95
# Klasik yön (fatura tam KDV, muavinde kalan). 0.80(%20) ve 0.90(%10)
# kasıtlı dışarıda: bunlar KDV oran farkı senaryolarıyla karışabilir;
# %20 tevkifat zaten TERS yönde (1.25 çarpanı) yakalanıyor.
TEVKIFAT_ORANLARI = (Decimal("0.70"), Decimal("0.60"),
                     Decimal("0.50"), Decimal("0.40"), Decimal("0.30"),
                     Decimal("0.20"), Decimal("0.10"), Decimal("0.95"))

# Ters yön: fatura özeti TEVKİFAT SONRASI KDV'yi gösterir (Luca/GİB özetinde
# sık görülür), muavin fişinde ise KDV'nin TAMAMI yazılıdır. Bu durumda
# muavin/fatura oranı = 1/(1-t) çıkar: %20 -> 1.25, %30 -> 1.4286,
# %40 -> 1.6667, %50 -> 2.0, %60 -> 2.5, %70 -> 3.3333, %90 -> 10.0
# Ters yön çarpanları: fatura özeti tevkifat SONRASI KDV gösterir, muavin
# tam KDV içerir. Yaygın Türkiye KDV tevkifat oranlarından türetildi:
#   %10 -> 1.1111, %20 -> 1.25, %30 -> 1.4286, %33(2/3) -> 1.5,
#   %40 -> 1.6667, %50 -> 2.0, %60 -> 2.5, %70 -> 3.3333, %80 -> 5.0,
#   %90 -> 10.0
TEVKIFAT_CARPANLARI = (Decimal("1.25"), Decimal("1.4286"), Decimal("1.5"),
                       Decimal("1.667"), Decimal("2.0"), Decimal("2.5"),
                       Decimal("3.333"), Decimal("5.0"), Decimal("10.0"),
                       Decimal("1.1111"), Decimal("1.0526"))

SORUNLU_DURUMLAR = (
    DURUM_TUTAR_FARKI, DURUM_VKN_FARKI, DURUM_KDV_SIFIR, DURUM_CETVELDE_YOK,
    DURUM_FATURADA_YOK, DURUM_MUKERRER, DURUM_PARSE_SORUNU,
)


def vkn_uyumlu(f, c):
    f_vkn = f.get("satici_vkn") or ""
    c_vkn = c.get("vkn") or ""
    if not f_vkn or not c_vkn:
        return True
    return f_vkn == c_vkn


def tutarlar_uyumlu(f, c):
    for alan in ("matrah", "kdv"):
        f_deger = f.get(alan)
        c_deger = c.get(alan)
        if f_deger is not None and c_deger is not None:
            if alan == "kdv" and (f.get("fatura_tipi") or f.get("tip") or "").upper() == "IADE":
                f_deger = abs(f_deger)
            if abs(f_deger - c_deger) > TOLERANS:
                return False
    return True


def fark_metni(f_alan, c_alan):
    f_deger = "" if f_alan is None else f"{f_alan:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    c_deger = "" if c_alan is None else f"{c_alan:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"Fatura: {f_deger} | Cetvel: {c_deger}"


def duplikat_bul(liste, anahtar_fonksiyonu):
    sayac = defaultdict(int)
    for oge in liste:
        sayac[anahtar_fonksiyonu(oge)] += 1
    return {a: n for a, n in sayac.items() if n > 1}


def _tutar_esit(a, b):
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(a - b) < TOLERANS


def _oran_yaklasik(f_deger, c_deger, hedef):
    """f_deger'in c_deger'e oranı hedef tevkifat oranına yakın mı?"""
    if f_deger is None or c_deger is None:
        return False
    if f_deger == 0:
        return False
    oran = Decimal(str(c_deger)) / Decimal(str(f_deger))
    hedef_d = Decimal(str(hedef))
    return abs(oran - hedef_d) <= Decimal("0.02")


def tevkifat_kes(f, c, ek_oran=None):
    """Fatura ile cetvel KDV/matrahı tevkifat oranıyla ilişkiliyse oranı döndürür, yoksa None.

    İki yönlü denetim:
    1) Klasik: fatura tam KDV taşır, muavinde tevkifat sonrası kalan
       (# oranı TEVKIFAT_ORANLARI).
    2) Ters: fatura özeti tevkifat SONRASI KDV gösterir (Luca/GİB özet
       Excel'inde yaygın), muavinde KDV'nin TAMAMI kayıtlıdır
       (çarpım oranı TEVKIFAT_CARPANLARI). Bu durumda pozitif oran
       döner; tevkifat_oranı = 1 - 1/carpan.
    ek_oran: firma kuralından gelen özel kabul oranı (varsayılanların yanında denenir).

    YANLIŞ-POZİTİF KORUMASI:
    Sadece KDV oranı değil, MATRAH oranı da tevkifatla tutarlı olmalı.
    Eczane/ilaç faturalarında KDV 1.25 çarpanına yakın görünebilir ama
    matrah oranı (1:1 ya da tamsayı) farklıdır -> tevkifat sayılmaz.
    TEVKİFAT GATE (kullanıcı kuralı): tevkifat faturadan bilinmedikçe
    muavin KDV-oranı tek başına tevkifat üretmez. Faturanın kendi tipi
    "TEVKIFAT" (veya fatura_tevkifatli bayrağı) yoksa bu işlev None döner.
    Fatura tipi boş (özet-xlsx kaynağı) ise eski davranış korunur.
    """
    ft = str((f or {}).get("fatura_tipi") or "").strip().upper()
    if ft and ft != "TEVKIFAT" and not (f or {}).get("fatura_tevkifatli"):
        return None
    f_kdv = f.get("kdv")
    c_kdv = c.get("kdv")
    f_matrah = f.get("matrah")
    c_matrah = c.get("matrah")
    if f_kdv is None or c_kdv is None or f_kdv == 0:
        return None

    oranlar = TEVKIFAT_ORANLARI + ((ek_oran,) if ek_oran is not None else ())
    for oran in oranlar:
        if _oran_yaklasik(f_kdv, c_kdv, oran):
            # Klasik yön: fatura tam KDV; matrah da aynı oranda düşmüş olmalı
            # (f_matrah / c_matrah ≈ oran). Matrah bilinmiyorsa kabul et.
            if f_matrah is not None and c_matrah is not None and c_matrah != 0:
                if abs(Decimal(str(f_matrah)) / Decimal(str(c_matrah))
                       - Decimal(str(oran))) <= Decimal("0.03"):
                    return oran
            else:
                return oran
        # Matrah oranı kontrolüyle yakalanan (matrah yoksa sadece kdv)
        if f_matrah is not None and c_matrah is not None and c_matrah != 0:
            if abs(Decimal(str(f_matrah)) / Decimal(str(c_matrah))
                   - Decimal(str(oran))) <= Decimal("0.03") \
                    and _oran_yaklasik(f_kdv, c_kdv, oran):
                return oran

    # Ters yön: muavin > fatura özeti KDV'si
    carpanlar = TEVKIFAT_CARPANLARI + \
        ((1 / (Decimal("1") - ek_oran),) if ek_oran is not None
         and ek_oran != 1 else ())
    for carpan in carpanlar:
        if _oran_yaklasik(f_kdv, c_kdv, carpan):
            # Ters yönde matrah: muavin matrahı / özet matrahı ≈ carpan
            if f_matrah is not None and c_matrah is not None and f_matrah != 0:
                if abs(Decimal(str(c_matrah)) / Decimal(str(f_matrah))
                       - Decimal(str(carpan))) <= Decimal("0.03"):
                    return float(carpan)
            else:
                return float(carpan)
    return None


def tevkifat_detay(f, c, oran):
    parcalar = []
    for alan in ("matrah", "kdv"):
        f_deger = f.get(alan)
        c_deger = c.get(alan)
        if f_deger is not None and c_deger is not None:
            parcalar.append(alan.capitalize() + ": " + fark_metni(f_deger, c_deger))
    f_kdv = f.get("kdv")
    c_kdv = c.get("kdv")
    ters = bool(oran and Decimal(str(oran)) > 1)
    if ters:
        # Ters yön: fatura özeti tevkifat sonrası gösterir, muavin tam KDV
        tevkifat_oran = 1 - 1 / Decimal(str(oran))
        t_yuzde = int(round(tevkifat_oran * 100))
        temel = " | ".join(parcalar)
        if f_kdv and c_kdv:
            return (temel + f" | Fatura tevkifatlı (≈%{t_yuzde} tevkifat; "
                    f"muavin tam KDV {float(c_kdv):,.2f} | özet {float(f_kdv):,.2f})")
        return temel + f" | Tevkifatlı fatura (≈%{t_yuzde} tevkifat)"
    bant_yuzde = int(round((1 - oran) * 100))
    if f_kdv and c_kdv is not None:
        kayitli = float(c_kdv / f_kdv * 100)
        return (" | ".join(parcalar)
                + f" | Muavin'de fatura KDV'sinin %{kayitli:.1f}'i kayıtlı"
                + f" (tevkifat/kısmi kayıt bandı: %{bant_yuzde})")
    return (" | ".join(parcalar) + f" | Muavin KDV tevkifatlı (≈%{bant_yuzde} düşülmüş)")



def _tarih_gun_farki(a, b):
    try:
        da = datetime.strptime(str(a or "")[:10], "%Y-%m-%d")
        db = datetime.strptime(str(b or "")[:10], "%Y-%m-%d")
        return abs((da - db).days)
    except Exception:
        return None


def _aday_puani(a_vkn, a_belge, a_tarih, a_matrah, a_kdv,
                b_vkn, b_belge, b_tarih, b_matrah, b_kdv):
    puan = 0
    vkn_esit = bool(a_vkn and b_vkn and str(a_vkn) == str(b_vkn))
    if vkn_esit:
        puan += 3
    benzerlik = 0.0
    if a_belge and b_belge:
        benzerlik = SequenceMatcher(None, str(a_belge).upper(), str(b_belge).upper()).ratio()
        if benzerlik >= 0.85:
            puan += 3
        elif benzerlik >= 0.65:
            puan += 2
        elif benzerlik >= 0.50:
            puan += 1
    if _tutar_esit(a_matrah, b_matrah):
        puan += 1
    if _tutar_esit(a_kdv, b_kdv):
        puan += 1
    gun = _tarih_gun_farki(a_tarih, b_tarih)
    if gun is not None and gun <= 7:
        puan += 1
    return puan, benzerlik, vkn_esit


OLASI_ESLESME_ESIK = 6


def olasilari_isaretle(sonuc_satirlari, faturalar, cetvel_kayitlari):
    """Sorunlu satirlara 'olası eşleşme' önerisi ve VKN kontrol hanesi uyarısı ekler."""
    for r in sonuc_satirlari:
        vkn = str(r.get("vkn") or "").strip()
        detay = r.get("detay") or ""
        if len(vkn) in (10, 11) and vkn.isdigit() and not vkn_gecerli_mi(vkn) \
                and "kontrol hanesi" not in detay:
            uyarı = "⚠ VKN kontrol hanesi geçersiz (yanlış okunmuş olabilir)"
            r["detay"] = (detay + " | " + uyarı) if detay else uyarı

    eksik_faturalar = [r for r in sonuc_satirlari if "CETVELDE YOK" in r["durum"]]
    eksik_cetveller = [r for r in sonuc_satirlari if r["durum"] == DURUM_FATURADA_YOK]
    if not eksik_faturalar and not eksik_cetveller:
        return
    if len(eksik_faturalar) * max(1, len(cetvel_kayitlari)) > 500000 \
            or len(eksik_cetveller) * max(1, len(faturalar)) > 500000:
        return

    cetvel_veriler = [
        (str(c.get("vkn") or ""), c.get("belge_no"), c.get("tarih"),
         c.get("matrah"), c.get("kdv"), c)
        for c in cetvel_kayitlari if c.get("belge_no")
    ]
    for r in eksik_faturalar:
        en_iyi = None
        adet = 0
        for v, belge, tarih, matrah, kdv, c in cetvel_veriler:
            puan, sim, ve = _aday_puani(
                r.get("vkn"), r.get("belge_no"), r.get("tarih"), r.get("matrah"), r.get("kdv"),
                v, belge, tarih, matrah, kdv)
            if en_iyi is None or puan > en_iyi[0]:
                en_iyi = (puan, sim, ve, belge, tarih, kdv, c)
                adet = 1
            elif puan == en_iyi[0]:
                adet += 1
        if not en_iyi or en_iyi[0] < OLASI_ESLESME_ESIK:
            continue
        if not (en_iyi[2] or en_iyi[1] >= 0.50):
            continue
        c = en_iyi[6]
        metin = (f"Olası eşleşme: {en_iyi[3]} / {(c.get('unvan') or '?')[:40]}"
                 f" ({en_iyi[4] or 'tarih yok'}, KDV {tl_format(en_iyi[5])})")
        if adet > 1:
            metin += f" (+{adet - 1} benzer aday)"
        ek = " | " + metin
        r["detay"] = (r.get("detay") or "") + ek if r.get("detay") else metin

    fatura_veriler = [
        (str(f.get("satici_vkn") or ""), f.get("belge_no"), f.get("tarih"),
         f.get("matrah"), f.get("kdv"), f)
        for f in faturalar if f.get("belge_no")
    ]
    for r in eksik_cetveller:
        en_iyi = None
        adet = 0
        for v, belge, tarih, matrah, kdv, f in fatura_veriler:
            puan, sim, ve = _aday_puani(
                r.get("vkn"), r.get("belge_no"), r.get("tarih"), r.get("matrah"), r.get("kdv"),
                v, belge, tarih, matrah, kdv)
            if en_iyi is None or puan > en_iyi[0]:
                en_iyi = (puan, sim, ve, belge, tarih, kdv, f)
                adet = 1
            elif puan == en_iyi[0]:
                adet += 1
        if not en_iyi or en_iyi[0] < OLASI_ESLESME_ESIK:
            continue
        if not (en_iyi[2] or en_iyi[1] >= 0.50):
            continue
        f = en_iyi[6]
        metin = (f"Olası eşleşme: {en_iyi[3]} / {(f.get('satici_unvan') or '?')[:40]}"
                 f" ({en_iyi[4] or 'tarih yok'}, KDV {tl_format(en_iyi[5])})")
        if adet > 1:
            metin += f" (+{adet - 1} benzer aday)"
        ek = " | " + metin
        r["detay"] = (r.get("detay") or "") + ek if r.get("detay") else metin


def _harfler(metin):
    """Karşılaştırma için yalnız harf/rakam içerik döndürür."""
    import re as _re
    return _re.sub(r"[^\w]", "", (metin or "").upper())


def _satici_muavinde_var_mi(satici_metin, muavin_metinleri):
    """Satıcı unvanının anlamlı kelime kökü, muavin açıklamalarının
    herhangi birinde geçiyor mu? Hiç geçmiyorsa False -> fiş işlenmemiş."""
    if not satici_metin or not muavin_metinleri:
        return True  # bilinmiyor -> varsayımsal geçerli
    k = re.sub(r"[^A-ZÇĞİÖŞÜ0-9]", " ", satici_metin.upper()).split()
    # Jenerik/ortak kelimeler eşleşme sayılmaz (GIDA, SAN, TIC, LTD...)
    # bunlar her satıcıda geçtiği için yanlış pozitif üretir.
    GENEL = {"GIDA","SAN","TIC","LTD","STI","A","S","TURIZM","HIZMET",
         "PAZARLAMA","SANAYI","TICARET","TUKETIM","MALLARI","VE","LIMITED",
         "YURTICI","YURTDISI","TASIMACILIK","URUNLERI","GID","URN","TIC",
         "INSAA","İNSAA","INSAAT","İNŞAAT","NAKLIYAT","DAGITIM",
         "PAZ","TEM","KURUYEMIS","KURUMSAL","URUN","DONDU","TOPRAK",
         "ŞİRKETİ","SIRKETI","SATIS","SATIŞ","ANONIM","ANONİM",
         "MEŞRUBAT","MESRUBAT","GIDACILIK","ELEKTRONIK"}
    kelimeler = [x for x in k
                 if len(x) >= 4 and x not in GENEL and not x.isdigit()]
    if not kelimeler:
        return True  # ayırt edici kelime yok -> bilinemez, varsayımsal geçer
    for km in kelimeler:
        for m in muavin_metinleri:
            if km in m:
                return True
    return False


def capraz_kontrol(faturalar, cetvel_kayitlari, kurallar=None):
    def anahtar_fatura(f):
        return (f["belge_no"] or "").upper()

    def anahtar_cetvel(c):
        return (c.get("belge_no") or "").upper()

    def _kdv0_fatura(f):
        f_kdv = f.get("kdv")
        if f_kdv is None:
            return True
        if (f.get("fatura_tipi") or f.get("tip") or "").upper() == "IADE":
            f_kdv = abs(f_kdv)
        return abs(f_kdv) < TOLERANS

    kdv0_belges = {anahtar_fatura(f) for f in faturalar if _kdv0_fatura(f)}
    if kdv0_belges:
        faturalar = [f for f in faturalar if anahtar_fatura(f) not in kdv0_belges]
        cetvel_kayitlari = [c for c in cetvel_kayitlari if anahtar_cetvel(c) not in kdv0_belges]

    sonuc_satirlari = []
    ozet = {
        "fatura_adet": len(faturalar),
        "cetvel_adet": len(cetvel_kayitlari),
        "eslesen": 0,
        "tutar_farki": 0,
        "vkn_farki": 0,
        "kdv_sifir": len(kdv0_belges),
        "cetvelde_yok": 0,
        "faturada_yok": 0,
        "mukerrer": 0,
        "parse_sorunu": 0,
        "tevkifatli": 0,
        "onayli_fark": 0,
    }

    f_grup = defaultdict(list)
    for f in faturalar:
        if f["belge_no"]:
            f_grup[anahtar_fatura(f)].append(f)

    c_grup = defaultdict(list)
    for c in cetvel_kayitlari:
        if c.get("belge_no"):
            c_grup[anahtar_cetvel(c)].append(c)

    kullanilan_c = set()
    kullanilan_f = set()

    # Muavin kayıtlarının unvan/metin seti: bir faturanın satıcısı muavin
    # boyunca hiç geçmiyorsa fişi işlenmemiş olabilir (net bilgi üretir).
    muavin_metinleri = []
    for c in cetvel_kayitlari:
        parca = (str(c.get("unvan") or "") + " " +
                 str(c.get("belge_no") or "")).strip()
        if parca:
            muavin_metinleri.append(parca.upper())

    def durum_ekle(durum, f, c, detay=""):
        f_belge = (f or {}).get("belge_no") if f else ((c or {}).get("belge_no") if c else "")
        f_vkn = (f or {}).get("satici_vkn") if f else ((c or {}).get("vkn") if c else "")
        f_tarih = (f or {}).get("tarih") if f else ((c or {}).get("tarih") if c else "")
        f_matrah = (f or {}).get("matrah") if f else ((c or {}).get("matrah") if c else "")
        f_kdv = (f or {}).get("kdv") if f else ((c or {}).get("kdv") if c else "")
        f_unvan = f.get("satici_unvan") if f else (c.get("unvan") if c else "")
        f_toplam = f.get("toplam") if f else None
        f_oranlar = f.get("oranlar") if f else []
        f_tip = f.get("fatura_tipi") if f else ""
        f_ok = f.get("oran_kontrol") if f else ""
        sonuc_satirlari.append({
            "durum": durum,
            "belge_no": f_belge,
            "vkn": f_vkn,
            "tarih": f_tarih,
            "matrah": f_matrah,
            "kdv": f_kdv,
            "toplam": f_toplam,
            "oranlar": list(f_oranlar) if f_oranlar else [],
            "tip": (f_tip or "") if f_tip else "",
            "oran_kontrol": (f_ok or "") if f_ok else "",
            "unvan": (f_unvan or "") if f_unvan else "",
            "kaynak": "Fatura" if f else ("Cetvel" if c else ""),
            "detay": detay,
        })

    def fark_parcalari(f, c):
        parcalar = []
        for alan in ("matrah", "kdv"):
            f_deger = f.get(alan)
            c_deger = c.get(alan)
            if f_deger is not None and c_deger is not None and abs(f_deger - c_deger) > TOLERANS:
                parcalar.append(alan.capitalize() + ": " + fark_metni(f_deger, c_deger))
        return parcalar

    for anahtar, f_listesi in f_grup.items():
        c_listesi = c_grup.pop(anahtar, [])
        if not c_listesi:
            continue
        # YÖN EŞLEŞMESİ: alış faturalar yalnız 191 hesabıyla, satış
        # faturalar yalnız 391 hesabıyla karşılaştırılır. Cetvel hesabı
        # bilinmeyen kayıtlar (eski veri) her iki yöne de açıktır.
        ilk_f = f_listesi[0]
        fatura_yon = (ilk_f.get("fatura_tipi") or
                      ilk_f.get("tip") or "").upper()
        if "SATIS" in fatura_yon or "GIDEN" in fatura_yon:
            c_listesi = [c for c in c_listesi
                         if not c.get("hesap") or c.get("hesap") != "191"]
        elif "ALIS" in fatura_yon or "GELEN" in fatura_yon or "IADE" in fatura_yon:
            c_listesi = [c for c in c_listesi
                         if not c.get("hesap") or c.get("hesap") != "391"]
        if not c_listesi:
            continue

        # ÇOK ORANLI FATURA: KDV kırılımı birden fazla oranda olan
        # faturada her cetvel satırı kendi oranındaki tutarla ayrı
        # değerlendirilir; tüm cetvel satırları birer orana oturursa
        # toplam tutar farkı YAZILMAZ, artan oranlar ayrıca bildirilir.
        if len(f_listesi) == 1:
            f0 = f_listesi[0]
            oran_kalemleri = [o for o in (f0.get("oran_kalemleri") or [])
                              if isinstance(o, dict)
                              and o.get("kdv") is not None]
            if len(oran_kalemleri) > 1:
                kalan_oran = list(oran_kalemleri)
                oran_eslesme = {}
                for j, c in enumerate(c_listesi):
                    cv = c.get("kdv")
                    if cv is None:
                        continue
                    adaylar = [o for o in kalan_oran
                               if _tutar_esit(float(o["kdv"]),
                                              float(cv))]
                    if len(adaylar) == 1:
                        oran_eslesme[j] = adaylar[0]
                        kalan_oran.remove(adaylar[0])
                tam_kapsam = (len(oran_eslesme) == len(c_listesi)
                              and len(c_listesi) >= 2)

                # Cetvel satirlari tek tek orana oturmuyorsa ama KDV
                # toplamlari kirilimin toplamina esitse fatura kitapta
                # toplu kaydedilmistir; matematiksel olarak kapandigi
                # icin tutar farki YAZILMAZ.
                toplam_kapandi = False
                if not tam_kapsam and c_listesi and all(
                        c.get("kdv") is not None for c in c_listesi):
                    olcek = float(TOLERANS) * max(1, len(c_listesi))
                    toplam_kapandi = abs(
                        sum(float(c["kdv"]) for c in c_listesi)
                        - sum(float(o["kdv"])
                              for o in oran_kalemleri)) <= olcek

                if tam_kapsam or toplam_kapandi:
                    if toplam_kapandi and not tam_kapsam:
                        satir_f = dict(f0)
                        satir_f["toplam"] = None
                        oran_metni = "+".join(
                            "%{:g}".format(o["oran"])
                            for o in oran_kalemleri)
                        detay = (f"Oran kırılımı toplamda eşleşti "
                                 f"(KDV {oran_metni})")
                        for c in c_listesi:
                            kullanilan_c.add((id(c), anahtar))
                        kullanilan_f.add(id(f0))
                        if all(vkn_uyumlu(f0, c)
                               for c in c_listesi):
                            ozet["eslesen"] += 1
                            durum_ekle(DURUM_OK, satir_f,
                                       c_listesi[0], detay=detay)
                        else:
                            ozet["vkn_farki"] += 1
                            durum_ekle(DURUM_VKN_FARKI, satir_f,
                                       c_listesi[0],
                                       detay=detay + " | Fatura VKN: "
                                       f"{f0['satici_vkn']} | "
                                       f"Cetvel VKN: "
                                       f"{c_listesi[0]['vkn']}")
                        continue
                    for j, c in enumerate(c_listesi):
                        kullanilan_c.add((id(c), anahtar))
                        kullanilan_f.add(id(f0))
                        kalem = oran_eslesme[j]
                        satir_f = dict(f0)
                        satir_f["matrah"] = kalem.get("matrah")
                        satir_f["kdv"] = kalem["kdv"]
                        satir_f["toplam"] = None
                        if not vkn_uyumlu(f0, c):
                            ozet["vkn_farki"] += 1
                            durum_ekle(DURUM_VKN_FARKI, satir_f, c,
                                       detay=f"Oran %{kalem['oran']:g} | "
                                       f"Fatura VKN: {f0['satici_vkn']} | "
                                       f"Cetvel VKN: {c['vkn']}")
                        else:
                            ozet["eslesen"] += 1
                            durum_ekle(DURUM_OK, satir_f, c,
                                       detay=f"Oran bazında eşleşti "
                                       f"(KDV %{kalem['oran']:g})")
                    for o in kalan_oran:
                        ozet["cetvelde_yok"] += 1
                        satir_f = dict(f0)
                        satir_f["matrah"] = o.get("matrah")
                        satir_f["kdv"] = o["kdv"]
                        satir_f["toplam"] = None
                        durum_ekle(DURUM_CETVELDE_YOK, satir_f, None,
                                   detay=f"Faturanın KDV %{o['oran']:g} "
                                   "oranlı kalemi muavin cetvelde yok")
                    continue

        # Akıllı eşleştirme: aynı belge numarasında birden fazla fatura ve/veya
        # cetvel kaydı olabilir (belge numarası çakışması). Sırayla değil,
        # içerik uyumuna göre eşleştirilir:
        #   1) tarih eşit + tutar uyumlu, 2) yalnız tutar uyumlu, 3) kalanlar sırayla.
        c_kullanilan = set()
        eslesmeler = []

        def _bos_indeksler():
            return [j for j in range(len(c_listesi)) if j not in c_kullanilan]

        for f in f_listesi:
            for j in _bos_indeksler():
                c = c_listesi[j]
                if f.get("tarih") and f["tarih"] == c.get("tarih") and tutarlar_uyumlu(f, c):
                    eslesmeler.append((f, j))
                    c_kullanilan.add(j)
                    break
        eslenen_f = {id(f) for f, _ in eslesmeler}
        for f in f_listesi:
            if id(f) in eslenen_f:
                continue
            for j in _bos_indeksler():
                if tutarlar_uyumlu(f, c_listesi[j]):
                    eslesmeler.append((f, j))
                    c_kullanilan.add(j)
                    break
        eslenen_f = {id(f) for f, _ in eslesmeler}
        kalan_f = [f for f in f_listesi if id(f) not in eslenen_f]
        for f, j in zip(kalan_f, sorted(_bos_indeksler())):
            eslesmeler.append((f, j))
            c_kullanilan.add(j)

        for f, j in eslesmeler:
            c = c_listesi[j]
            kullanilan_c.add((id(c), anahtar))
            kullanilan_f.add(id(f))
            if not vkn_uyumlu(f, c):
                durum = DURUM_VKN_FARKI
                ozet["vkn_farki"] += 1
                detay = f"Fatura satıcı VKN: {f['satici_vkn']} | Cetvel VKN: {c['vkn']}"
                farklar = fark_parcalari(f, c)
                if farklar:
                    detay += " | " + " | ".join(farklar)
            elif not tutarlar_uyumlu(f, c):
                ek_kesinti = None
                if kurallar:
                    kural = kural_bul(kurallar, unvan=f.get("satici_unvan"),
                                      vkn=f.get("satici_vkn"), belge_no=f.get("belge_no"))
                    # Kural kullanıcı diliyle KESİNTİ oranıdır (%90 tevkifat);
                    # eşleşme muavinde KALAN oranla yapılır (1 - kesinti).
                    ek_kesinti = beklenen_oran(kural)
                ek_oran = (Decimal("1") - ek_kesinti) if ek_kesinti is not None else None
                tk_oran = tevkifat_kes(f, c, ek_oran=ek_oran)
                if tk_oran is not None:
                    durum = DURUM_TEVKIFATLI
                    ozet["tevkifatli"] += 1
                    detay = tevkifat_detay(f, c, tk_oran)
                    if ek_kesinti is not None and tk_oran == ek_oran:
                        detay += f" | Kural oranı: %{int(ek_kesinti * 100)}"
                else:
                    durum = DURUM_TUTAR_FARKI
                    ozet["tutar_farki"] += 1
                    detay = " | ".join(fark_parcalari(f, c))
                    if f.get("tarih") and c.get("tarih") and f["tarih"] != c["tarih"]:
                        detay += f" | Tarih: {f['tarih']} vs {c['tarih']}"
            else:
                durum = DURUM_OK
                ozet["eslesen"] += 1
                # Yanlış eşleşme koruması: satıcı unvanı ile muavin
                # açıklaması hiç ortak harf dizisi içermiyorsa şüpheli
                # olarak işaretle (belge no OCR yanılması olabilir).
                detay = ""
                try:
                    _fu = _harfler(f.get("satici_unvan") or "")
                    _cu = _harfler(c.get("unvan") or "")
                    if _fu and _cu and not (_fu[:8] in _cu or _cu[:8] in _fu):
                        ortak = max((len(_fu[i:i+5]) for i in range(0, len(_fu) - 4)
                                     for j in range(len(_cu))
                                     if _cu.startswith(_fu[i:i+5], j)), default=0)
                        if ortak < 4:
                            detay = "⚠ Şüpheli eşleşme: unvanlar farklı"
                            ozet["supheli_eslesme"] =                                 ozet.get("supheli_eslesme", 0) + 1
                except Exception:
                    pass
                if (f.get("indirim_toplam") or Decimal("0")) > Decimal("0"):
                    durum = DURUM_INDIRIMLI
                    detay = f"Fatura özel indirim içerir (≈{f['indirim_toplam']:,.2f})"
            durum_ekle(durum, f, c, detay)

        # Artan faturalar: eşleşen bir faturanın birebir kopyasıysa mükerrer,
        # değilse muavindefterinde hiç yoktur → CETVELDE YOK.
        eslesen_f = {id(f) for f, _ in eslesmeler}
        eslesen_icerik = [(p.get("tarih"), p.get("matrah"), p.get("kdv")) for p, _ in eslesmeler]
        for f in f_listesi:
            if id(f) in eslesen_f:
                continue
            kullanilan_f.add(id(f))
            if any(f.get("tarih") == t and _tutar_esit(f.get("matrah"), m)
                   and _tutar_esit(f.get("kdv"), kdv)
                   for t, m, kdv in eslesen_icerik):
                ozet["mukerrer"] += 1
                durum_ekle(DURUM_MUKERRER, f, None, "Aynı fatura birden fazla kayıt halinde")
            else:
                            ozet["cetvelde_yok"] += 1
                            detay = []
                            if f["matrah"] is None or f["kdv"] is None:
                                detay.append("Tutarlar okunamadı")
                            # Net bilgi: satıcı muavin defterinde hiç geçmiyorsa fiş
                            # işlenmemiş olabilir (Luca'da muhasebeleştirme bekleniyor).
                            if not _satici_muavinde_var_mi(
                                    (f.get("satici_unvan") or ""),
                                    muavin_metinleri):
                                detay.append("Muavinde satıcı hiç geçmiyor — fiş "
                                             "işlenmemiş olabilir (Luca'da "
                                             "muhasebeleştirme bekleniyor)")
                            if not detay:
                                detay.append("Cetvelde kaydı yok")
                            durum_ekle(DURUM_CETVELDE_YOK, f, None,
                                       " / ".join(detay))
        # Artan cetvel satırları: defterde mükerrer kayıt.
        for j, c in enumerate(c_listesi):
            if j in c_kullanilan:
                continue
            ozet["mukerrer"] += 1
            durum_ekle(DURUM_MUKERRER, None, c, "Cetvelde aynı fatura birden fazla satır halinde")

    kalan_f = []
    for f in faturalar:
        if id(f) in kullanilan_f:
            continue
        if f["belge_no"]:
            kalan_f.append(f)

    for f in kalan_f:
        ozet["cetvelde_yok"] += 1
        detay = []
        if f["matrah"] is None or f["kdv"] is None:
            detay.append("Tutarlar okunamadı")
        if not _satici_muavinde_var_mi((f.get("satici_unvan") or ""),
                                       muavin_metinleri):
            detay.append("Muavinde satıcı hiç geçmiyor — fiş işlenmemiş "
                         "olabilir (Luca'da muhasebeleştirme bekleniyor)")
        if not detay:
            detay.append("Cetvelde kaydı yok")
        durum_ekle(DURUM_CETVELDE_YOK, f, None, " / ".join(detay))

    for anahtar, c_listesi in list(c_grup.items()):
        for c in c_listesi:
            if (id(c), anahtar) in kullanilan_c:
                continue
            if not c["belge_no"]:
                continue
            ozet["faturada_yok"] += 1
            durum_ekle(DURUM_FATURADA_YOK, None, c, "Faturalar arasında kaydı yok")

    for f in faturalar:
        if f["belge_no"] is None and f["satici_vkn"] is None and f["matrah"] is None:
            ozet["parse_sorunu"] += 1
            durum_ekle(DURUM_PARSE_SORUNU, f, None, "PDF'den veri çıkarılamadı (taranmış PDF olabilir)")

    # Firma kuralları: onaylı fark işaretlemesi
    onay_kurallari = [k for k in (kurallar or []) if k.get("onayla")]
    if onay_kurallari:
        for r in sonuc_satirlari:
            if r["durum"] not in SORUNLU_DURUMLAR:
                continue
            kural = kural_bul(onay_kurallari, unvan=r.get("unvan"),
                              vkn=r.get("vkn"), belge_no=r.get("belge_no"))
            if kural:
                r["durum"] = DURUM_ONAYLI
                ekle = f"[Kural: {kural.get('ad') or kural.get('eslesme')}] onaylı fark"
                r["detay"] = (r["detay"] + " | " + ekle) if r.get("detay") else ekle
                ozet["onayli_fark"] += 1

    try:
        olasilari_isaretle(sonuc_satirlari, faturalar, cetvel_kayitlari)
    except Exception:
        pass

    ozet["fark_toplami"] = sum((r["durum"] == DURUM_TUTAR_FARKI) for r in sonuc_satirlari)
    sonuc_satirlari.sort(key=lambda r: (SORUNLU_DURUMLAR.index(r["durum"]) if r["durum"] in SORUNLU_DURUMLAR else 99, r["belge_no"] or ""))
    return sonuc_satirlari, ozet


# ============================================================================
# İADE FATURA DESTEĞİ (YENİ)
# ============================================================================

def z_raporu_hesap_kontrol(fis_kayitlari, muavin_kayitlari):
    """MAHSUP fişi PDF'i ile muavin defterini hesap bazında karşılaştırır.

    Kayıt formatı (her iki taraf için): {belge, tarih, hesap, hesap_adi, borc, alacak}
    Sonuç satırları capraz_kontrol ile aynı formatta üretilir.
    """
    sonuc_satirlari = []
    ozet = {
        "fatura_adet": len(fis_kayitlari),
        "cetvel_adet": len(muavin_kayitlari),
        "eslesen": 0, "tutar_farki": 0, "vkn_farki": 0, "kdv_sifir": 0,
        "cetvelde_yok": 0, "faturada_yok": 0, "mukerrer": 0,
        "parse_sorunu": 0, "fark_toplami": 0,
    }

    def anahtar(k):
        return ((k["belge"] or "").upper(), k.get("hesap") or "")

    f_grup = defaultdict(list)
    for k in fis_kayitlari:
        f_grup[anahtar(k)].append(k)
    m_grup = defaultdict(list)
    for k in muavin_kayitlari:
        m_grup[anahtar(k)].append(k)

    kullanilan_f = set()
    kullanilan_m = set()

    def kayit_tutar(k):
        return k["alacak"] if k["alacak"] else k["borc"]

    def durum_ekle(durum, f, m, detay=""):
        k = f if f is not None else m
        tutar = kayit_tutar(k) if k is not None else None
        belge = (k["belge"] or "") if k is not None else ""
        sonuc_satirlari.append({
            "durum": durum,
            "belge_no": belge,
            "vkn": "",
            "tarih": k.get("tarih") if k is not None else None,
            "matrah": tutar,
            "kdv": None,
            "toplam": None,
            "oranlar": [],
            "tip": "Z RAPORU" if belge.startswith("Z") else "MAHSUP",
            "oran_kontrol": "",
            "unvan": (k.get("hesap_adi") or "") if k is not None else "",
            "kaynak": "Fatura" if f is not None else "Cetvel",
            "detay": detay,
        })

    for a, f_list in f_grup.items():
        m_list = m_grup.pop(a, [])
        if not m_list:
            continue
        es = min(len(f_list), len(m_list))
        for i in range(es):
            f = f_list[i]
            m = m_list[i]
            kullanilan_f.add(id(f))
            kullanilan_m.add((id(m), a))
            f_tutar = kayit_tutar(f)
            m_tutar = kayit_tutar(m)
            hesap = a[1]
            if f_tutar is not None and m_tutar is not None and abs(f_tutar - m_tutar) > TOLERANS:
                ozet["tutar_farki"] += 1
                durum_ekle(DURUM_TUTAR_FARKI, f, m, "Hesap: " + hesap + " | " + fark_metni(f_tutar, m_tutar))
            else:
                ozet["eslesen"] += 1
                durum_ekle(DURUM_OK, f, m, "Hesap: " + hesap)
        for f in f_list[es:]:
            ozet["mukerrer"] += 1
            durum_ekle(DURUM_MUKERRER, f, None, "Hesap: " + a[1] + " | Aynı belge/hesap birden fazla kayıt")
        for m in m_list[es:]:
            ozet["mukerrer"] += 1
            durum_ekle(DURUM_MUKERRER, None, m, "Hesap: " + a[1] + " | Muavinde aynı belge/hesap birden fazla kayıt")

    kalan_f = [f for f in fis_kayitlari if id(f) not in kullanilan_f and f["belge"]]
    for f in kalan_f:
        ozet["cetvelde_yok"] += 1
        durum_ekle(DURUM_CETVELDE_YOK, f, None, "Hesap: " + (f.get("hesap") or "") + " | Muavinde kaydı yok")

    for a, m_list in list(m_grup.items()):
        for m in m_list:
            if (id(m), a) in kullanilan_m or not m["belge"]:
                continue
            ozet["faturada_yok"] += 1
            durum_ekle(DURUM_FATURADA_YOK, None, m, "Hesap: " + (m.get("hesap") or "") + " | Faturada kaydı yok")

    ozet["fark_toplami"] = ozet["tutar_farki"]
    sonuc_satirlari.sort(key=lambda r: (SORUNLU_DURUMLAR.index(r["durum"]) if r["durum"] in SORUNLU_DURUMLAR else 99, r["belge_no"] or ""))
    return sonuc_satirlari, ozet


def capraz_kontrol_iade_destekli(faturalar, cetvel_kayitlari, kurallar=None):
    """İade faturalarını ayrı ele alarak çapraz kontrol yapar.

    capraz_kontrol ile aynı sonucu verir, ancak:
    - İade faturaları "İADE MUAVİNDE YOK" olarak ayrı raporlanır
    - İadeler mutlak değerle muavinle eşleşir
    """
    from iade_ayristirici import iade_ayristirici_ozet, iade_ozet_hesapla

    gruplar = iade_ayristirici_ozet(faturalar)
    normal_faturalar = gruplar["normal"]
    iade_faturalar = gruplar["iade"]

    # Normal faturaları normal kontrol
    if normal_faturalar:
        sonuc, ozet = capraz_kontrol(normal_faturalar, cetvel_kayitlari, kurallar=kurallar)
    else:
        sonuc = []
        ozet = {
            "fatura_adet": 0, "cetvel_adet": len(cetvel_kayitlari),
            "eslesen": 0, "tutar_farki": 0, "vkn_farki": 0, "kdv_sifir": 0,
            "cetvelde_yok": 0, "faturada_yok": 0, "mukerrer": 0,
            "parse_sorunu": 0, "fark_toplami": 0,
        }

    # İade faturaları ayrı kontrol (muavin 191 hesabında aranmalı).
    # Sorun: normal ve iade faturalar ayn cetvel listesini kullandığdan,
    # iade'le eşleşen muavin kayıtlarını normal kontrol'de "FATURALARDA YOK"
    # olarak ikire gösterdı. Düzeltme: iade faturaları SONRA kontrol edilip,
    # eşleşen belge'ler normal "FATURALARDA YOK" sonuc'dan tam kaldırılır.
    if iade_faturalar:
        iade_eksikler = []
        durum_cevir = {
            DURUM_OK: "İADE EŞLEŞTİ",
            DURUM_CETVELDE_YOK: "İADE MUAVİNDE YOK",
            DURUM_TUTAR_FARKI: "İADE MATRAH FARKI",
            DURUM_VKN_FARKI: "İADE VKN FARKI",
            DURUM_MUKERRER: "İADE MÜKERRER",
            DURUM_TEVKIFATLI: "İADE TEVKİFATLI",
        }
        # İade kontrolü SADECE iade belge numaralarına uyan muavin satırlarıyla
        # yapılır. Tüm liste verilirse, normal geçişte eşleşmiş muavin kayıtları
        # iade geçişinde tekrar "FATURALARDA YOK" olarak raporlanıyordu.
        import copy as _cpy
        iade_belge_kumesi = {(f["belge_no"] or "").upper() for f in iade_faturalar}
        iade_cetvel = [
            c for c in cetvel_kayitlari
            if (c.get("belge_no") or "").upper() in iade_belge_kumesi
        ]
        iade_abs = []
        for f in iade_faturalar:
            f2 = _cpy.deepcopy(f)
            if f2.get("kdv") is not None:
                f2["kdv"] = abs(f2["kdv"])
            if f2.get("matrah") is not None:
                f2["matrah"] = abs(f2["matrah"])
            iade_abs.append(f2)
        iade_sonuc, iade_ozet2 = capraz_kontrol(iade_abs, iade_cetvel, kurallar=kurallar)
        for r, f in zip(iade_sonuc, iade_faturalar):
            r["durum"] = durum_cevir.get(r["durum"], r["durum"])
            if r["kdv"] is not None:
                r["kdv"] = abs(r["kdv"])
            if r["matrah"] is not None:
                r["matrah"] = abs(r["matrah"])
            r["belge_no"] = f["belge_no"]
            r["kaynak"] = "Fatura (İade)"
            if r["durum"] == "İADE MUAVİNDE YOK":
                iade_eksikler.append(r["belge_no"] or "")
        sonuc.extend(iade_sonuc)

        # Normal kontrolde "FATURALARDA YOK" çıkmış, iade ile eşleşen muavin satırlarını kaldır
        ozet["tevkifatli"] = ozet.get("tevkifatli", 0) + iade_ozet2.get("tevkifatli", 0)
        eslesen_iade_belge = {r["belge_no"] for r in iade_sonuc if r["durum"] == "İADE EŞLEŞTİ"}
        if eslesen_iade_belge:
            onceki_sayı = len(sonuc)
            sonuc = [
                r for r in sonuc
                if not (r["durum"] == DURUM_FATURADA_YOK and r["belge_no"] in eslesen_iade_belge)
            ]
            cikan = onceki_sayı - len(sonuc)
            ozet["faturada_yok"] = max(0, ozet.get("faturada_yok", 0) - cikan)

        # Özete iade bilgisi ekle
        iade_ozet = iade_ozet_hesapla(iade_faturalar)
        ozet["iade_adet"] = iade_ozet["iade_adet"]
        ozet["iade_kdv_toplam"] = float(iade_ozet["toplam_iade_kdv"])
        ozet["iade_matrah_toplam"] = float(iade_ozet["toplam_iade_matrah"])
        ozet["iade_muavinde_yok"] = len(iade_eksikler)
        ozet["fatura_adet"] = ozet.get("fatura_adet", 0) + len(iade_faturalar)

    return sonuc, ozet

