import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

TL_BASLIKLAR = ("TL", "TUTAR", "KDV", "TOPLAM", "MATRAH", "ORAN", "MAL", "HIZMET", "HİZMET", "VERGİ", "VERGI", "İSKONTO", "ISKONTO", "BEDEL", "FİYAT", "FIYAT", "ARACILIK")

# KDV oranları ve simgeleri
KDV_ORAN_MAP = {
    1: Decimal("0.01"),
    5: Decimal("0.05"),
    10: Decimal("0.10"),
    20: Decimal("0.20"),
}

# Ay Adları (Türkçe)
AY_ADLARI = {
    1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan",
    5: "Mayıs", 6: "Haziran", 7: "Temmuz", 8: "Ağustos",
    9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık",
}


def sadeleştir(metin: str) -> str:
    return re.sub(r"\s+", " ", str(metin or "")).strip()


RAKAM_KARISIK = str.maketrans({
    "O": "0", "o": "0",
    "I": "1", "İ": "1", "ı": "1",
    "i": "1", "l": "1",
})


def rakamlara_cevir(deger):
    if deger is None:
        return ""
    return str(deger).translate(RAKAM_KARISIK)


def vkn_temizle(deger):
    if deger is None:
        return ""
    return re.sub(r"\D", "", rakamlara_cevir(str(deger)))


def fatura_no_temizle(deger):
    if deger is None:
        return ""
    metin = str(deger).upper().replace("№", "").replace("#", "").strip()
    metin = re.sub(r"[^A-Z0-9]", "", metin)
    return metin


def tutar_parse(deger):
    if deger is None:
        return None
    metin = str(deger).strip()
    for k in TL_BASLIKLAR:
        metin = metin.replace(k, "")
    metin = metin.replace("₺", "").replace("%", "").replace(" ", "").strip()
    metin = metin.replace("(", "0").replace(")", "0")
    metin = rakamlara_cevir(metin)
    if not metin:
        return None
    if "," in metin and "." in metin:
        metin = metin.replace(".", "").replace(",", ".")
    elif "," in metin:
        metin = metin.replace(",", ".")
    elif "." in metin:
        parcalar = metin.split(".")
        if not (len(parcalar) == 2 and len(parcalar[1]) <= 2):
            metin = metin.replace(".", "")
    try:
        deger = Decimal(metin)
        if not deger.is_finite():
            return None
        return deger.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return None


def tarih_parse(deger):
    if deger is None:
        return None
    metin = str(deger).strip()
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", metin)
    if m:
        yil, ay, gun = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if ay < 1 or ay > 12 or gun < 1 or gun > 31:
            return None
        return f"{yil:04d}-{ay:02d}-{gun:02d}"
    m = re.search(r"(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})", metin)
    if not m:
        return None
    gun, ay, yil = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if ay < 1 or ay > 12 or gun < 1 or gun > 31:
        return None
    return f"{yil:04d}-{ay:02d}-{gun:02d}"


def tl_format(deger):
    if deger is None:
        return ""
    return f"{deger:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def tckn_gecerli_mi(tckn):
    tckn = str(tckn or "").strip()
    if len(tckn) != 11 or not tckn.isdigit() or tckn[0] == "0":
        return False
    h = [int(x) for x in tckn]
    if (sum(h[0:9:2]) * 7 - sum(h[1:8:2])) % 10 != h[9]:
        return False
    return sum(h[0:10]) % 10 == h[10]


def vkn_gecerli_mi(vkn):
    deger = rakamlara_cevir(str(vkn or "").strip())
    if not deger.isdigit():
        return True
    if len(deger) == 11:
        return tckn_gecerli_mi(deger)
    if len(deger) != 10:
        return True
    h = [int(x) for x in deger]
    toplam = 0
    for i in range(9):
        tmp = (h[i] + 9 - i) % 10
        carpim = (tmp * (2 ** (9 - i))) % 9
        if tmp != 0 and carpim == 0:
            carpim = 9
        toplam += carpim
    kontrol = 0 if toplam % 10 == 0 else 10 - (toplam % 10)
    return kontrol == h[9]


_RAKAM_BENZER = r"[0-9OoIilıİ]"
_SAYI_TOKEN = re.compile(
    rf"{_RAKAM_BENZER}{{1,3}}(?:\.{_RAKAM_BENZER}{{3}})+(?:,{_RAKAM_BENZER}{{1,2}})?"
    rf"|{_RAKAM_BENZER}+(?:,{_RAKAM_BENZER}{{1,2}})?"
)


def sayilari_bul(metin: str) -> list[Decimal]:
    sonuc: list[Decimal] = []
    for m in _SAYI_TOKEN.finditer(str(metin or "")):
        aday = m.group(0)
        if not re.search(r"[0-9]", aday):
            continue
        d = tutar_parse(aday)
        if d is not None:
            sonuc.append(d)
    return sonuc


# ─── Ek Yardımcı Fonksiyonlar (v3.2.0) ──────────────────────────────

def donem_adi(donem: str) -> str:
    """YYYY-AA formatındaki dönem adını Türkçe olarak döndürür.

    Örnek: "2024-07" -> "Temmuz 2024"
    """
    try:
        parcalar = donem.split("-")
        yil = int(parcalar[0])
        ay = int(parcalar[1])
        return f"{AY_ADLARI.get(ay, '?')} {yil}"
    except (ValueError, IndexError):
        return donem


def sayiyi_bol(deger: Decimal, bolunen: int) -> list[Decimal]:
    """Bir tutarı eşit parçalara böler (yuvarlama farklarını telafi eder).

    Örnek: 1000.00 / 3 -> [333.34, 333.33, 333.33]
    """
    if not deger or bolunen <= 0:
        return []
    deger_d = Decimal(str(deger))
    b = Decimal(str(bolunen))
    taban = (deger_d / b).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    kalan = deger_d - taban * b
    sonuc = [taban] * bolunen
    # Kalanı ilk satırlara dağıt
    i = 0
    while kalan > 0 and i < bolunen:
        ekle = min(Decimal("0.01"), kalan)
        sonuc[i] += ekle
        kalan -= ekle
        i += 1
    return sonuc


def yuzde_hesapla(bolum: Decimal, toplam: Decimal) -> Optional[Decimal]:
    """İki değer arasındaki yüzdelik oranı hesaplar."""
    if not toplam or toplam == 0:
        return None
    return (Decimal(str(bolum)) / Decimal(str(toplam)) * Decimal("100")).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )


def guvenli_decimal(deger: Any) -> Optional[Decimal]:
    """Değeri güvenli bir şekilde Decimal'a çevirir; başarısızsa None döner."""
    if deger is None:
        return None
    try:
        d = Decimal(str(deger).replace(",", "."))
        return d if d.is_finite() else None
    except Exception:
        return None


def tarihleri_karsilastir(tarih1: Optional[str], tarih2: Optional[str]) -> Optional[int]:
    """İki tarih arasındaki gün farkını hesaplar.

    Format: YYYY-MM-DD
    Fark: tarih1 - tarih2 (pozitif ise tarih1 daha yeni)
    """
    if not tarih1 or not tarih2:
        return None
    try:
        d1 = datetime.strptime(str(tarih1)[:10], "%Y-%m-%d")
        d2 = datetime.strptime(str(tarih2)[:10], "%Y-%m-%d")
        return (d1 - d2).days
    except ValueError:
        return None


def belge_no_normallestir(belge_no: str) -> str:
    """Belge numarasını karşılaştırma için normalize eder.

    - Büyük harfe çevirir
    - Boşlukları ve özel karakterleri temizler
    - Leading zero korunmaz (eşleştirmeyi zorlaştırır)
    """
    if not belge_no:
        return ""
    metin = str(belge_no).upper().strip()
    metin = re.sub(r"[^A-Z0-9]", "", metin)
    return metin
