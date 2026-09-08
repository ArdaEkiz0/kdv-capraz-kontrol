import json
import logging
import os
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

YOL = os.path.dirname(os.path.abspath(__file__))
AYAR_YOLU = os.path.join(YOL, "ayar.json")
GECMIS_YOLU = os.path.join(YOL, "gecmis.json")

# Varsayılan ayarlar
VARSAYILAN_AYARLAR = {
    "fatura_klasor": "",
    "cetvel_klasor": "",
    "rapor_klasor": "",
    "fatura_dosyalari": [],
    "cetvel_dosyalari": [],
    "pencere_boyut": "1280x780",
    "son_donem": "",
    "son_faturalar": [],
    "son_cetveller": [],
    "otomatik_guncelleme": True,
    "teema": "varsayilan",
    "dil": "tr",
}


def _yukle(yol: str, varsayilan: Any) -> Any:
    try:
        with open(yol, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return varsayilan
    except Exception as hata:
        logger.warning("Ayar dosyasi okunamadi (%s): %s — varsayilan kullaniliyor", yol, hata)
        return varsayilan


def _kaydet(yol: str, veri: Any) -> None:
    try:
        with open(yol, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=2)
    except Exception as hata:
        logger.warning("Ayar dosyasi kaydedilemedi (%s): %s", yol, hata)


def ayar_yukle() -> dict[str, Any]:
    yuklenen = _yukle(AYAR_YOLU, {})
    # Eksik anahtarları varsayılan değerlerle doldur
    for anahtar, deger in VARSAYILAN_AYARLAR.items():
        if anahtar not in yuklenen:
            yuklenen[anahtar] = deger
    return yuklenen


def ayar_kaydet(ayar: dict[str, Any]) -> None:
    _kaydet(AYAR_YOLU, ayar)


def ayar_al(anahtar: str, varsayilan: Any = None) -> Any:
    """Tek bir ayar değerini okur."""
    ayarlar = ayar_yukle()
    return ayarlar.get(anahtar, varsayilan)


def ayar_guncelle(**kwargs: Any) -> None:
    """Birden fazla ayarı aynı anda günceller."""
    ayarlar = ayar_yukle()
    ayarlar.update(kwargs)
    ayar_kaydet(ayarlar)


def gecmis_yukle() -> list[dict[str, Any]]:
    return _yukle(GECMIS_YOLU, [])


def gecmis_kaydet(gecmis: list[dict[str, Any]]) -> None:
    _kaydet(GECMIS_YOLU, gecmis[-12:])


def gecmis_ekle(ozet, eksikler):
    gecmis = gecmis_yukle()
    gecmis.append({
        "zaman": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "eslesen": ozet.get("eslesen", 0),
        "tutar_farki": ozet.get("tutar_farki", 0),
        "cetvelde_yok": ozet.get("cetvelde_yok", 0),
        "faturada_yok": ozet.get("faturada_yok", 0),
        "eksikler": sorted(set(eksikler)),
    })
    gecmis_kaydet(gecmis)


def gecmis_karsilastir(eksikler):
    """Bir onceki kontrole gore kapanan ve yeni eksikleri bulur."""
    gecmis = gecmis_yukle()
    if not gecmis:
        return None
    onceki = gecmis[-1]
    once = set(onceki.get("eksikler", []))
    simdi = set(eksikler)
    return {
        "zaman": onceki.get("zaman", ""),
        "kapanan": sorted(once - simdi),
        "yeni": sorted(simdi - once),
        "onceki_eslesen": onceki.get("eslesen"),
        "onceki_cetvelde_yok": onceki.get("cetvelde_yok"),
    }
