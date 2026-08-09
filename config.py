import json
import os
from datetime import datetime

YOL = os.path.dirname(os.path.abspath(__file__))
AYAR_YOLU = os.path.join(YOL, "ayar.json")
GECMIS_YOLU = os.path.join(YOL, "gecmis.json")


def _yukle(yol, varsayilan):
    try:
        with open(yol, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return varsayilan


def _kaydet(yol, veri):
    try:
        with open(yol, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def ayar_yukle():
    return _yukle(AYAR_YOLU, {
        "fatura_klasor": "", "cetvel_klasor": "", "rapor_klasor": "",
        "fatura_dosyalari": [], "cetvel_dosyalari": [],
    })


def ayar_kaydet(ayar):
    _kaydet(AYAR_YOLU, ayar)


def gecmis_yukle():
    return _yukle(GECMIS_YOLU, [])


def gecmis_kaydet(gecmis):
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
