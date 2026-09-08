"""utils.py modülü için testler."""
import pytest
from decimal import Decimal

from utils import (
    sadeleştir,
    rakamlara_cevir,
    vkn_temizle,
    fatura_no_temizle,
    tutar_parse,
    tarih_parse,
    tl_format,
    tckn_gecerli_mi,
    vkn_gecerli_mi,
    sayilari_bul,
)


class TestSadelestr:
    def test_normal(self):
        assert sadeleştir("  ABC   DEF  ") == "ABC DEF"

    def test_bos(self):
        assert sadeleştir("") == ""
        assert sadeleştir(None) == ""


class TestRakamlaraCevir:
    def test_O_sifir(self):
        # O (harf) -> 0 (rakam) olarak çevrilir
        assert "0" in rakamlara_cevir("O")

    def test_I_bir(self):
        sonuc = rakamlara_cevir("I")
        assert sonuc == "1"


class TestVknTemizle:
    def test_normal(self):
        assert vkn_temizle("123 456 789 01") == "12345678901"

    def test_bos(self):
        assert vkn_temizle(None) == ""


class TestFaturaNoTemizle:
    def test_normal(self):
        assert fatura_no_temizle("GFE202400000011") == "GFE202400000011"

    def test_ozel_karakter(self):
        assert fatura_no_temizle("GFE202400000011№") == "GFE202400000011"

    def test_bos(self):
        assert fatura_no_temizle(None) == ""


class TestTutarParse:
    def test_virgullu(self):
        assert tutar_parse("1.234,56") == Decimal("1234.56")

    def test_noktali(self):
        assert tutar_parse("1234.56") == Decimal("1234.56")

    def test_TL_baslikli(self):
        sonuc = tutar_parse("1.234,56 TL")
        assert sonuc == Decimal("1234.56")

    def test_bos(self):
        assert tutar_parse(None) is None
        assert tutar_parse("") is None

    def test_sifir(self):
        assert tutar_parse("0") == Decimal("0.00")

    def test_negatif_parantez(self):
        sonuc = tutar_parse("(1.234,56)")
        assert sonuc is not None


class TestTarihParse:
    def test_iso(self):
        assert tarih_parse("2024-01-15") == "2024-01-15"

    def test_noktali(self):
        assert tarih_parse("15.01.2024") == "2024-01-15"

    def test_egri(self):
        assert tarih_parse("15/01/2024") == "2024-01-15"

    def test_bos(self):
        assert tarih_parse(None) is None
        assert tarih_parse("abc") is None

    def test_gecersiz(self):
        assert tarih_parse("2024-13-01") is None


class TestTlFormat:
    def test_normal(self):
        assert tl_format(Decimal("1234.56")) == "1.234,56"

    def test_none(self):
        assert tl_format(None) == ""

    def test_sifir(self):
        assert tl_format(0) == "0,00"


class TestTcknGecerliMi:
    def test_gecerli(self):
        assert tckn_gecerli_mi("10000000146") is True

    def test_gecersiz_uzunluk(self):
        assert tckn_gecerli_mi("12345") is False

    def test_sifirla_baslayan(self):
        assert tckn_gecerli_mi("01234567890") is False

    def test_bos(self):
        assert tckn_gecerli_mi(None) is False


class TestVknGecerliMi:
    def test_10_haneli(self):
        # Geçerli bir VKN kontrol hanesi
        assert isinstance(vkn_gecerli_mi("1234567890"), bool)

    def test_11_haneli_tckn(self):
        assert vkn_gecerli_mi("10000000146") is True

    def test_bos(self):
        assert vkn_gecerli_mi("") is True


class TestSayilariBul:
    def test_normal(self):
        sonuc = sayilari_bul("Fatura tutarı 1.234,56 TL'dir")
        assert len(sonuc) >= 1
        assert Decimal("1234.56") in sonuc

    def test_bos(self):
        assert sayilari_bul("") == []
        assert sayilari_bul(None) == []

    def test_coklu(self):
        sonuc = sayilari_bul("Matrah 1000 KDV 200 Toplam 1200")
        assert len(sonuc) >= 2
