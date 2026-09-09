"""Toast bildirim sistemi."""
import tkinter as tk


def toast_goster(kok_pencere, mesaj, tip="info", sure=3000):
    """Toast bildirim gösterir."""
    renk_map = {
        "info": ("#3b82f6", "#ffffff"),
        "basari": ("#10b981", "#ffffff"),
        "uyari": ("#f59e0b", "#1e293b"),
        "hata": ("#ef4444", "#ffffff"),
    }
    arka, yazi = renk_map.get(tip, renk_map["info"])

    emoji_map = {"info": "i", "basari": "+", "uyari": "!", "hata": "x"}
    emoji = emoji_map.get(tip, "i")

    toast = tk.Toplevel(kok_pencere)
    toast.overrideredirect(True)
    toast.attributes("-topmost", True)

    try:
        ekran_w = kok_pencere.winfo_screenwidth()
        ekran_h = kok_pencere.winfo_screenheight()
        genislik = min(400, max(250, len(mesaj) * 8 + 60))
        x = ekran_w - genislik - 20
        y = ekran_h - 120
        toast.geometry(f"{genislik}x45+{x}+{y}")
    except Exception:
        toast.geometry("350x45+100+100")

    cerceve = tk.Frame(toast, bg=arka, padx=12, pady=6)
    cerceve.pack(fill="both", expand=True)

    tk.Label(cerceve, text=f"[{emoji}] {mesaj}", bg=arka, fg=yazi,
             font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x")

    def kapat():
        try:
            toast.destroy()
        except Exception:
            pass

    kok_pencere.after(sure, kapat)
