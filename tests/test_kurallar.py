"""kurallar.py modülü için testler."""
import pytest
import tempfile
import os
import json
from decimal import Decimal

# Kurallar modülünü test etmek için DOSYA yolunu geçici dizine yönlendir
import kurallar


@pytest.fixture(autouse=True)
def kural_temp(tmp_path):
    """Geçici kurallar.json dosyası oluşturur."""
    kurallar.DOSYA = str(tmp_path / "kurallar.json")
    yield tmp_path
    if os.path.exists(kurallar.DOSYA):
        os.remove(kurallar.DOSYA)


class TestKuralBul:
    def test_unvan_eslesme(self):
        kurallar_listesi = [
            {"ad": "Opet", "eslesme": "OPET", "oran": "0.90", "onayla": False},
        ]
        sonuc = kurallar.kural_bul(kurallar_listesi, unvan="OPET AKARYAKIT A.Ş.")
        assert sonuc is not None
        assert sonuc["ad"] == "Opet"

    def test_vkn_eslesme(self):
        kurallar_listesi = [
            {"ad": "Firma", "eslesme": "1234567890", "oran": "", "onayla": False},
        ]
        sonuc = kurallar.kural_bul(kurallar_listesi, vkn="1234567890")
        assert sonuc is not None

    def test_eslesme_yok(self):
        kurallar_listesi = [
            {"ad": "Opet", "eslesme": "OPET", "oran": "0.90", "onayla": False},
        ]
        sonuc = kurallar.kural_bul(kurallar_listesi, unvan="BILINMEYEN FIRMA")
        assert sonuc is None

    def test_bos_liste(self):
        assert kurallar.kural_bul([], unvan="X") is None
        assert kurallar.kural_bul(None, unvan="X") is None


class TestBeklenenOran:
    def test_normal(self):
        kural = {"oran": "0.90"}
        sonuc = kurallar.beklenen_oran(kural)
        assert sonuc == Decimal("0.90")

    def test_bos(self):
        assert kurallar.beklenen_oran(None) is None
        assert kurallar.beklenen_oran({"oran": ""}) is None

    def test_gecersiz(self):
        assert kurallar.beklenen_oran({"oran": "abc"}) is None

    def test_sinir_disi(self):
        # 0 veya 1'in dışında olmalı
        assert kurallar.beklenen_oran({"oran": "0"}) is None
        assert kurallar.beklenen_oran({"oran": "1"}) is None


class TestKurallariOkuKaydet:
    def test_bos_dosya(self, tmp_path):
        kurallar.DOSYA = str(tmp_path / "yok.json")
        sonuc = kurallar.kurallari_oku()
        assert sonuc == []

    def test_kaydet_ve_oku(self, tmp_path):
        kurallar.DOSYA = str(tmp_path / "kurallar.json")
        liste = [
            {"ad": "Opet", "eslesme": "OPET", "oran": "0.90", "onayla": False},
            {"ad": "Bos", "eslesme": "", "oran": "", "onayla": False},
        ]
        kaydedilen = kurallar.kurallari_kaydet(liste)
        assert len(kaydedilen) == 1  # boş eslesme'li elendi
        okunan = kurallar.kurallari_oku()
        assert len(okunan) == 1
        assert okunan[0]["ad"] == "Opet"
