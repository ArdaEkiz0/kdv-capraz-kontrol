"""Durum çubuğu — alt kısımda sistem durumu göstergesi."""
import tkinter as tk
from datetime import datetime


class DurumCubugu:
    """Pencerenin alt kısmında durum çubuğu oluşturur."""

    def __init__(self, kok_pencere):
        self.kok = kok_pencere

        self.cerceve = tk.Frame(kok_pencere, bg="#1e293b", padx=10, pady=4)
        self.cerceve.pack(fill="x", side="bottom")

        # Sol taraf
        self.sol = tk.Frame(self.cerceve, bg="#1e293b")
        self.sol.pack(side="left", fill="x", expand=True)

        self.db_label = tk.Label(self.sol, text="DB: --", bg="#1e293b",
                                  fg="#94a3b8", font=("Segoe UI", 9))
        self.db_label.pack(side="left", padx=(0, 15))

        self.dosya_label = tk.Label(self.sol, text="Dosya: 0", bg="#1e293b",
                                     fg="#94a3b8", font=("Segoe UI", 9))
        self.dosya_label.pack(side="left", padx=(0, 15))

        self.cetvel_label = tk.Label(self.sol, text="Cetvel: 0", bg="#1e293b",
                                      fg="#94a3b8", font=("Segoe UI", 9))
        self.cetvel_label.pack(side="left", padx=(0, 15))

        # Sağ taraf
        self.sag = tk.Frame(self.cerceve, bg="#1e293b")
        self.sag.pack(side="right")

        self.zaman_label = tk.Label(self.sag, text="", bg="#1e293b",
                                     fg="#64748b", font=("Segoe UI", 9))
        self.zaman_label.pack(side="right")

        self.islem_label = tk.Label(self.sag, text="", bg="#1e293b",
                                     fg="#94a3b8", font=("Segoe UI", 9))
        self.islem_label.pack(side="right", padx=(0, 15))

    def guncelle(self, dosya=None, cetvel=None, db_durum=None, son_islem=None):
        if dosya is not None:
            self.dosya_label.configure(text=f"Dosya: {dosya}")
        if cetvel is not None:
            self.cetvel_label.configure(text=f"Cetvel: {cetvel}")
        if db_durum is not None:
            if db_durum:
                self.db_label.configure(text="DB: Bagli", fg="#10b981")
            else:
                self.db_label.configure(text="DB: Bagli degil", fg="#ef4444")
        if son_islem is not None:
            self.islem_label.configure(text=son_islem)
            self.zaman_label.configure(text=datetime.now().strftime("%H:%M:%S"))

    def mesaj(self, metin, renk="#94a3b8"):
        self.islem_label.configure(text=metin, fg=renk)
        self.zaman_label.configure(text=datetime.now().strftime("%H:%M:%S"))
