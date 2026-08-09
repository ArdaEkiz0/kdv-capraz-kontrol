"""SQLite tabanlı geçmiş takip ve trend analizi.

JSON dosyalarının (gecmis.json) yerini alır:
- Hızlı sorgular
- Trend analizi
- Aylık/haftalık karşılaştırma
"""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from decimal import Decimal
from typing import List, Dict, Optional

DB_YOLU = Path.home() / ".kdv_kontrol" / "history.db"


class KdvDatabase:
    def __init__(self, yol: Optional[Path] = None):
        self.yol = yol or DB_YOLU
        self.yol.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.yol), detect_types=sqlite3.PARSE_DECLTYPES)
        self.conn.row_factory = sqlite3.Row
        self._tablolari_olustur()

    def _tablolari_olustur(self):
        """Şemayı kur (idempotent)."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS kontroller (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zaman TEXT NOT NULL,
                donem TEXT,
                fatura_sayisi INTEGER DEFAULT 0,
                cetvel_sayisi INTEGER DEFAULT 0,
                eslesen INTEGER DEFAULT 0,
                tutar_farki INTEGER DEFAULT 0,
                vkn_farki INTEGER DEFAULT 0,
                cetvelde_yok INTEGER DEFAULT 0,
                faturada_yok INTEGER DEFAULT 0,
                mukerrer INTEGER DEFAULT 0,
                parse_sorunu INTEGER DEFAULT 0,
                toplam_kdv TEXT DEFAULT '0',
                eksik_kdv TEXT DEFAULT '0'
            );

            CREATE TABLE IF NOT EXISTS eksik_belgeler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kontrol_id INTEGER NOT NULL,
                belge_no TEXT,
                vkn TEXT,
                unvan TEXT,
                kdv TEXT,
                tarih TEXT,
                FOREIGN KEY (kontrol_id) REFERENCES kontroller(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS tutar_farklari (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kontrol_id INTEGER NOT NULL,
                belge_no TEXT,
                vkn TEXT,
                matrah_farki TEXT,
                kdv_farki TEXT,
                FOREIGN KEY (kontrol_id) REFERENCES kontroller(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_kontrol_zaman
                ON kontroller(zaman);
            CREATE INDEX IF NOT EXISTS idx_eksik_kontrol
                ON eksik_belgeler(kontrol_id);
            CREATE INDEX IF NOT EXISTS idx_eksik_belge
                ON eksik_belgeler(belge_no);
        """)
        self.conn.commit()

    def kontrol_kaydet(
        self,
        ozet: Dict,
        eksik_belgeler: List[Dict],
        donem: str = "",
    ) -> int:
        """Bir kontrolün tüm verilerini kaydet."""
        zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        eksik_kdv_toplam = sum(
            (Decimal(str(r.get("kdv") or 0)) for r in eksik_belgeler),
            Decimal("0"),
        )

        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO kontroller (
                zaman, donem, fatura_sayisi, cetvel_sayisi,
                eslesen, tutar_farki, vkn_farki, cetvelde_yok,
                faturada_yok, mukerrer, parse_sorunu,
                toplam_kdv, eksik_kdv
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                zaman,
                donem,
                ozet.get("fatura_adet", 0),
                ozet.get("cetvel_adet", 0),
                ozet.get("eslesen", 0),
                ozet.get("tutar_farki", 0),
                ozet.get("vkn_farki", 0),
                ozet.get("cetvelde_yok", 0),
                ozet.get("faturada_yok", 0),
                ozet.get("mukerrer", 0),
                ozet.get("parse_sorunu", 0),
                str(ozet.get("toplam_kdv", "0")),
                str(eksik_kdv_toplam),
            ),
        )
        kontrol_id = cur.lastrowid

        # Eksik belgeleri toplu ekle
        if eksik_belgeler:
            self.conn.executemany(
                """
                INSERT INTO eksik_belgeler
                    (kontrol_id, belge_no, vkn, unvan, kdv, tarih)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        kontrol_id,
                        r.get("belge_no") or "",
                        r.get("vkn") or "",
                        r.get("unvan") or "",
                        str(r.get("kdv") or "0"),
                        r.get("tarih") or "",
                    )
                    for r in eksik_belgeler
                ],
            )
        self.conn.commit()
        return kontrol_id

    def son_kontrol(self) -> Optional[Dict]:
        """En son yapılan kontrol."""
        row = self.conn.execute(
            "SELECT * FROM kontroller ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    def eslesen_orani(self, kontrol_id: int) -> float:
        """Belirli bir kontrol için eşleşme yüzdesi."""
        row = self.conn.execute(
            "SELECT eslesen, fatura_sayisi FROM kontroller WHERE id = ?",
            (kontrol_id,),
        ).fetchone()
        if not row or row["fatura_sayisi"] == 0:
            return 0.0
        return (row["eslesen"] / row["fatura_sayisi"]) * 100

    def trend_aylik(self, ay_sayisi: int = 12) -> List[Dict]:
        """Son N ayın trend verileri."""
        baslangic = (datetime.now() - timedelta(days=ay_sayisi * 31)).strftime("%Y-%m-%d")
        return [
            dict(r)
            for r in self.conn.execute(
                """
                SELECT * FROM kontroller
                WHERE zaman >= ?
                ORDER BY zaman ASC
                """,
                (baslangic,),
            ).fetchall()
        ]

    def eksik_belgeler_getir(self, kontrol_id: int) -> List[Dict]:
        """Bir kontroldeki eksik belgeler."""
        return [
            dict(r)
            for r in self.conn.execute(
                "SELECT * FROM eksik_belgeler WHERE kontrol_id = ?",
                (kontrol_id,),
            ).fetchall()
        ]

    def kapanan_eksikler(self, onceki_id: int, simdi_id: int) -> List[str]:
        """Bir önceki kontrolde eksik olup şimdi kapananlar."""
        return [
            r["belge_no"]
            for r in self.conn.execute(
                """
                SELECT belge_no FROM eksik_belgeler
                WHERE kontrol_id = ? AND belge_no NOT IN (
                    SELECT belge_no FROM eksik_belgeler WHERE kontrol_id = ?
                )
                """,
                (onceki_id, simdi_id),
            ).fetchall()
            if r["belge_no"]
        ]

    def yeni_eksikler(self, onceki_id: int, simdi_id: int) -> List[str]:
        """Önceki kontrolde yokken şimdi eksik olanlar."""
        return [
            r["belge_no"]
            for r in self.conn.execute(
                """
                SELECT belge_no FROM eksik_belgeler
                WHERE kontrol_id = ? AND belge_no NOT IN (
                    SELECT belge_no FROM eksik_belgeler WHERE kontrol_id = ?
                )
                """,
                (simdi_id, onceki_id),
            ).fetchall()
            if r["belge_no"]
        ]

    def tekrarlayan_eksikler(self, ay_sayisi: int = 3) -> List[Dict]:
        """Son N ayda sürekli eksik olan belgeler (alarm için)."""
        return [
            dict(r)
            for r in self.conn.execute(
                """
                SELECT belge_no, vkn, COUNT(*) as tekrar_sayisi,
                       SUM(CAST(kdv AS REAL)) as toplam_kdv
                FROM eksik_belgeler
                WHERE kontrol_id IN (
                    SELECT id FROM kontroller ORDER BY id DESC LIMIT ?
                )
                GROUP BY belge_no
                HAVING tekrar_sayisi >= 2
                ORDER BY tekrar_sayisi DESC
                """,
                (ay_sayisi,),
            ).fetchall()
        ]

    def vkn_risk_skorlari(self) -> List[Dict]:
        """Satıcı bazlı risk skoru (yüksek tutar + sık eksik = yüksek risk)."""
        return [
            dict(r)
            for r in self.conn.execute(
                """
                SELECT vkn,
                       unvan,
                       COUNT(*) as eksik_sayisi,
                       SUM(CAST(kdv AS REAL)) as toplam_eksik_kdv,
                       COUNT(DISTINCT kontrol_id) as farkli_kontrol
                FROM eksik_belgeler
                WHERE vkn != ''
                GROUP BY vkn
                ORDER BY toplam_eksik_kdv DESC
                LIMIT 20
                """
            ).fetchall()
        ]

    def temizle(self):
        """Tüm verileri sil (test/reset için)."""
        self.conn.executescript(
            "DELETE FROM tutar_farklari; DELETE FROM eksik_belgeler; DELETE FROM kontroller;"
        )
        self.conn.commit()

    def kapat(self):
        self.conn.close()


# Singleton instance
_db = None

def db_al() -> KdvDatabase:
    global _db
    if _db is None:
        _db = KdvDatabase()
    return _db
