import re
from decimal import Decimal, ROUND_HALF_UP

TL_BASLIKLAR = ("TL", "TUTAR", "KDV", "TOPLAM", "MATRAH", "ORAN", "MAL", "HIZMET", "HİZMET", "VERGİ", "VERGI", "İSKONTO", "ISKONTO", "BEDEL", "FİYAT", "FIYAT", "ARACILIK")


def sadeleştir(metin):
    return re.sub(r"\s+", " ", str(metin or "")).strip()


def vkn_temizle(deger):
    if deger is None:
        return ""
    return re.sub(r"\D", "", str(deger))


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
    metin = metin.replace("(", "0").replace(")", "0").replace("O", "0").replace("l", "1")
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


def sayilari_bul(metin):
    sonuc = []
    for m in re.finditer(r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?", metin):
        try:
            d = tutar_parse(m.group(0))
            if d is not None:
                sonuc.append(d)
        except Exception:
            pass
    return sonuc
