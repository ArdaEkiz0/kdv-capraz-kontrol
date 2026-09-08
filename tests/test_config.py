"""config.py modülü için testler."""
import os
import tempfile
import pytest

import config


@pytest.fixture(autouse=True)
def gecici_dosyalar(tmp_path):
    """Test sırasında geçici dosya yolları kullan."""
    config.AYAR_YOLU = str(tmp_path / "ayar.json")
    config.GECMIS_YOLU = str(tmp_path / "gecmis.json")
    yield
    for f in [config.AYAR_YOLU, config.GECMIS_YOLU]:
        if os.path.exists(f):
            os.remove(f)


class TestGecmisEkle:
    def test_ekleme(self):
        ozet = {"eslesen": 5, "tutar_farki": 1, "cetvelde_yok": 2,
                "faturada_yok": 0}
        config.gecmis_ekle(ozet, ["FTN001", "FTN002"])
        gecmis = config.gecmis_yukle()
        assert len(gecmis) == 1
        assert gecmis[0]["eslesen"] == 5
        assert "FTN001" in gecmis[0]["eksikler"]

    def test_coklu_ekleme(self):
        for i in range(3):
            config.gecmis_ekle({"eslesen": i}, [f"FTN{i:03d}"])
        gecmis = config.gecmis_yukle()
        assert len(gecmis) == 3


class TestGecmisKarsilastir:
    def test_bos_gecmis(self):
        sonuc = config.gecmis_karsilastir(["FTN001"])
        assert sonuc is None

    def test_kapanan(self):
        config.gecmis_ekle({}, ["FTN001", "FTN002"])
        sonuc = config.gecmis_karsilastir(["FTN001"])
        assert "FTN002" in sonuc["kapanan"]

    def test_yeni(self):
        config.gecmis_ekle({}, ["FTN001"])
        sonuc = config.gecmis_karsilastir(["FTN001", "FTN003"])
        assert "FTN003" in sonuc["yeni"]
