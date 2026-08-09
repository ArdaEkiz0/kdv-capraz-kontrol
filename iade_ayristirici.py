"""İade faturalarını normalden ayır, muavin karşılaştırmasında ayrı ele al."""
from typing import Dict, List
from decimal import Decimal
from matcher import (DURUM_OK, DURUM_TUTAR_FARKI, DURUM_VKN_FARKI,
                     DURUM_CETVELDE_YOK, DURUM_FATURADA_YOK, DURUM_MUKERRER)

IADE_DURUM_EK_SATIR = "İADE EŞLEŞTİ"
IADE_DURUM_MATRAH_FARKI = "İADE MATRAH FARKI"
IADE_DURUM_CETVELDE_YOK = "İADE MUAVİNDE YOK"

# İade tipleri (XML'den gelen InvoiceTypeCode)
IADE_TIPLERI = {"IADE", "CREDIT_NOTE", "CREDITNOTE", "TEVKIFATIADE"}


def iade_mi(fatura: Dict) -> bool:
    """Fatura iade mi?"""
    tip = (fatura.get("tip") or "").upper().replace(" ", "")
    if tip in IADE_TIPLERI:
        return True
    matrah = fatura.get("matrah")
    if matrah is not None and matrah < 0:
        return True
    kdv = fatura.get("kdv")
    if kdv is not None and kdv < 0:
        return True
    return False


def iade_ayristirici_ozet(faturalar: List[Dict]) -> Dict:
    """Faturaları normal/iade olarak ayır."""
    normal = []
    iade = []
    for f in faturalar:
        if iade_mi(f):
            iade.append(f)
        else:
            normal.append(f)
    return {"normal": normal, "iade": iade}


def iade_ozet_hesapla(iade_faturalar: List[Dict]) -> Dict:
    """İade faturalarından özet üret (191 indirilecek KDV hesabı için)."""
    toplam_iade_kdv = Decimal("0")
    toplam_iade_matrah = Decimal("0")
    oran_dagilim = {}
    for f in iade_faturalar:
        kdv = f.get("kdv") or Decimal("0")
        matrah = f.get("matrah") or Decimal("0")
        toplam_iade_kdv += abs(kdv)
        toplam_iade_matrah += abs(matrah)
        for oran in f.get("oranlar") or []:
            g = oran_dagilim.setdefault(oran, {"adet": 0, "matrah": Decimal("0"), "kdv": Decimal("0")})
            g["adet"] += 1
            g["matrah"] += abs(matrah)
            g["kdv"] += abs(kdv)
    return {
        "iade_adet": len(iade_faturalar),
        "toplam_iade_matrah": toplam_iade_matrah,
        "toplam_iade_kdv": toplam_iade_kdv,
        "oran_dagilim": oran_dagilim,
    }
