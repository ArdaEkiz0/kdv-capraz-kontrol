"""duzeltmeler.py modülü için testler."""
import pytest
from decimal import Decimal

from duzeltmeler import (
    gurultu_mu,
    metni_duzelt,
    kdv_matrah_dogrula,
    toplam_dogrula,
    tevkifat_orani_bul,
    metin_listesi_temizle,
)


class TestGurultuMu:
    def test_bos_metin(self):
        assert gurultu_mu("") is True
        assert gurultu_mu(None) is True
        assert gurultu_mu("   ") is True

    def test_kisa_metin(self):
        assert gurultu_mu("ab") is True

    def test_tckn(self):
        assert gurultu_mu("12345678901") is True

    def test_ettn(self):
        ettn = "550e8400-e29b-41d4-a716-446655440000"
        assert gurultu_mu(ettn) is True

    def test_kdv_ozeti(self):
        assert gurultu_mu("KDV Dahil Toplam: 1200 TL") is True
        assert gurultu_mu("Vergi Toplamı: 200") is True
        assert gurultu_mu("Genel Toplam: 5000") is True

    def test_pos_satiri(self):
        assert gurultu_mu("POS No: 12345") is True
        assert gurultu_mu("Ödeme No: ABC123") is True

    def test_normal_fatura_satiri(self):
        assert gurultu_mu("ABC2026000000001 Fatura Satırı 1000 TL") is False
        assert gurultu_mu("Mal/Hizmet: Bilgisayar") is False


class TestMetniDuzelt:
    def test_bos_metin(self):
        assert metni_duzelt("") == ""
        assert metni_duzelt(None) is None

    def test_turkce_karakter(self):
        sonuc = metni_duzelt("İSTANBUL")
        assert sonuc == "ISTANBUL"

    def test_firma_adi(self):
        sonuc = metni_duzelt("ABC TİCARET A.Ş.")
        assert "TICARET" in sonuc
        assert "A.S." in sonuc

    def test_fazla_bosluk(self):
        sonuc = metni_duzelt("ABC   TİCARET    A.Ş.")
        assert "  " not in sonuc


class TestKdvDogrula:
    def test_dogru_oran(self):
        sonuc = kdv_matrah_dogrula(Decimal("1000"), Decimal("200"), Decimal("20"))
        assert sonuc["ok"] is True
        assert sonuc["beklenen"] == Decimal("200.00")

    def test_yanlis_oran(self):
        sonuc = kdv_matrah_dogrula(Decimal("1000"), Decimal("250"), Decimal("20"))
        assert sonuc["ok"] is False

    def test_eksik_deger(self):
        sonuc = kdv_matrah_dogrula(None, Decimal("200"), Decimal("20"))
        assert sonuc["ok"] is False

    def test_yuzde10(self):
        sonuc = kdv_matrah_dogrula(Decimal("5786.12"), Decimal("578.61"), Decimal("10"))
        assert sonuc["ok"] is True


class TestToplamDogrula:
    def test_dogru(self):
        sonuc = toplam_dogrula(Decimal("1000"), Decimal("200"), Decimal("1200"))
        assert sonuc["ok"] is True

    def test_yanlis(self):
        sonuc = toplam_dogrula(Decimal("1000"), Decimal("200"), Decimal("1300"))
        assert sonuc["ok"] is False

    def test_eksik(self):
        sonuc = toplam_dogrula(Decimal("1000"), Decimal("200"), None)
        assert sonuc["ok"] is False


class TestTevkifatOrani:
    def test_klasik_yuzde30(self):
        fatura_kdv = Decimal("200")
        muavin_kdv = Decimal("140")  # 200 * 0.70 = 140
        sonuc = tevkifat_orani_bul(fatura_kdv, muavin_kdv)
        assert sonuc is not None
        assert sonuc["yön"] == "klasik"
        assert sonuc["yüzde"] == 30

    def test_klasik_yuzde5(self):
        fatura_kdv = Decimal("100")
        muavin_kdv = Decimal("95")  # 100 * 0.95 = 95
        sonuc = tevkifat_orani_bul(fatura_kdv, muavin_kdv)
        assert sonuc is not None
        assert sonuc["yüzde"] == 5

    def test_ters_yon(self):
        fatura_kdv = Decimal("160")
        muavin_kdv = Decimal("200")  # ters: 200 / 160 = 1.25
        sonuc = tevkifat_orani_bul(fatura_kdv, muavin_kdv)
        assert sonuc is not None
        assert sonuc["yön"] == "ters"

    def test_eslesme_yok(self):
        fatura_kdv = Decimal("100")
        muavin_kdv = Decimal("88")  # hiçbir orana uymuyor
        sonuc = tevkifat_orani_bul(fatura_kdv, muavin_kdv)
        assert sonuc is None


class TestMetinListesiTemizle:
    def test_gurultu_elendi(self):
        satirlar = [
            "ABC2026000000001 Fatura 1000 TL",
            "12345678901",
            "KDV Dahil Toplam: 1200 TL",
            "XYZ2026000000002 Fatura 500 TL",
        ]
        sonuc = metin_listesi_temizle(satirlar)
        assert len(sonuc) == 2
        assert any("ABC" in s for s in sonuc)
        assert any("XYZ" in s for s in sonuc)

    def test_bos_liste(self):
        assert metin_listesi_temizle([]) == []
