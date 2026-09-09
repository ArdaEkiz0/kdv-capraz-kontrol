"""Toast bildirim sistemi — kısa süreli bildirimler.

Pencerenin sağ alt köşesinde kayan bildirim gösterir.

Kullanım:
    from toast import toast_goster
    toast_goster("Kaydedildi!", tip="basari")
"""


def toast_goster(kok_pencere, mesaj, tip="info", sure=3000):
    """Toast bildirim gösterir.

    Args:
        kok_pencere: Ana pencere (tk.Tk veya tk.Toplevel)
        mesaj: Gösterilecek mesaj
        tip: "info", "basari", "uyari", "hata"
        sure: Milisaniye cinsinden süre (varsayılan: 3000)
    """
    import tkinter as tk

    # Renkler
    renk_map = {
        "info": ("#3b82f6", "#ffffff"),
        "basari": ("#10b981", "#ffffff"),
        "uyari": ("#f59e0b", "#1e293b"),
        "hata": ("#ef4444", "#ffffff"),
    }
    arka, yazi = renk_map.get(tip, renk_map["info"])

    # Emoji
    emoji_map = {
        "info": "ℹ️",
        "basari": "✅",
        "uyari": "⚠️",
        "hata": "❌",
    }
    emoji = emoji_map.get(tip, "ℹ️")

    # Toast penceresi
    toast = tk.Toplevel(kok_pencere)
    toast.overrideredirect(True)
    toast.attributes("-topmost", True)

    # Pencere konumu (sağ alt)
    try:
        ekran_w = kok_pencere.winfo_screenwidth()
        ekran_h = kok_pencere.winfo_screenheight()
        genislik = max(300, len(mesaj) * 8 + 80)
        yukseklik = 50
        x = ekran_w - genislik - 20
        y = ekran_h - yukseklik - 80
        toast.geometry(f"{genislik}x{yukseklik}+{x}+{y}")
    except Exception:
        toast.geometry("400x50+100+100")

    # Arka plan
    cerceve = tk.Frame(toast, bg=arka, padx=12, pady=8)
    cerceve.pack(fill="both", expand=True)

    # Metin
    tk.Label(cerceve, text=f"{emoji} {mesaj}", bg=arka, fg=yazi,
             font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x")

    # Animasyonlu kapanma
    def kapat():
        try:
            toast.attributes("-alpha", 0.95)
            kok_pencere.after(50, lambda: toast.attributes("-alpha", 0.85))
            kok_pencere.after(100, lambda: toast.attributes("-alpha", 0.7))
            kok_pencere.after(150, lambda: toast.attributes("-alpha", 0.5))
            kok_pencere.after(200, lambda: toast.destroy())
        except Exception:
            try:
                toast.destroy()
            except Exception:
                pass

    kok_pencere.after(sure, kapat)
