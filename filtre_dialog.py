"""Gelişmiş filtre ve arama penceresi.

Tablo üzerinde şu filtreleri sağlar:
- Tarih aralığı (gg/aa/yyyy - gg/aa/yyyy)
- VKN (içerir/eşittir)
- Tutar aralığı (min-max)
- Durum (Eşleşti/Sorunlu/Tümü)
- Metin arama (belge no, ünvan)
"""
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk
from decimal import Decimal, InvalidOperation
from typing import Dict, Callable, List


class GelismisFiltreDialog:
    """Gelişmiş filtre penceresi."""

    def __init__(self, parent, sonuc_satirlari: List[Dict], uygula_callback: Callable):
        self.parent = parent
        self.sonuc_satirlari = sonuc_satirlari
        self.uygula_callback = uygula_callback
        self.filtre = self._varsayilan_filtre()
        self._pencere_ac()

    def _varsayilan_filtre(self) -> Dict:
        bitis = datetime.now().strftime("%d.%m.%Y")
        baslangic = (datetime.now() - timedelta(days=90)).strftime("%d.%m.%Y")
        return {
            "tarih_baslangic": baslangic,
            "tarih_bitis": bitis,
            "vkn": "",
            "belge_no": "",
            "unvan": "",
            "min_tutar": "",
            "max_tutar": "",
            "durumlar": set(),
        }

    def _pencere_ac(self):
        self.pencere = tk.Toplevel(self.parent)
        self.pencere.title("Gelişmiş Filtre")
        self.pencere.geometry("520x620")
        self.pencere.transient(self.parent)
        self.pencere.grab_set()
        self._arayuz_kur()

    def _arayuz_kur(self):
        ana = ttk.Frame(self.pencere, padding=12)
        ana.pack(fill="both", expand=True)

        # ---------- Tarih Aralığı ----------
        tarih_frame = ttk.LabelFrame(ana, text="📅 Tarih Aralığı", padding=8)
        tarih_frame.pack(fill="x", pady=(0, 8))

        ttk.Label(tarih_frame, text="Başlangıç (gg.aa.yyyy):").grid(row=0, column=0, sticky="w", pady=2)
        self.baslangic_var = tk.StringVar(value=self.filtre["tarih_baslangic"])
        ttk.Entry(tarih_frame, textvariable=self.baslangic_var, width=14).grid(row=0, column=1, padx=4)

        ttk.Label(tarih_frame, text="Bitiş (gg.aa.yyyy):").grid(row=1, column=0, sticky="w", pady=2)
        self.bitis_var = tk.StringVar(value=self.filtre["tarih_bitis"])
        ttk.Entry(tarih_frame, textvariable=self.bitis_var, width=14).grid(row=1, column=1, padx=4)

        hizli_frame = ttk.Frame(tarih_frame)
        hizli_frame.grid(row=2, column=0, columnspan=2, pady=(8, 0))
        ttk.Label(hizli_frame, text="Hızlı:").pack(side="left", padx=(0, 4))
        for gun, etiket in [(7, "7 gün"), (30, "30 gün"), (90, "3 ay"), (365, "1 yıl")]:
            ttk.Button(
                hizli_frame,
                text=etiket,
                width=8,
                command=lambda g=gun: self._hizli_tarih(g),
            ).pack(side="left", padx=2)

        # ---------- Metin Filtreleri ----------
        metin_frame = ttk.LabelFrame(ana, text="🔎 Metin Arama", padding=8)
        metin_frame.pack(fill="x", pady=(0, 8))

        ttk.Label(metin_frame, text="Belge No:").grid(row=0, column=0, sticky="w", pady=2)
        self.belge_var = tk.StringVar()
        ttk.Entry(metin_frame, textvariable=self.belge_var, width=20).grid(row=0, column=1, padx=4, sticky="we")

        ttk.Label(metin_frame, text="VKN:").grid(row=1, column=0, sticky="w", pady=2)
        self.vkn_var = tk.StringVar()
        ttk.Entry(metin_frame, textvariable=self.vkn_var, width=20).grid(row=1, column=1, padx=4, sticky="we")

        ttk.Label(metin_frame, text="Ünvan (içerir):").grid(row=2, column=0, sticky="w", pady=2)
        self.unvan_var = tk.StringVar()
        ttk.Entry(metin_frame, textvariable=self.unvan_var, width=20).grid(row=2, column=1, padx=4, sticky="we")

        metin_frame.columnconfigure(1, weight=1)

        # ---------- Tutar Aralığı ----------
        tutar_frame = ttk.LabelFrame(ana, text="💰 Tutar Aralığı (TL)", padding=8)
        tutar_frame.pack(fill="x", pady=(0, 8))

        ttk.Label(tutar_frame, text="Min KDV:").grid(row=0, column=0, sticky="w", pady=2)
        self.min_var = tk.StringVar()
        ttk.Entry(tutar_frame, textvariable=self.min_var, width=14).grid(row=0, column=1, padx=4)

        ttk.Label(tutar_frame, text="Max KDV:").grid(row=1, column=0, sticky="w", pady=2)
        self.max_var = tk.StringVar()
        ttk.Entry(tutar_frame, textvariable=self.max_var, width=14).grid(row=1, column=1, padx=4)

        # ---------- Durum Filtresi ----------
        durum_frame = ttk.LabelFrame(ana, text="⚠️ Durum", padding=8)
        durum_frame.pack(fill="x", pady=(0, 8))

        self.durum_degiskenler = {}
        self.tum_durumlar = [
            ("EŞLEŞTİ", "✅ Eşleşti"),
            ("TUTAR FARKI", "❌ Tutar Farkı"),
            ("VKN FARKI", "⚠️ VKN Farkı"),
            ("MÜKERRER", "🔁 Mükerrer"),
            ("CETVELDE YOK", "🚫 Cetvelde Yok"),
            ("FATURALARDA YOK", "🚫 Faturalarda Yok"),
            ("PARSE SORUNU", "❓ Okunamadı"),
        ]
        for i, (deger, etiket) in enumerate(self.tum_durumlar):
            var = tk.BooleanVar(value=False)
            self.durum_degiskenler[deger] = var
            ttk.Checkbutton(
                durum_frame, text=etiket, variable=var
            ).grid(row=i // 2, column=i % 2, sticky="w", padx=4, pady=2)

        # ---------- Butonlar ----------
        buton_frame = ttk.Frame(ana)
        buton_frame.pack(fill="x", pady=(12, 0))

        ttk.Button(
            buton_frame, text="🔄 Sıfırla", command=self._sifirla
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            buton_frame, text="İptal", command=self.pencere.destroy
        ).pack(side="right", padx=(4, 0))
        ttk.Button(
            buton_frame, text="✅ Filtrele", command=self._filtrele
        ).pack(side="right")

    # ---------- Yardımcılar ----------

    def _hizli_tarih(self, gun: int):
        bitis = datetime.now()
        baslangic = bitis - timedelta(days=gun)
        self.baslangic_var.set(baslangic.strftime("%d.%m.%Y"))
        self.bitis_var.set(bitis.strftime("%d.%m.%Y"))

    def _sifirla(self):
        varsayilan = self._varsayilan_filtre()
        self.baslangic_var.set(varsayilan["tarih_baslangic"])
        self.bitis_var.set(varsayilan["tarih_bitis"])
        self.belge_var.set("")
        self.vkn_var.set("")
        self.unvan_var.set("")
        self.min_var.set("")
        self.max_var.set("")
        for var in self.durum_degiskenler.values():
            var.set(False)

    def _tarih_ayikla(self, tarih_str: str):
        if not tarih_str:
            return None
        for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(tarih_str.strip(), fmt)
            except ValueError:
                continue
        return None

    def _tutar_ayikla(self, deger: str):
        if not deger:
            return None
        temiz = deger.replace(".", "").replace(",", ".")
        try:
            return Decimal(temiz)
        except (InvalidOperation, ValueError):
            return None

    def _filtrele(self):
        baslangic = self._tarih_ayikla(self.baslangic_var.get())
        bitis = self._tarih_ayikla(self.bitis_var.get())
        secili_durumlar = {d for d, v in self.durum_degiskenler.items() if v.get()}

        self.filtre = {
            "tarih_baslangic": baslangic,
            "tarih_bitis": bitis,
            "belge_no": self.belge_var.get().strip().upper(),
            "vkn": self.vkn_var.get().strip(),
            "unvan": self.unvan_var.get().strip().lower(),
            "min_tutar": self._tutar_ayikla(self.min_var.get()),
            "max_tutar": self._tutar_ayikla(self.max_var.get()),
            "durumlar": secili_durumlar,
        }
        self.uygula_callback(self.filtre)
        self.pencere.destroy()


def filtre_uygula(satirlar: List[Dict], f: Dict) -> List[Dict]:
    """Sonuç satırlarına filtre uygula, eşleşenleri döndür."""
    sonuc = []
    for s in satirlar:
        # Tarih filtresi
        if f.get("tarih_baslangic") or f.get("tarih_bitis"):
            t_str = s.get("tarih") or ""
            t = None
            if t_str:
                for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
                    try:
                        t = datetime.strptime(t_str, fmt)
                        break
                    except ValueError:
                        continue
            if t is None:
                continue
            if f.get("tarih_baslangic") and t < f["tarih_baslangic"]:
                continue
            if f.get("tarih_bitis") and t > f["tarih_bitis"]:
                continue

        # Metin filtreleri
        if f.get("belge_no"):
            belge = (s.get("belge_no") or "").upper()
            if f["belge_no"] not in belge:
                continue
        if f.get("vkn"):
            vkn = (s.get("vkn") or "").replace(" ", "")
            if f["vkn"] not in vkn:
                continue
        if f.get("unvan"):
            unvan = (s.get("unvan") or "").lower()
            if f["unvan"] not in unvan:
                continue

        # Tutar filtresi
        if f.get("min_tutar") is not None or f.get("max_tutar") is not None:
            kdv = s.get("kdv")
            if kdv is None:
                continue
            try:
                kdv_dec = Decimal(str(kdv))
            except (InvalidOperation, ValueError):
                continue
            if f.get("min_tutar") is not None and kdv_dec < f["min_tutar"]:
                continue
            if f.get("max_tutar") is not None and kdv_dec > f["max_tutar"]:
                continue

        # Durum filtresi
        if f.get("durumlar"):
            if s.get("durum") not in f["durumlar"]:
                continue

        sonuc.append(s)
    return sonuc
