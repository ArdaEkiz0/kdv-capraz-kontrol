"""Parse edilen verileri kullanıcıya göster, düzeltme şansı ver."""
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List, Callable


class AyiklamaOnizleme(tk.Toplevel):
    """Fatura/cetvel okuma sonrası önizleme ve onay."""

    def __init__(self, parent, baslik: str, kayitlar: List[Dict], onay_callback: Callable):
        super().__init__(parent)
        self.kayitlar = kayitlar
        self.onay_callback = onay_callback
        self.title(f"Önizleme - {baslik}")
        self.geometry("900x500")
        self.transient(parent)
        self.grab_set()
        self._arayuz_kur(baslik)

    def _arayuz_kur(self, baslik: str):
        ana = ttk.Frame(self, padding=10)
        ana.pack(fill="both", expand=True)

        ust = ttk.Frame(ana)
        ust.pack(fill="x")
        ttk.Label(
            ust,
            text=f"📋 {baslik} - Toplam {len(self.kayitlar)} kayıt okundu",
            font=("Segoe UI", 11, "bold"),
        ).pack(side="left")

        sorunlu = sum(
            1 for k in self.kayitlar
            if not k.get("belge_no") or (not k.get("vkn") and "vkn" in k)
        )
        if sorunlu:
            ttk.Label(
                ust,
                text=f"⚠️ {sorunlu} kayıtta eksik bilgi var",
                foreground="#B00000",
            ).pack(side="right")

        cols = ("belge_no", "tarih", "vkn", "unvan", "matrah", "kdv")
        tree_frame = ttk.Frame(ana)
        tree_frame.pack(fill="both", expand=True, pady=(8, 0))

        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=15)
        basliklar = {
            "belge_no": ("Belge No", 130),
            "tarih": ("Tarih", 90),
            "vkn": ("VKN", 110),
            "unvan": ("Ünvan", 200),
            "matrah": ("Matrah", 90),
            "kdv": ("KDV", 90),
        }
        for c in cols:
            tree.heading(c, text=basliklar[c][0])
            tree.column(c, width=basliklar[c][1], anchor="w" if c == "unvan" else "center")

        for k in self.kayitlar:
            sorun = (not k.get("belge_no")) or (not k.get("vkn") and "vkn" in k)
            tag = "sorunlu" if sorun else ""
            tree.insert("", "end", tags=(tag,), values=(
                k.get("belge_no") or "❗",
                k.get("tarih") or "",
                k.get("vkn") or (k.get("satici_vkn") or " "),
                k.get("unvan") or k.get("satici_unvan") or "",
                f"{k.get('matrah'):,.2f}" if k.get("matrah") is not None else "",
                f"{k.get('kdv'):,.2f}" if k.get("kdv") is not None else "",
            ))
        tree.tag_configure("sorunlu", background="#FFE4B5")

        sy = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sy.set)
        tree.pack(side="left", fill="both", expand=True)
        sy.pack(side="right", fill="y")

        btn = ttk.Frame(ana)
        btn.pack(fill="x", pady=(8, 0))
        ttk.Button(btn, text="✅ Onayla ve Devam Et", command=self._onayla).pack(side="right", padx=4)
        ttk.Button(btn, text="❌ İptal", command=self.destroy).pack(side="right")

    def _onayla(self):
        self.onay_callback(self.kayitlar)
        self.destroy()
