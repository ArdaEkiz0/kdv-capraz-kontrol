"""Beyanname kutuları ile defter 191/391 toplamları karşılaştırma penceresi."""
import tkinter as tk
from decimal import Decimal, InvalidOperation
from tkinter import ttk

from beyanname import beyanname_karsilastir, defter_toplamlari
from utils import tl_format


class BeyannameDialog(tk.Toplevel):
    def __init__(self, kok, cetvel_kayitlari):
        super().__init__(kok)
        self.title("Beyanname Karşılaştırma")
        self.geometry("640x460")
        self.configure(bg="#FFFFFF")
        self.resizable(True, True)
        self.cetvel_kayitlari = cetvel_kayitlari or []

        toplam, adet = defter_toplamlari(self.cetvel_kayitlari)

        ust = ttk.LabelFrame(self, text="Defter Toplamları (kontrol cetvelinden)", padding=(10, 6))
        ust.pack(fill="x", padx=12, pady=(12, 6))
        ttk.Label(ust, text=f"191 İndirilecek KDV: {tl_format(toplam['191'])} TL "
                            f"({adet['191']} kayıt)").pack(anchor="w")
        ttk.Label(ust, text=f"391 Hesaplanan KDV: {tl_format(toplam['391'])} TL "
                            f"({adet['391']} kayıt)").pack(anchor="w")

        giris = ttk.LabelFrame(self, text="Beyanname Değerleri (boş bırakılabilir)", padding=(10, 8))
        giris.pack(fill="x", padx=12, pady=6)
        ttk.Label(giris, text="İndirilecek KDV (₺):").grid(row=0, column=0, sticky="w")
        self.indirilecek_giris = ttk.Entry(giris, width=18)
        self.indirilecek_giris.grid(row=0, column=1, padx=(4, 18))
        ttk.Label(giris, text="Hesaplanan KDV (₺):").grid(row=0, column=2, sticky="w")
        self.hesaplanan_giris = ttk.Entry(giris, width=18)
        self.hesaplanan_giris.grid(row=0, column=3, padx=4)
        ttk.Button(giris, text="Karşılaştır", command=self._karsilastir).grid(
            row=1, column=0, columnspan=4, pady=(8, 0))

        self.sonuc_metni = tk.Text(self, height=10, state="disabled", wrap="word",
                                   bg="#F7F9FC", relief="flat",
                                   font=("Consolas", 10), padx=10, pady=8)
        kaydirma = ttk.Scrollbar(self, orient="vertical", command=self.sonuc_metni.yview)
        self.sonuc_metni.configure(yscrollcommand=kaydirma.set)
        self.sonuc_metni.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=(6, 12))
        kaydirma.pack(side="right", fill="y", pady=(6, 12))

    def _deger_oku(self, entry):
        metin = (entry.get() or "").strip().replace(".", "").replace(",", ".")
        if not metin:
            return None
        try:
            return Decimal(metin)
        except InvalidOperation:
            raise ValueError(f"Geçersiz sayı: {entry.get()}")

    def _karsilastir(self):
        try:
            indirilecek = self._deger_oku(self.indirilecek_giris)
            hesaplanan = self._deger_oku(self.hesaplanan_giris)
        except ValueError as hata:
            from tkinter import messagebox
            messagebox.showwarning("Uyarı", str(hata), parent=self)
            return

        sonuc = beyanname_karsilastir(self.cetvel_kayitlari, indirilecek, hesaplanan)
        self.sonuc_metni.configure(state="normal")
        self.sonuc_metni.delete("1.0", "end")
        if not sonuc:
            self.sonuc_metni.insert("end",
                                    "Cetvel kayıtlarında 191/391 hesap satırı bulunamadı.\n"
                                    "Önce kontrol çalıştırıp cetvelleri okutun.")
        else:
            self.sonuc_metni.insert("end", f"{'Konu':<24}{'Beyanname':>16}{'Defter':>16}"
                                           f"{'Fark':>14}  Sonuç\n")
            self.sonuc_metni.insert("end", "-" * 82 + "\n")
            for s in sonuc:
                isaret = "✓ Uyumlu" if s["uyumlu"] else "✗ FARK VAR"
                self.sonuc_metni.insert("end",
                                        f"{s['konu']:<24}{tl_format(s['beyanname']):>16}"
                                        f"{tl_format(s['defter']):>16}{tl_format(s['fark']):>14}"
                                        f"  {isaret}\n")
            if all(s["uyumlu"] for s in sonuc):
                self.sonuc_metni.insert("end", "\nTüm değerler uyumlu.\n")
            else:
                self.sonuc_metni.insert("end",
                                        "\nUyumsuzluk var: beyanname değerlerini veya defter "
                                        "kayıtlarını gözden geçirin.\n")
        self.sonuc_metni.configure(state="disabled")
