"""Bir sonuç satırına çift tıklandığında: ilgili faturanın tüm detayları."""
import os
import threading
import tkinter as tk
from tkinter import ttk
from typing import Dict

from utils import tl_format


class FaturaDetayPencere(tk.Toplevel):
    """Bir sonuç satırının detaylı görüntüsü + PDF önizleme."""

    def __init__(self, parent, fatura: Dict, sonuc: Dict):
        super().__init__(parent)
        self.fatura = fatura
        self.sonuc = sonuc
        self.title(f"Fatura Detayı - {sonuc.get('belge_no') or '-'}")
        self.geometry("1020x600")
        self.minsize(860, 520)
        self.transient(parent)
        self._gorsel = None
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

        govde = ttk.Frame(ana)
        govde.pack(fill="both", expand=True)

        # ---- Sol: metin detayları ----
        sol = ttk.Frame(govde)
        sol.pack(side="left", fill="both", expand=True, padx=(0, 10))

        bilgi = ttk.LabelFrame(sol, text="📋 Temel Bilgiler", padding=8)
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
            detay_frame = ttk.LabelFrame(sol, text="📊 Oran Bazlı KDV Detayı", padding=8)
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
            not_frame = ttk.LabelFrame(sol, text="⚠️ Notlar", padding=8)
            not_frame.pack(fill="x", pady=(0, 8))
            for n in notlar:
                ttk.Label(not_frame, text="• " + n, foreground="#B00000").pack(anchor="w")

        detay_metin = self.sonuc.get("detay") or ""
        if detay_metin:
            eslesme_frame = ttk.LabelFrame(sol, text="🔍 Eşleşme Detayı", padding=8)
            eslesme_frame.pack(fill="x")
            ttk.Label(eslesme_frame, text=detay_metin, wraplength=480).pack(anchor="w")

        # ---- Sağ: PDF önizleme ----
        onizleme = ttk.LabelFrame(govde, text="🖼 Fatura Görseli (sayfa 1)", padding=6)
        onizleme.pack(side="left", fill="both", expand=False)
        onizleme.configure(width=430)
        onizleme.pack_propagate(False)

        self._onizleme_etiket = tk.Label(onizleme, bg="#f1f5f9",
                                         text="Yükleniyor...", fg="#64748b",
                                         font=("Segoe UI", 9))
        self._onizleme_etiket.pack(fill="both", expand=True)

        kaynak = str(f.get("dosya") or "")
        if kaynak.lower().endswith(".pdf") and os.path.exists(kaynak):
            self._yuklenen = None
            self._yukleme_hata = None
            threading.Thread(target=self._onizleme_yukle, args=(kaynak,), daemon=True).start()
            self._onizleme_yokle()
        else:
            sebep = "Excel/XML kaynağı — görsel yok" if not kaynak.lower().endswith(".pdf") \
                else "PDF dosyası bulunamadı"
            self._onizleme_etiket.configure(text=f"Önizleme yok\n({sebep})")

        alt = ttk.Frame(ana)
        alt.pack(fill="x", pady=(8, 0))
        ttk.Button(alt, text="📂 Dosyayı Aç",
                   command=lambda: self._dosya_ac(kaynak)).pack(side="left")
        ttk.Button(alt, text="Kapat", command=self.destroy).pack(side="right")

    def _onizleme_yokle(self):
        """Ana thread'de çalışan yoklama döngüsü (işçi thread'i bekler)."""
        if not self.winfo_exists():
            return
        if self._yuklenen is not None:
            self._onizleme_uygula(self._yuklenen)
            return
        if self._yukleme_hata is not None:
            self._onizleme_etiket.configure(text=f"Önizleme yüklenemedi\n({self._yukleme_hata})")
            return
        self.after(120, self._onizleme_yokle)

    def _onizleme_yukle(self, pdf_yolu):
        """İşçi thread: yalnızca hesaplar, hiçbir Tk çağrısı yapmaz."""
        try:
            from ocr import sayfa_gorsel
            gorsel = sayfa_gorsel(pdf_yolu, 0)
            if gorsel is None:
                raise ValueError("görsel üretilemedi")
            genislik, yukseklik = gorsel.size
            olcek = min(400.0 / max(genislik, 1), 540.0 / max(yukseklik, 1), 1.0)
            if olcek < 1.0:
                gorsel = gorsel.resize((int(genislik * olcek), int(yukseklik * olcek)))
            self._yuklenen = gorsel
        except Exception as hata:
            self._yukleme_hata = str(hata) or hata.__class__.__name__

    def _onizleme_uygula(self, gorsel):
        try:
            from PIL import ImageTk
            foto = ImageTk.PhotoImage(gorsel)
            self._gorsel = foto
            self._onizleme_etiket.configure(image=foto, text="")
        except Exception as hata:
            self._onizleme_etiket.configure(text=f"Önizleme yüklenemedi\n({hata})")

    def _dosya_ac(self, yol):
        if yol and os.path.exists(yol):
            try:
                os.startfile(yol)
            except OSError:
                pass

    def _panoya_kopyala(self, metin, buton=None):
        self.clipboard_clear()
        self.clipboard_append(metin)
        if buton is not None:
            eski_metin = buton.cget("text")
            buton.configure(text="✓ Kopyalandı")
            self.after(1500, lambda: buton.configure(text=eski_metin))
