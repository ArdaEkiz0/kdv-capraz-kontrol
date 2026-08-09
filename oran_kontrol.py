"""Matrah × KDV Oranı = KDV tutarı doğrulaması.

Faturadaki KDV oranı ile KDV tutarının matematiksel tutarlılığını kontrol eder.
Raporlarda 'KDV Matrah Kontrolü' sütunu olarak gösterilir.
"""
from decimal import Decimal
from typing import Dict, List

from utils import tl_format

# Türkiye KDV oranları
GECERLI_ORANLAR = {0, 1, 8, 10, 18, 20}

TOLERANS_ORAN = Decimal("0.02")


def oran_dogrula(fatura: Dict) -> Dict:
    """Tek bir fatura için matrah × oran doğrulaması.

    Returns:
        {
            "uyumlu": True/False,
            "beklenen_kdv": Decimal,
            "gercek_kdv": Decimal,
            "fark": Decimal,
            "oran_listesi": [10, 20, ...],
            "mesaj": "...",
        }
    """
    matrah = fatura.get("matrah")
    kdv = fatura.get("kdv")
    oranlar = fatura.get("oranlar") or []

    sonuc = {
        "uyumlu": False,
        "beklenen_kdv": None,
        "gercek_kdv": kdv,
        "fark": None,
        "oran_listesi": list(oranlar),
        "mesaj": "",
    }

    if matrah is None or kdv is None:
        sonuc["mesaj"] = "Matrah/KDV okunamadı"
        return sonuc

    matrah = Decimal(str(matrah))
    kdv = Decimal(str(kdv))

    if len(oranlar) == 1:
        oran = Decimal(str(oranlar[0]))
        beklenen = (matrah * oran / Decimal("100")).quantize(Decimal("0.01"))
        fark = abs(beklenen - abs(kdv))
        sonuc["beklenen_kdv"] = beklenen
        sonuc["fark"] = fark
        if fark <= TOLERANS_ORAN:
            sonuc["uyumlu"] = True
            sonuc["mesaj"] = f"Uyumlu (%{oranlar[0]})"
        else:
            sonuc["uyumlu"] = False
            sonuc["mesaj"] = (
                f"Beklenen {tl_format(beklenen)} ≠ Gerçek {tl_format(kdv)} (fark: {tl_format(fark)})"
            )

    elif len(oranlar) > 1:
        detay = fatura.get("vergi_detay") or []
        if detay:
            toplam_beklenen = Decimal("0")
            tutarsizliklar = []
            for st in detay:
                if st.get("matrah") and st.get("oran"):
                    o = Decimal(str(st["oran"]))
                    m = Decimal(str(st["matrah"]))
                    beklenen_st = (m * o / Decimal("100")).quantize(Decimal("0.01"))
                    toplam_beklenen += beklenen_st
                    if abs(beklenen_st - Decimal(str(st.get("kdv") or 0))) > TOLERANS_ORAN:
                        tutarsizliklar.append(
                            f"%{st['oran']}: beklenen {tl_format(beklenen_st)} vs {tl_format(st.get('kdv', 0))}"
                        )
            sonuc["beklenen_kdv"] = toplam_beklenen
            sonuc["fark"] = abs(toplam_beklenen - abs(kdv))
            if not tutarsizliklar and abs(toplam_beklenen - abs(kdv)) <= TOLERANS_ORAN:
                sonuc["uyumlu"] = True
                sonuc["mesaj"] = "Çok oranlı, hepsi uyumlu"
            else:
                sonuc["mesaj"] = "Tutarsızlık: " + " | ".join(tutarsizliklar) if tutarsizliklar else "Toplam uyumsuz"
        else:
            sonuc["mesaj"] = f"Çok oranlı ({', '.join('%' + str(o) for o in oranlar)}), detay yok"

    else:
        if matrah > 0:
            tahmini_oran = (abs(kdv) / matrah * Decimal("100")).quantize(Decimal("1"))
            sonuc["mesaj"] = f"Oran belirsiz (~%{tahmini_oran})"
            if abs(tahmini_oran - Decimal("20")) <= Decimal("1") and abs(abs(kdv) - matrah * Decimal("0.20")) <= TOLERANS_ORAN:
                sonuc["uyumlu"] = True
                sonuc["oran_listesi"] = [20]
                sonuc["mesaj"] = "Tahmini %20, uyumlu"

    for o in oranlar:
        if o not in GECERLI_ORANLAR:
            sonuc["mesaj"] += f" ⚠️ Geçersiz oran: %{o}"

    return sonuc


def coklu_oran_dogrula(faturalar: List[Dict]) -> List[Dict]:
    """Birden fazla faturayı toplu kontrol et."""
    return [oran_dogrula(f) for f in faturalar]
