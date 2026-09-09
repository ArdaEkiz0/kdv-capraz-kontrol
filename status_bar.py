"""Durum çubuğu — alt kısımda sistem durumu göstergesi.

Dosya sayısı, DB durumu, son işlem zamanını gösterir.

Kullanım:
    from status_bar import DurumCubugu
    dc = DurumCubugu(ana_pencere)
    dc.guncelle(dosya=5, db=True, son_islem="Kontrol tamamlandı")
"""
import tkinter as tk
from datetime import datetime


class DurumCubugu:
    """Pencerenin alt kısmında durum çubuğu oluşturur."""

    def __init__(self, kok_pencere, side="bottom"):
        self.kok = kok_pencere
        self._aktif = True

        self.cerceve = tk.Frame(kok_pencere, bg="#1e293b", padx=10, pady=3)
        self.cerceve.pack(fill="x", side=side, before=self._log_kutusunu_bul(kok_pencere))

        # Sol taraf: durum göstergeleri
        self.sol = tk.Frame(self.cerceve, bg="#1e293b")
        self.sol.pack(side="left", fill="x", expand=True)

        # DB durumu
        self.db_label = tk.Label(self.sol, text="🗄️ DB: --", bg="#1e293b",
                                  fg="#94a3b8", font=("Segoe UI", 9))
        self.db_label.pack(side="left", padx=(0, 15))

        # Dosya sayısı
        self.dosya_label = tk.Label(self.sol, text="📁 Dosya: 0", bg="#1e293b",
                                     fg="#94a3b8", font=("Segoe UI", 9))
        self.dosya_label.pack(side="left", padx=(0, 15))

        # Cetvel sayısı
        self.cetvel_label = tk.Label(self.sol, text="📋 Cetvel: 0", bg="#1e293b",
                                      fg="#94a3b8", font=("Segoe UI", 9))
        self.cetvel_label.pack(side="left", padx=(0, 15))

        # Sağ taraf: son işlem zamanı
        self.sag = tk.Frame(self.cerceve, bg="#1e293b")
        self.sag.pack(side="right")

        self.zaman_label = tk.Label(self.sag, text="", bg="#1e293b",
                                     fg="#64748b", font=("Segoe UI", 9))
        self.zaman_label.pack(side="right")

        self.islem_label = tk.Label(self.sag, text="", bg="#1e293b",
                                     fg="#94a3b8", font=("Segoe UI", 9))
        self.islem_label.pack(side="right", padx=(0, 15))

    def _log_kutusunu_bul(self, parent):
        """Log kutusunu bul (durum çubuğundan önce yerleşmesi için)."""
        try:
            for child in parent.winfo_children():
                if isinstance(child, tk.Frame):
                    for alt in child.winfo_children():
                        if isinstance(alt, tk.Frame):
                            for daha_alt in alt.winfo_children():
                                if isinstance(daha_alt, tk.Text):
                                    return child
        except Exception:
            pass
        return None

    def guncelle(self, dosya=None, cetvel=None, db_durum=None, son_islem=None):
        """Durum çubuğunu günceller.

        Args:
            dosya: Fatura dosya sayısı
            cetvel: Cetvel dosya sayısı
            db_durum: True/False (DB bağlı mı)
            son_islem: Son yapılan işlem açıklaması
        """
        if dosya is not None:
            self.dosya_label.configure(text=f"📁 Dosya: {dosya}")
        if cetvel is not None:
            self.cetvel_label.configure(text=f"📋 Cetvel: {cetvel}")
        if db_durum is not None:
            if db_durum:
                self.db_label.configure(text="🗄️ DB: Bağlı", fg="#10b981")
            else:
                self.db_label.configure(text="🗄️ DB: Bağlı değil", fg="#ef4444")
        if son_islem is not None:
            self.islem_label.configure(text=son_islem)
            self.zaman_label.configure(
                text=f"🕐 {datetime.now().strftime('%H:%M:%S')}")

    def mesaj(self, metin, renk="#94a3b8"):
        """Durum çubuğunda mesaj gösterir."""
        self.islem_label.configure(text=metin, fg=renk)
        self.zaman_label.configure(text=f"🕐 {datetime.now().strftime('%H:%M:%S')}")

    def temizle(self):
        """Durum çubuğunu temizler."""
        self.dosya_label.configure(text="📁 Dosya: 0")
        self.cetvel_label.configure(text="📋 Cetvel: 0")
        self.islem_label.configure(text="")
        self.zaman_label.configure(text="")
