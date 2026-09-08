"""db.py modülü için testler."""
import os
import tempfile
import pytest
from pathlib import Path

from db import KdvDatabase


@pytest.fixture
def gecici_db(tmp_path):
    """Geçici test veritabanı oluşturur."""
    db_yolu = tmp_path / "test_history.db"
    db = KdvDatabase(yol=db_yolu)
    yield db
    db.kapat()


class TestKdvDatabase:
    def test_tablo_olusturma(self, gecici_db):
        """Tablolar başarıyla oluşturulmalı."""
        tablolar = gecici_db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        tablo_adlari = {t["name"] for t in tablolar}
        assert "kontroller" in tablo_adlari
        assert "eksik_belgeler" in tablo_adlari

    def test_kontrol_kaydet(self, gecici_db):
        """Kontrol başarıyla kaydedilmeli."""
        ozet = {
            "fatura_adet": 10,
            "cetvel_sayisi": 8,
            "eslesen": 5,
            "tutar_farki": 2,
            "vkn_farki": 1,
            "cetvelde_yok": 1,
            "faturada_yok": 1,
            "mukerrer": 0,
            "parse_sorunu": 0,
            "toplam_kdv": "2000",
        }
        eksik = [
            {"belge_no": "FTN001", "vkn": "12345678901",
             "unvan": "Test A.Ş.", "kdv": "200", "tarih": "2024-01-15"},
        ]
        kid = gecici_db.kontrol_kaydet(ozet, eksik, "2024-01")
        assert kid > 0

    def test_son_kontrol(self, gecici_db):
        """Son kontrol doğru dönmeli."""
        ozet = {
            "fatura_adet": 5, "cetvel_sayisi": 3,
            "eslesen": 3, "tutar_farki": 0, "vkn_farki": 0,
            "cetvelde_yok": 0, "faturada_yok": 0,
            "mukerrer": 0, "parse_sorunu": 0, "toplam_kdv": "500",
        }
        gecici_db.kontrol_kaydet(ozet, [], "2024-06")
        son = gecici_db.son_kontrol()
        assert son is not None
        assert son["donem"] == "2024-06"
        assert son["fatura_sayisi"] == 5

    def test_eslesen_orani(self, gecici_db):
        """Eşleşme oranı hesaplanmalı."""
        ozet = {
            "fatura_adet": 10, "cetvel_sayisi": 8,
            "eslesen": 7, "tutar_farki": 0, "vkn_farki": 0,
            "cetvelde_yok": 0, "faturada_yok": 0,
            "mukerrer": 0, "parse_sorunu": 0, "toplam_kdv": "1000",
        }
        kid = gecici_db.kontrol_kaydet(ozet, [], "2024-03")
        oran = gecici_db.eslesen_orani(kid)
        assert abs(oran - 70.0) < 0.1

    def test_eksik_belgeler_getir(self, gecici_db):
        """Eksik belgeler doğru dönmeli."""
        ozet = {
            "fatura_adet": 3, "cetvel_sayisi": 2,
            "eslesen": 1, "tutar_farki": 0, "vkn_farki": 0,
            "cetvelde_yok": 1, "faturada_yok": 0,
            "mukerrer": 0, "parse_sorunu": 0, "toplam_kdv": "300",
        }
        eksik = [
            {"belge_no": "FTN001", "vkn": "111", "unvan": "A",
             "kdv": "100", "tarih": "2024-01-01"},
            {"belge_no": "FTN002", "vkn": "222", "unvan": "B",
             "kdv": "200", "tarih": "2024-01-02"},
        ]
        kid = gecici_db.kontrol_kaydet(ozet, eksik)
        bulunan = gecici_db.eksik_belgeler_getir(kid)
        assert len(bulunan) == 2

    def test_temizle(self, gecici_db):
        """Veritabanı temizlenmeli."""
        ozet = {
            "fatura_adet": 1, "cetvel_sayisi": 1,
            "eslesen": 1, "tutar_farki": 0, "vkn_farki": 0,
            "cetvelde_yok": 0, "faturada_yok": 0,
            "mukerrer": 0, "parse_sorunu": 0, "toplam_kdv": "100",
        }
        gecici_db.kontrol_kaydet(ozet, [])
        gecici_db.temizle()
        assert gecici_db.son_kontrol() is None
