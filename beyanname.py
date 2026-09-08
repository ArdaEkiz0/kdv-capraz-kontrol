"""Beyanname kutuları ile defter (191/391) toplamları karşılaştırması."""
from decimal import Decimal

from utils import tutar_parse


def _hesap_anahtari(kayit):
    for n in kayit.get("notlar") or []:
        if isinstance(n, str) and n.startswith("Hesap: "):
            kod = n[7:].strip()
            if kod.startswith("191"):
                return "191"
            if kod.startswith("391"):
                return "391"
    return "diger"


def defter_toplamlari(cetvel_kayitlari):
    """Cetvel kayıtlarını 191/391'e göre gruplayıp KDV toplamlarını döndürür.

    Returns: ({'191': Decimal, '391': Decimal, 'diger': Decimal},
              {'191': adet, '391': adet, 'diger': adet})
    """
    toplam = {"191": Decimal("0"), "391": Decimal("0"), "diger": Decimal("0")}
    adet = {"191": 0, "391": 0, "diger": 0}
    for k in cetvel_kayitlari or []:
        kdv = k.get("kdv")
        if not kdv:
            continue
        anahtar = _hesap_anahtari(k)
        toplam[anahtar] += Decimal(str(kdv))
        adet[anahtar] += 1
    return toplam, adet


def beyanname_karsilastir(cetvel_kayitlari, indirilecek_beyan, hesaplanan_beyan):
    """Defter toplamları ile girilen beyanname değerlerini karşılaştırır.

    Returns: [{"konu", "beyanname", "defter", "fark", "uyumlu"}...] veya None (veri yok)
    """
    toplam, adet = defter_toplamlari(cetvel_kayitlari)
    if not adet["191"] and not adet["391"]:
        return None

    satirlar = []
    esleme = [
        ("İndirilecek KDV (191)", indirilecek_beyan, toplam["191"], adet["191"]),
        ("Hesaplanan KDV (391)", hesaplanan_beyan, toplam["391"], adet["391"]),
    ]
    for konu, beyan_deger, defter_toplam, n in esleme:
        if beyan_deger is None or (isinstance(beyan_deger, str) and not beyan_deger.strip()):
            continue
        if isinstance(beyan_deger, str):
            beyan = tutar_parse(beyan_deger)
            if beyan is None:
                continue
        else:
            beyan = Decimal(str(beyan_deger))
        fark = (defter_toplam - beyan).quantize(Decimal("0.01"))
        satirlar.append({
            "konu": konu,
            "beyanname": beyan,
            "defter": defter_toplam.quantize(Decimal("0.01")),
            "fark": fark,
            "kayit_adedi": n,
            "uyumlu": abs(fark) <= Decimal("0.02"),
        })
    return satirlar or None
