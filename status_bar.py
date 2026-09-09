"""Durum cubugu — alt kisimda sistem durumu gostergesi."""
import tkinter as tk
from datetime import datetime


class DurumCubugu:
    """Pencerenin alt kisminda durum cubugu olusturur."""

    def __init__(self, kok_pencere):
        self.kok = kok_pencere
        self.ARKA = "#1e293b"
        self.YAZI = "#94a3b8"
        self.YAZI_2 = "#64748b"
        self.YESIL = "#10b981"
        self.KIRMIZI = "#ef4444"

        self.cerceve = tk.Frame(kok_pencere, bg=self.ARKA, padx=10, pady=4)
        self.cerceve.pack(fill="x", side="bottom")

        self.sol = tk.Frame(self.cerceve, bg=self.ARKA)
        self.sol.pack(side="left", fill="x", expand=True)

        self.db_label = tk.Label(self.sol, text="DB: --", bg=self.ARKA,
                                  fg=self.YAZI, font=("Segoe UI", 9))
        self.db_label.pack(side="left", padx=(0, 15))

        self.dosya_label = tk.Label(self.sol, text="Dosya: 0", bg=self.ARKA,
                                     fg=self.YAZI, font=("Segoe UI", 9))
        self.dosya_label.pack(side="left", padx=(0, 15))

        self.cetvel_label = tk.Label(self.sol, text="Cetvel: 0", bg=self.ARKA,
                                      fg=self.YAZI, font=("Segoe UI", 9))
        self.cetvel_label.pack(side="left", padx=(0, 15))

        self.sag = tk.Frame(self.cerceve, bg=self.ARKA)
        self.sag.pack(side="right")

        self.islem_label = tk.Label(self.sag, text="", bg=self.ARKA,
                                     fg=self.YAZI, font=("Segoe UI", 9))
        self.islem_label.pack(side="right", padx=(0, 15))

        self.zaman_label = tk.Label(self.sag, text="", bg=self.ARKA,
                                     fg=self.YAZI_2, font=("Segoe UI", 9))
        self.zaman_label.pack(side="right")

    def guncelle(self, dosya=None, cetvel=None, db_durum=None, son_islem=None):
        if dosya is not None:
            self.dosya_label.configure(text=f"Dosya: {dosya}")
        if cetvel is not None:
            self.cetvel_label.configure(text=f"Cetvel: {cetvel}")
        if db_durum is not None:
            if db_durum:
                self.db_label.configure(text="DB: Bagli", fg=self.YESIL)
            else:
                self.db_label.configure(text="DB: Bagli degil", fg=self.KIRMIZI)
        if son_islem is not None:
            self.islem_label.configure(text=son_islem)
            self.zaman_label.configure(text=datetime.now().strftime("%H:%M:%S"))

    def tema_guncelle(self, tema):
        """Tema degisince renkleri gunceller."""
        self.ARKA = tema.get("durum_cubuk", "#1e293b")
        self.YAZI = tema.get("metin_ikincil", "#94a3b8")
        self.cerceve.configure(bg=self.ARKA)
        self.sol.configure(bg=self.ARKA)
        self.sag.configure(bg=self.ARKA)
        for lbl in [self.db_label, self.dosya_label, self.cetvel_label,
                    self.islem_label, self.zaman_label]:
            lbl.configure(bg=self.ARKA)
