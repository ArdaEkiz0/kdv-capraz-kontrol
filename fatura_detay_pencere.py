"""Bir sonuç satırına çift tıklandığında: ilgili faturanın tüm detayları."""
import tkinter as tk
from tkinter import ttk
from typing import Dict

from utils import tl_format


class FaturaDetayPencere(tk.Toplevel):
    """Bir sonuç satırının detaylı görüntüsü."""

    def __init__(self, parent, fatura: Dict, sonuc: Dict):
        super().__init__(parent)
        self.fatura = fatura
        self.sonuc = sonuc
        self.title(f"Fatura Detayı - {sonuc.get('belge_no') or '-'}")
        self.geometry("600x500")
        self.transient(parent)
        self._arayuz_kur()

    def _arayuz_kur(self):
        ana = ttk.Frame(self, padding=12)
        ana.pack(fill="both", expand=True)

        baslik_satir = ttk.Frame(ana)
        baslik_satir.pack(fill="x", pady=(0, 8))
        belge_no = str(self.sonuc.get("belge_no") or self.fatura.get("belge_no") or "")
        baslik = ttk.Label(
            baslik_satir,
            text=f"📄 {belge_no or 'Belge Yok'}",
            font=("Segoe UI", 14, "bold"),
            foreground="#4472C4",
        )
        baslik.pack(side="left")
        if belge_no:
            kopyala_buton = ttk.Button(
                baslik_satir, text="📋 Numarayı Kopyala",
                command=lambda: self._panoya_kopyala(belge_no, kopyala_buton))
            kopyala_buton.pack(side="left", padx=(12, 0))
            baslik.configure(cursor="hand2")
            baslik.bind("<Button-1>", lambda e: self._panoya_kopyala(belge_no, kopyala_buton))

        bilgi = ttk.LabelFrame(ana, text="📋 Temel Bilgiler", padding=8)
        bilgi.pack(fill="x", pady=(0, 8))

        f = self.fatura
        sektor = f.get("sektor") or ""
        if sektor:
            sektor_etiket = {"TELECOM": "📡 Telekom", "ELEKTRIK": "⚡ Elektrik"}.get(sektor, sektor)
        else:
            sektor_etiket = ""
        satirlar = [
            ("Belge No", f.get("belge_no") or "-"),
            ("Tarih", f.get("tarih") or "-"),
            ("Tip", f.get("tip") or "-"),
            ("Sektör", sektor_etiket or "-"),
            ("Satıcı VKN", f.get("satici_vkn") or "-"),
            ("Satıcı Ünvan", f.get("satici_unvan") or "-"),
            ("Alıcı VKN", f.get("alici_vkn") or "-"),
            ("KDV Oranları", ", ".join(f"%{o}" for o in f.get("oranlar") or []) or "-"),
            ("Matrah", tl_format(f.get("matrah")) + " TL"),
            ("KDV (tüm vergi)", tl_format(f.get("kdv")) + " TL"),
        ]
        kdv_ayrik = f.get("kdv_ayrik")
        if kdv_ayrik is not None:
            satirlar.append(("KDV (saf 0015)", tl_format(kdv_ayrik) + " TL"))
            satirlar.append(("Diğer vergiler", tl_format(f.get("diger_vergi_toplam")) + " TL"))
        satirlar.append(("Toplam", tl_format(f.get("toplam")) + " TL"))
        satirlar.append(("Eşleşme Durumu", self.sonuc.get("durum") or "-"))
        for i, (etiket, deger) in enumerate(satirlar):
            ttk.Label(bilgi, text=etiket + ":", font=("Segoe UI", 9, "bold")).grid(
                row=i, column=0, sticky="w", pady=2, padx=(0, 8)
            )
            ttk.Label(bilgi, text=str(deger)).grid(row=i, column=1, sticky="w", pady=2)

        bilgi.columnconfigure(1, weight=1)

        detay = f.get("vergi_detay") or []
        if detay:
            detay_frame = ttk.LabelFrame(ana, text="📊 Oran Bazlı KDV Detayı", padding=8)
            detay_frame.pack(fill="both", expand=True, pady=(0, 8))

            cols = ("ad", "oran", "matrah", "kdv", "muafiyet")
            tree = ttk.Treeview(detay_frame, columns=cols, show="headings", height=4)
            tree.heading("ad", text="Vergi")
            tree.heading("oran", text="Oran")
            tree.heading("matrah", text="Matrah")
            tree.heading("kdv", text="KDV")
            tree.heading("muafiyet", text="Muafiyet")
            tree.column("ad", width=200, anchor="w")
            tree.column("oran", width=70, anchor="center")
            tree.column("matrah", width=110, anchor="e")
            tree.column("kdv", width=110, anchor="e")
            tree.column("muafiyet", width=130, anchor="w")

            for st in detay:
                tree.insert("", "end", values=(
                    st.get("ad") or (f"KDV" if st.get('kod') == '0015' else "-"),
                    f"%{st.get('oran')}" if st.get('oran') else "-",
                    tl_format(st.get("matrah")),
                    tl_format(st.get("kdv")),
                    st.get("muafiyet") or "",
                ))
            tree.pack(fill="both", expand=True)

        notlar = f.get("notlar") or []
        if notlar:
            not_frame = ttk.LabelFrame(ana, text="⚠️ Notlar", padding=8)
            not_frame.pack(fill="x", pady=(0, 8))
            for n in notlar:
                ttk.Label(not_frame, text="• " + n, foreground="#B00000").pack(anchor="w")

        detay_metin = self.sonuc.get("detay") or ""
        if detay_metin:
            detay_frame = ttk.LabelFrame(ana, text="🔍 Eşleşme Detayı", padding=8)
            detay_frame.pack(fill="x")
            ttk.Label(detay_frame, text=detay_metin, wraplength=550).pack(anchor="w")

        ttk.Button(ana, text="Kapat", command=self.destroy).pack(pady=(8, 0))

    def _panoya_kopyala(self, metin, buton=None):
        self.clipboard_clear()
        self.clipboard_append(metin)
        if buton is not None:
            eski_metin = buton.cget("text")
            buton.configure(text="✓ Kopyalandı")
            self.after(1500, lambda: buton.configure(text=eski_metin))
