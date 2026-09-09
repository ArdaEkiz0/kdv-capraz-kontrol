"""Tooltip widget — hover ile açıklama kutusu.

Widget'ın üzerine gelince küçük açıklama kutusu gösterir.

Kullanım:
    from tooltip import Tooltip
    Tooltip(buton, "Bu buton kaydeder")
"""


class Tooltip:
    """Widget için tooltip (açıklama kutusu) oluşturur."""

    def __init__(self, widget, metin, gecikme=500):
        """
        Args:
            widget: Tooltip eklenecek widget
            metin: Gösterilecek açıklama
            gecikme: Milisaniye cinsinden gecikme
        """
        self.widget = widget
        self.metin = metin
        self.gecikme = gecikme
        self._pencere = None
        self._zamanlayici = None

        self.widget.bind("<Enter>", self._giris, add="+")
        self.widget.bind("<Leave>", self._cikis, add="+")
        self.widget.bind("<ButtonPress>", self._cikis, add="+")

    def _giris(self, event=None):
        self._iptal()
        self._zamanlayici = self.widget.after(self.gecikme, self._goster)

    def _cikis(self, event=None):
        self._iptal()
        self._kapat()

    def _iptal(self):
        if self._zamanlayici:
            self.widget.after_cancel(self._zamanlayici)
            self._zamanlayici = None

    def _goster(self):
        if self._pencere:
            return
        try:
            import tkinter as tk

            x = self.widget.winfo_rootx() + 20
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5

            self._pencere = tk.Toplevel(self.widget)
            self._pencere.wm_overrideredirect(True)
            self._pencere.wm_attributes("-topmost", True)

            cerceve = tk.Frame(self._pencere, bg="#1e293b", padx=6, pady=4,
                               highlightbackground="#475569", highlightthickness=1)
            cerceve.pack()

            tk.Label(cerceve, text=self.metin, bg="#1e293b", fg="#e2e8f0",
                     font=("Segoe UI", 9), wraplength=300, justify="left").pack()

            self._pencere.wm_geometry(f"+{x}+{y}")
        except Exception:
            self._pencere = None

    def _kapat(self):
        if self._pencere:
            try:
                self._pencere.destroy()
            except Exception:
                pass
            self._pencere = None

    def guncelle(self, yeni_metin):
        """Tooltip metnini günceller."""
        self.metin = yeni_metin
