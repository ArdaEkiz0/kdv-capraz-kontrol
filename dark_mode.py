"""Karanlık/Aydınlık mod tema desteği."""


ACIK_TEMA = {
    "ad": "Acik",
    "bg": "#f5f7fb",
    "kart": "#ffffff",
    "border": "#dbe2ef",
    "metin": "#1e293b",
    "metin_ikincil": "#64748b",
    "baslik_alani": "#eef2ff",
    "primer": "#2563eb",
    "primer_koyu": "#1d4ed8",
    "primer_acik": "#dbeafe",
    "mor": "#7c3aed",
    "basarili": "#10b981",
    "uyari": "#f59e0b",
    "hata": "#ef4444",
    "buton_metin": "#ffffff",
    "secili": "#dbeafe",
    "satir_bg": "#ffffff",
    "satir_alt": "#f8fafc",
    "log_bg": "#ffffff",
    "durum_cubuk": "#1e293b",
}

KARANLIK_TEMA = {
    "ad": "Karanlik",
    "bg": "#0f172a",
    "kart": "#1e293b",
    "border": "#334155",
    "metin": "#e2e8f0",
    "metin_ikincil": "#94a3b8",
    "baslik_alani": "#1e3a5f",
    "primer": "#3b82f6",
    "primer_koyu": "#2563eb",
    "primer_acik": "#1e3a5f",
    "mor": "#8b5cf6",
    "basarili": "#10b981",
    "uyari": "#f59e0b",
    "hata": "#ef4444",
    "buton_metin": "#ffffff",
    "secili": "#1e3a5f",
    "satir_bg": "#1e293b",
    "satir_alt": "#0f172a",
    "log_bg": "#0f172a",
    "durum_cubuk": "#0f172a",
}


class TemaYoneticisi:
    def __init__(self):
        self.aktif_tema = "acik"
        self.tema_verileri = {"acik": ACIK_TEMA, "karanlik": KARANLIK_TEMA}

    def al(self, anahtar):
        return self.tema_verileri[self.aktif_tema].get(anahtar)

    def uygula(self, tema_adi="acik"):
        if tema_adi in self.tema_verileri:
            self.aktif_tema = tema_adi

    def toggle(self):
        if self.aktif_tema == "acik":
            self.aktif_tema = "karanlik"
        else:
            self.aktif_tema = "acik"
        return self.aktif_tema

    def renk_paleti(self):
        return self.tema_verileri[self.aktif_tema]

    def tk_renkleri_uygula(self, kok_pencere):
        """Tüm tk widget'larının renklerini günceller."""
        t = self.tema_verileri[self.aktif_tema]

        def gez(widget):
            try:
                bg = str(widget.cget("background") or "")
                fg = str(widget.cget("foreground") or "")

                # Frame'leri güncelle
                if isinstance(widget, tk.Frame):
                    if bg not in ("#ffffff", "#f5f7fb", "#0f172a", "#1e293b", "#1e3a5f"):
                        pass
                    else:
                        widget.configure(bg=t["bg"])

                # Label'ları güncelle
                elif isinstance(widget, tk.Label):
                    if bg in ("#ffffff", "#f5f7fb", "#0f172a", "#eef2ff", "#1e3a5f"):
                        widget.configure(bg=t["bg"])
                    if fg in ("#1e293b", "#e2e8f0", "#64748b", "#94a3b8"):
                        widget.configure(fg=t["metin"])

                # Text widget'larını güncelle
                elif isinstance(widget, tk.Text):
                    if bg in ("#ffffff", "#f5f7fb", "#0f172a"):
                        widget.configure(bg=t["kart"], fg=t["metin"])

                # Button'ları güncelle
                elif isinstance(widget, tk.Button):
                    if bg in ("#ffffff", "#f5f7fb", "#0f172a"):
                        widget.configure(bg=t["kart"], fg=t["metin"])

            except Exception:
                pass

            for cocuk in widget.winfo_children():
                gez(cocuk)

        try:
            gez(kok_pencere)
        except Exception:
            pass

    def tk_stil_uygula(self, stil):
        """ttk.Style'a tema uygular."""
        t = self.tema_verileri[self.aktif_tema]

        stil.configure("TFrame", background=t["bg"])
        stil.configure("Kart.TFrame", background=t["kart"], relief="flat")

        stil.configure("TLabel", background=t["bg"], foreground=t["metin"],
                       font=("Segoe UI", 10))
        stil.configure("Kart.TLabel", background=t["kart"], foreground=t["metin"],
                       font=("Segoe UI", 10))
        stil.configure("Ikincil.TLabel", background=t["bg"],
                       foreground=t["metin_ikincil"], font=("Segoe UI", 9))

        stil.configure("TButton", background=t["primer"], foreground=t["buton_metin"],
                       font=("Segoe UI", 10), padding=(10, 6), borderwidth=0,
                       focuscolor="none")
        stil.map("TButton",
                 background=[("active", t["primer_koyu"]),
                             ("pressed", t["primer_koyu"])],
                 relief=[("pressed", "sunken")])

        stil.configure("Baslik.TLabel", background=t["baslik_alani"],
                       foreground=t["primer"], font=("Segoe UI", 16, "bold"),
                       padding=10)

        stil.configure("TRadiobutton", background=t["bg"], foreground=t["metin"],
                       font=("Segoe UI", 10))
        stil.configure("TCombobox", fieldbackground=t["kart"], background=t["kart"],
                       foreground=t["metin"], arrowcolor=t["primer"])

        stil.configure("Treeview", background=t["satir_bg"],
                       fieldbackground=t["satir_bg"], foreground=t["metin"],
                       rowheight=28, font=("Segoe UI", 10), borderwidth=0)
        stil.configure("Treeview.Heading", background=t["baslik_alani"],
                       foreground=t["metin"], font=("Segoe UI", 10, "bold"),
                       padding=(8, 7), relief="flat")
        stil.map("Treeview",
                 background=[("selected", t["secili"])],
                 foreground=[("selected", t["primer_koyu"])])

        stil.configure("Primary.TButton", background=t["primer"],
                       foreground=t["buton_metin"], font=("Segoe UI", 11, "bold"),
                       padding=(22, 10), borderwidth=0, focuscolor="none")
        stil.map("Primary.TButton",
                 background=[("active", t["primer_koyu"]),
                             ("pressed", t["primer_koyu"])],
                 relief=[("pressed", "sunken")])

        stil.configure("Arac.TButton", background=t["kart"], foreground=t["metin"],
                       font=("Segoe UI", 9), padding=(7, 4), borderwidth=1,
                       bordercolor=t["border"], focuscolor="none")
        stil.map("Arac.TButton",
                 background=[("active", t["primer_acik"]),
                             ("pressed", t["primer_acik"])],
                 bordercolor=[("active", t["primer"])])

        stil.configure("KartIkincil.TLabel", background=t["kart"],
                       foreground=t["metin_ikincil"], font=("Segoe UI", 9))
        stil.configure("KartBaslik.TLabel", background=t["kart"],
                       foreground=t["metin"], font=("Segoe UI", 11, "bold"))
        stil.configure("Kart.TRadiobutton", background=t["kart"],
                       foreground=t["metin"], font=("Segoe UI", 10))

        for yon in ("Vertical", "Horizontal"):
            stil.configure(f"{yon}.TScrollbar",
                          background="#334155" if self.aktif_tema == "karanlik" else "#e2e8f0",
                          troughcolor=t["bg"],
                          bordercolor=t["kart"],
                          arrowcolor=t["metin_ikincil"])
