"""matcher.py modülü için unit testler."""
import pytest
from decimal import Decimal

from matcher import (
    vkn_uyumlu,
    tutarlar_uyumlu,
    fark_metni,
    duplikat_bul,
    tevkifat_kes,
    tevkifat_detay,
    capraz_kontrol,
    capraz_kontrol_iade_destekli,
    DURUM_OK,
    DURUM_TUTAR_FARKI,
    DURUM_VKN_FARKI,
    DURUM_CETVELDE_YOK,
    DURUM_FATURADA_YOK,
    DURUM_MUKERRER,
    DURUM_TEVKIFATLI,
    DURUM_PARSE_SORUNU,
)


class TestVknUyumlu:
    def test_esit(self):
        f = {"satici_vkn": "12345678901"}
        c = {"vkn": "12345678901"}
        assert vkn_uyumlu(f, c) is True

    def test_farkli(self):
        f = {"satici_vkn": "12345678901"}
        c = {"vkn": "99988877766"}
        assert vkn_uyumlu(f, c) is False

    def test_birinin_icinde_bos(self):
        f = {"satici_vkn": ""}
        c = {"vkn": "12345678901"}
        assert vkn_uyumlu(f, c) is True


class TestTutarlarUyumlu:
    def test_esit(self):
        f = {"matrah": Decimal("1000"), "kdv": Decimal("200")}
        c = {"matrah": Decimal("1000"), "kdv": Decimal("200")}
        assert tutarlar_uyumlu(f, c) is True

    def test_tolerans_icinde(self):
        f = {"matrah": Decimal("1000.01"), "kdv": Decimal("200.01")}
        c = {"matrah": Decimal("1000.00"), "kdv": Decimal("200.00")}
        assert tutarlar_uyumlu(f, c) is True

    def test_farkli(self):
        f = {"matrah": Decimal("1000"), "kdv": Decimal("200")}
        c = {"matrah": Decimal("1000"), "kdv": Decimal("250")}
        assert tutarlar_uyumlu(f, c) is False

    def test_iade_mutlak(self):
        f = {"matrah": Decimal("-1000"), "kdv": Decimal("-200"),
             "fatura_tipi": "IADE"}
        c = {"matrah": Decimal("-1000"), "kdv": Decimal("200")}
        assert tutarlar_uyumlu(f, c) is True

    def test_iade_farkli(self):
        f = {"matrah": Decimal("-1000"), "kdv": Decimal("-200"),
             "fatura_tipi": "IADE"}
        c = {"matrah": Decimal("1000"), "kdv": Decimal("200")}
        assert tutarlar_uyumlu(f, c) is False


class TestFarkMetni:
    def test_normal(self):
        sonuc = fark_metni(Decimal("1000"), Decimal("200"))
        assert "1.000,00" in sonuc
        assert "200,00" in sonuc

    def test_none(self):
        sonuc = fark_metni(None, Decimal("200"))
        assert "Fatura: " in sonuc
        assert "Cetvel: 200,00" in sonuc


class TestDuplikatBul:
    def test_duplikat_var(self):
        liste = [{"belge": "A"}, {"belge": "A"}, {"belge": "B"}]
        sonuc = duplikat_bul(liste, lambda x: x["belge"])
        assert sonuc == {"A": 2}

    def test_duplikat_yok(self):
        liste = [{"belge": "A"}, {"belge": "B"}]
        sonuc = duplikat_bul(liste, lambda x: x["belge"])
        assert sonuc == {}


class TestTevkifatKes:
    def test_klasik_oran(self):
        # Bos fatura_tipi -> gate disinda kalir, tevkifat denenir
        # f_matrah/c_matrah = 700/1000 = 0.70, kdv/c_kdv = 140/200 = 0.70
        f = {"kdv": Decimal("200"), "matrah": Decimal("700"),
             "fatura_tipi": ""}
        c = {"kdv": Decimal("140"), "matrah": Decimal("1000")}
        sonuc = tevkifat_kes(f, c)
        assert sonuc is not None

    def test_tip_kontrol(self):
        f = {"kdv": Decimal("200"), "matrah": Decimal("700"),
             "fatura_tipi": "SATIS"}
        c = {"kdv": Decimal("140"), "matrah": Decimal("1000")}
        sonuc = tevkifat_kes(f, c)
        assert sonuc is None


class TestCaprazKontrol:
    def test_eslesen(self):
        faturalar = [{
            "belge_no": "FTN001", "tarih": "2024-01-15",
            "satici_vkn": "12345678901", "satici_unvan": "Test A.Ş.",
            "matrah": Decimal("1000"), "kdv": Decimal("200"),
            "toplam": Decimal("1200"), "oranlar": [20],
            "fatura_tipi": "", "oran_kontrol": "OK",
            "notlar": [], "dosya": "test.xml", "tip": "xml",
        }]
        cetvel = [{
            "belge_no": "FTN001", "vkn": "12345678901",
            "tarih": "2024-01-15", "matrah": Decimal("1000"),
            "kdv": Decimal("200"), "unvan": "Test A.Ş.", "notlar": [],
        }]
        sonuc, ozet = capraz_kontrol(faturalar, cetvel)
        assert ozet["eslesen"] == 1
        assert sonuc[0]["durum"] == DURUM_OK

    def test_tutar_farki(self):
        faturalar = [{
            "belge_no": "FTN002", "tarih": "2024-01-15",
            "satici_vkn": "12345678901", "satici_unvan": "Test A.Ş.",
            "matrah": Decimal("1000"), "kdv": Decimal("200"),
            "toplam": Decimal("1200"), "oranlar": [20],
            "fatura_tipi": "", "oran_kontrol": "OK",
            "notlar": [], "dosya": "test.xml", "tip": "xml",
        }]
        cetvel = [{
            "belge_no": "FTN002", "vkn": "12345678901",
            "tarih": "2024-01-15", "matrah": Decimal("1000"),
            "kdv": Decimal("250"), "unvan": "Test A.Ş.", "notlar": [],
        }]
        sonuc, ozet = capraz_kontrol(faturalar, cetvel)
        assert ozet["tutar_farki"] == 1

    def test_cetvelde_yok(self):
        faturalar = [{
            "belge_no": "FTN003", "tarih": "2024-01-15",
            "satici_vkn": "12345678901", "satici_unvan": "Test A.Ş.",
            "matrah": Decimal("1000"), "kdv": Decimal("200"),
            "toplam": Decimal("1200"), "oranlar": [20],
            "fatura_tipi": "", "oran_kontrol": "OK",
            "notlar": [], "dosya": "test.xml", "tip": "xml",
        }]
        sonuc, ozet = capraz_kontrol(faturalar, [])
        assert ozet["cetvelde_yok"] == 1

    def test_faturada_yok(self):
        cetvel = [{
            "belge_no": "FTN004", "vkn": "12345678901",
            "tarih": "2024-01-15", "matrah": Decimal("1000"),
            "kdv": Decimal("200"), "unvan": "Test A.Ş.", "notlar": [],
        }]
        sonuc, ozet = capraz_kontrol([], cetvel)
        assert ozet["faturada_yok"] == 1


class TestCaprazKontrolIadeDestekli:
    def test_iade_eslesme(self):
        faturalar = [{
            "belge_no": "IADE001", "tarih": "2024-02-10",
            "satici_vkn": "12345678901", "satici_unvan": "Test",
            "matrah": Decimal("-1000"), "kdv": Decimal("-200"),
            "toplam": Decimal("-1200"), "oranlar": [20],
            "fatura_tipi": "IADE", "oran_kontrol": "OK",
            "notlar": [], "dosya": "iade.xml", "tip": "xml",
        }]
        cetvel = [{
            "belge_no": "IADE001", "vkn": "12345678901",
            "tarih": "2024-02-10", "matrah": None,
            "kdv": Decimal("200"), "unvan": "Test", "notlar": [],
        }]
        sonuc, ozet = capraz_kontrol_iade_destekli(faturalar, cetvel)
        assert any(s["durum"] == "İADE EŞLEŞTİ" for s in sonuc)
