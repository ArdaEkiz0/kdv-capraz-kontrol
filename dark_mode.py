"""Karanlık/Aydınlık mod tema desteği.

Tema değiştirme ve renk paletleri.

Kullanım:
    from dark_mode import TemaYoneticisi, ACIK_TEMA, KARANLIK_TEMA
    ty = TemaYoneticisi()
    ty.uygula("karanlik")
"""

# Açık Tema (varsayılan)
ACIK_TEMA = {
    "ad": "Açık",
    "bg": "#f5f7fb",
    "kart": "#ffffff",
    "border": "#dbe2ef",
    "metin": "#1e293b",
    "metin_ikincil": "#64748b",
    "baslik_alani": "#eef2ff",
    "priner": "#2563eb",
    "priner_koyu": "#1d4ed8",
    "priner_acik": "#dbeafe",
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

# Karanlık Tema
KARANLIK_TEMA = {
    "ad": "Karanlık",
    "bg": "#0f172a",
    "kart": "#1e293b",
    "border": "#334155",
    "metin": "#e2e8f0",
    "metin_ikincil": "#94a3b8",
    "baslik_alani": "#1e3a5f",
    "priner": "#3b82f6",
    "priner_koyu": "#2563eb",
    "priner_acik": "#1e3a5f",
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
    """Tema yönetim sınıfı."""

    def __init__(self):
        self.aktif_tema = "acik"
        self.tema_verileri = {
            "acik": ACIK_TEMA,
            "karanlik": KARANLIK_TEMA,
        }

    def al(self, anahtar):
        """Aktif temadan değer alır."""
        return self.tema_verileri[self.aktif_tema].get(anahtar)

    def uygula(self, tema_adi="acik"):
        """Tema adını ayarlar."""
        if tema_adi in self.tema_verileri:
            self.aktif_tema = tema_adi

    def toggle(self):
        """Tema arasında geçiş yapar."""
        if self.aktif_tema == "acik":
            self.aktif_tema = "karanlik"
        else:
            self.aktif_tema = "acik"
        return self.aktif_tema

    def renk_paleti(self):
        """Aktif tema için renk paletini döner."""
        return self.tema_verileri[self.aktif_tema]

    def tk_stil_uygula(self, stil):
        """Tema adını ttk.Style'a uygular."""
        t = self.tema_verileri[self.aktif_tema]

        stil.configure("TFrame", background=t["bg"])
        stil.configure("Kart.TFrame", background=t["kart"], relief="flat")

        stil.configure("TLabel", background=t["bg"], foreground=t["metin"],
                       font=("Segoe UI", 10))
        stil.configure("Kart.TLabel", background=t["kart"], foreground=t["metin"],
                       font=("Segoe UI", 10))
        stil.configure("Ikincil.TLabel", background=t["bg"],
                       foreground=t["metin_ikincil"], font=("Segoe UI", 9))

        stil.configure("TButton", background=t["priner"], foreground=t["buton_metin"],
                       font=("Segoe UI", 10), padding=(10, 6), borderwidth=0,
                       focuscolor="none")
        stil.map("TButton",
                 background=[("active", t["priner_koyu"]),
                             ("pressed", t["priner_koyu"])],
                 relief=[("pressed", "sunken")])

        stil.configure("Baslik.TLabel", background=t["baslik_alani"],
                       foreground=t["priner"], font=("Segoe UI", 16, "bold"),
                       padding=10)

        stil.configure("TRadiobutton", background=t["bg"], foreground=t["metin"],
                       font=("Segoe UI", 10))
        stil.configure("TCombobox", fieldbackground=t["kart"], background=t["kart"],
                       foreground=t["metin"], arrowcolor=t["priner"])

        stil.configure("Treeview", background=t["satir_bg"],
                       fieldbackground=t["satir_bg"], foreground=t["metin"],
                       rowheight=28, font=("Segoe UI", 10), borderwidth=0)
        stil.configure("Treeview.Heading", background=t["baslik_alani"],
                       foreground=t["metin"], font=("Segoe UI", 10, "bold"),
                       padding=(8, 7), relief="flat")
        stil.map("Treeview",
                 background=[("selected", t["secili"])],
                 foreground=[("selected", t["priner_koyu"])])
        stil.map("Treeview.Heading",
                 background=[("active", "#334155" if self.aktif_tema == "karanlik" else "#e2e8f0")])

        stil.configure("Primary.TButton", background=t["priner"],
                       foreground=t["buton_metin"], font=("Segoe UI", 11, "bold"),
                       padding=(22, 10), borderwidth=0, focuscolor="none")
        stil.map("Primary.TButton",
                 background=[("active", t["priner_koyu"]),
                             ("pressed", t["priner_koyu"])],
                 relief=[("pressed", "sunken")])

        stil.configure("Arac.TButton", background=t["kart"], foreground=t["metin"],
                       font=("Segoe UI", 9), padding=(7, 4), borderwidth=1,
                       bordercolor=t["border"], focuscolor="none")
        stil.map("Arac.TButton",
                 background=[("active", t["priner_acik"]),
                             ("pressed", t["priner_acik"])],
                 bordercolor=[("active", t["priner"])])

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
