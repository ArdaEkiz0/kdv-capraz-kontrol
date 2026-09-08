"""Firma-bazlı eşleştirme kuralları.

kurallar.json formatı:
[
    {"ad": "Opet", "eslesme": "OPET", "oran": "0.90", "onayla": false}
]

- eslesme : Fatura ünvanında, satıcı VKN'sinde veya belge numarasında
            aranacak metin (büyük/küçük ve O/0 duyarsız eşleşir)
- oran    : Bu firmada kabul edilen tevkifat oranı ("0.90" gibi;
            boşsa yalnızca varsayılan 0.70 / 0.95 kullanılır)
- onayla  : true ise bu firmaya ait sorunlu satırlar "ONAYLI FARK"
            durumuna düşer ve sorun sayılmaz.
"""
import json
import os
from decimal import Decimal, InvalidOperation

from utils import rakamlara_cevir

DOSYA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kurallar.json")


def kurallari_oku():
    try:
        with open(DOSYA, "r", encoding="utf-8") as fh:
            liste = json.load(fh)
        if isinstance(liste, list):
            return [k for k in liste if isinstance(k, dict) and str(k.get("eslesme") or "").strip()]
    except Exception:
        pass
    return []


def kurallari_kaydet(liste):
    temiz = []
    for k in liste:
        kural = {
            "ad": str(k.get("ad") or "").strip(),
            "eslesme": str(k.get("eslesme") or "").strip(),
            "oran": str(k.get("oran") or "").strip().replace(",", "."),
            "onayla": bool(k.get("onayla")),
        }
        if not kural["eslesme"]:
            continue
        if kural["oran"]:
            try:
                Decimal(kural["oran"])
            except InvalidOperation:
                kural["oran"] = ""
        else:
            kural["oran"] = ""
        temiz.append(kural)
    with open(DOSYA, "w", encoding="utf-8") as fh:
        json.dump(temiz, fh, ensure_ascii=False, indent=2)
    return temiz


def _norm(metin):
    if not metin:
        return ""
    return " ".join(rakamlara_cevir(str(metin)).upper().split())


def kural_bul(kurallar, unvan="", vkn="", belge_no=""):
    """Verilen alanlara uyan ilk kuralı döndürür, yoksa None."""
    hedefler = (_norm(unvan), _norm(vkn), _norm(belge_no))
    for kural in kurallar or []:
        ibare = _norm(kural.get("eslesme"))
        if not ibare:
            continue
        for hedef in hedefler:
            if hedef and ibare in hedef:
                return kural
    return None


def beklenen_oran(kural):
    """Kuraldaki tevkifat (kesinti) oranını Decimal olarak döndürür (0..1 arası), yoksa None.

    Örn. "0.90" -> %90 tevkifat; muavinde kalan kısım 1 - 0.90 = 0.10 olur.
    """
    if not kural:
        return None
    metin = str(kural.get("oran") or "").strip().replace(",", ".")
    if not metin:
        return None
    try:
        deger = Decimal(metin)
    except InvalidOperation:
        return None
    return deger if Decimal("0") < deger < Decimal("1") else None
