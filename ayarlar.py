"""Kullanıcı ayarlarını sakla (son klasörler, window boyutu, vs.)."""
import json
import os
from pathlib import Path

AYAR_DOSYASI = Path.home() / ".kdv_kontrol" / "ayarlar.json"


class Ayarlar:
    """Singleton ayar yöneticisi."""

    _varsayilan = {
        "son_fatura_klasor": "",
        "son_cetvel_klasor": "",
        "son_rapor_klasor": "",
        "son_faturalar": [],
        "son_cetveller": [],
        "pencere_boyut": "1280x780",
        "son_donem": "",
        "varsayilan_tolerans": "0.02",
        "email_alici": "",
        "smtp_server": "",
        "smtp_port": 587,
        "smtp_user": "",
        "smtp_pass": "",
        "dashboard_acik": True,
    }

    def __init__(self):
        self.ayar_dosyasi = AYAR_DOSYASI
        self.ayar_dosyasi.parent.mkdir(parents=True, exist_ok=True)
        self.veri = self._yukle()

    def _yukle(self):
        try:
            with open(self.ayar_dosyasi, "r", encoding="utf-8") as f:
                yuklenen = json.load(f)
                for k, v in self._varsayilan.items():
                    yuklenen.setdefault(k, v)
                return yuklenen
        except Exception:
            return dict(self._varsayilan)

    def _kaydet(self):
        try:
            with open(self.ayar_dosyasi, "w", encoding="utf-8") as f:
                json.dump(self.veri, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def al(self, anahtar, varsayilan=None):
        return self.veri.get(anahtar, varsayilan)

    def kaydet(self, anahtar, deger):
        self.veri[anahtar] = deger
        self._kaydet()

    def toplu_kaydet(self, **kwargs):
        self.veri.update(kwargs)
        self._kaydet()


_ayar = None


def ayarlar_al() -> Ayarlar:
    global _ayar
    if _ayar is None:
        _ayar = Ayarlar()
    return _ayar
