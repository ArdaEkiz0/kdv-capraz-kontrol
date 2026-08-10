"""Veri İncele & Düzelt penceresi: faturalar ve muavin kayıtları düzenlenebilir."""
from decimal import Decimal, InvalidOperation

import tkinter as tk
from tkinter import messagebox, ttk


def _sayiya_cevir(metin):
    metin = (metin or "").strip().replace(",", ".")
    if not metin:
        return None
    try:
        return Decimal(metin)
    except InvalidOperation:
        return None


class VeriIncelePenceresi(tk.Toplevel):
    """Faturaları ve muavin kayıtlarını inceleyip düzelten pencere."""

    def __init__(self, parent, faturalar, cetvel_kayitlari, yeniden_kontrol_callback=None, log_callback=None):
        super().__init__(parent)
        self.faturalar = faturalar
        self.cetvel_kayitlari = cetvel_kayitlari
        self.yeniden_kontrol_callback = yeniden_kontrol_callback
        self.log_callback = log_callback
        self.degisen = False
        self.title("Veriyi İncele & Düzelt")
        self.geometry("980x620")
        self.transient(parent)
        self._arayuz_kur()

    def _arayuz_kur(self):
        ana = ttk.Frame(self, padding=8)
        ana.pack(fill="both", expand=True)

        aciklama = ttk.Label(
            ana,
            text=("Satırı seçin, sağdaki alanlardan düzeltin. 'Kaydet' veya 'Satırı Sil' ile uygulayın. "
                  "Muavin sekmesinde 'Yeni Kayıt Ekle' ile eksik fatura elle eklenebilir."),
            background="#DDEBF7", padding=6, anchor="w",
        )
        aciklama.pack(fill="x", pady=(0, 6))

        notebook = ttk.Notebook(ana)
        notebook.pack(fill="both", expand=True)

        self._fatura_sekmesi(notebook)
        self._muavin_sekmesi(notebook)

        alt = ttk.Frame(ana)
        alt.pack(fill="x", pady=(6, 0))
        ttk.Button(alt, text="Kontrolü Yeniden Çalıştır", command=self._yeniden_kontrol).pack(side="left")
        ttk.Label(alt, text="Değişiklikler bellek içinde uygulanır.", foreground="#666666").pack(
            side="left", padx=10)

    def _fatura_sekmesi(self, notebook):
        sekme = ttk.Frame(notebook, padding=6)
        notebook.add(sekme, text=f"Faturalar ({len(self.faturalar)})")

        sol = ttk.Frame(sekme)
        sol.pack(side="left", fill="both", expand=True)

        kolonlar = ("belge_no", "tarih", "vkn", "unvan", "matrah", "kdv", "toplam", "tip")
        basliklar = {
            "belge_no": "Belge No", "tarih": "Tarih", "vkn": "VKN", "unvan": "Satıcı",
            "matrah": "Matrah", "kdv": "KDV", "toplam": "Toplam", "tip": "Tip",
        }
        self.fatura_tree = ttk.Treeview(sol, columns=kolonlar, show="headings", height=16)
        for kolon in kolonlar:
            self.fatura_tree.heading(kolon, text=basliklar[kolon])
            self.fatura_tree.column(kolon, width=90, anchor="e" if kolon in ("matrah", "kdv", "toplam") else "w")
        self.fatura_tree.pack(side="left", fill="both", expand=True)
        kaydirma = ttk.Scrollbar(sol, orient="vertical", command=self.fatura_tree.yview)
        self.fatura_tree.configure(yscrollcommand=kaydirma.set)
        kaydirma.pack(side="right", fill="y")
        self.fatura_tree.bind("<<TreeviewSelect>>", self._fatura_secildi)

        form = ttk.LabelFrame(sekme, text="Fatura Düzenle", padding=8)
        form.pack(side="right", fill="y", padx=(8, 0))
        alanlar = [
            ("belge_no", "Belge No", 26), ("tarih", "Tarih", 10),
            ("satici_vkn", "Satıcı VKN", 14), ("satici_unvan", "Satıcı Ünvan", 34),
            ("alici_vkn", "Alıcı VKN", 14), ("matrah", "Matrah", 12),
            ("kdv", "KDV", 12), ("toplam", "Toplam", 12),
        ]
        self.fatura_girdiler = {}
        for i, (anahtar, etiket, genislik) in enumerate(alanlar):
            ttk.Label(form, text=etiket + ":").grid(row=i, column=0, sticky="w", pady=2, padx=(0, 6))
            girdi = ttk.Entry(form, width=genislik)
            girdi.grid(row=i, column=1, sticky="we", pady=2)
            self.fatura_girdiler[anahtar] = girdi
        form.columnconfigure(1, weight=1)
        ttk.Button(form, text="Kaydet", command=self._fatura_kaydet).grid(row=len(alanlar), column=0, sticky="we", pady=4, padx=(0, 3))
        ttk.Button(form, text="Satırı Sil", command=self._fatura_sil).grid(row=len(alanlar), column=1, sticky="we", pady=4)
        self.fatura_form = form
        self._fatura_listesini_doldur()

    def _muavin_sekmesi(self, notebook):
        sekme = ttk.Frame(notebook, padding=6)
        notebook.add(sekme, text=f"Muavin ({len(self.cetvel_kayitlari)})")

        sol = ttk.Frame(sekme)
        sol.pack(side="left", fill="both", expand=True)

        kolonlar = ("belge_no", "tarih", "vkn", "unvan", "kdv", "notlar")
        basliklar = {
            "belge_no": "Belge No", "tarih": "Tarih", "vkn": "VKN",
            "unvan": "Ünvan", "kdv": "KDV", "notlar": "Notlar",
        }
        self.muavin_tree = ttk.Treeview(sol, columns=kolonlar, show="headings", height=16)
        for kolon in kolonlar:
            self.muavin_tree.heading(kolon, text=basliklar[kolon])
            self.muavin_tree.column(kolon, width=90, anchor="e" if kolon == "kdv" else "w")
        self.muavin_tree.pack(side="left", fill="both", expand=True)
        kaydirma = ttk.Scrollbar(sol, orient="vertical", command=self.muavin_tree.yview)
        self.muavin_tree.configure(yscrollcommand=kaydirma.set)
        kaydirma.pack(side="right", fill="y")
        self.muavin_tree.bind("<<TreeviewSelect>>", self._muavin_secildi)

        form = ttk.LabelFrame(sekme, text="Muavin Kaydı Düzenle", padding=8)
        form.pack(side="right", fill="y", padx=(8, 0))
        alanlar = [
            ("belge_no", "Belge No", 26), ("tarih", "Tarih", 10),
            ("vkn", "VKN", 14), ("unvan", "Ünvan", 34),
            ("matrah", "Matrah", 12), ("kdv", "KDV", 12),
        ]
        self.muavin_girdiler = {}
        for i, (anahtar, etiket, genislik) in enumerate(alanlar):
            ttk.Label(form, text=etiket + ":").grid(row=i, column=0, sticky="w", pady=2, padx=(0, 6))
            girdi = ttk.Entry(form, width=genislik)
            girdi.grid(row=i, column=1, sticky="we", pady=2)
            self.muavin_girdiler[anahtar] = girdi
        form.columnconfigure(1, weight=1)
        ttk.Button(form, text="Kaydet", command=self._muavin_kaydet).grid(row=len(alanlar), column=0, sticky="we", pady=4, padx=(0, 3))
        ttk.Button(form, text="Yeni Kayıt Ekle", command=self._muavin_yeni).grid(row=len(alanlar), column=1, sticky="we", pady=4)
        ttk.Button(form, text="Satırı Sil", command=self._muavin_sil).grid(row=len(alanlar) + 1, column=0, columnspan=2, sticky="we", pady=2)
        self.muavin_form = form
        self._muavin_listesini_doldur()

    # ---------- Faturalar ----------
    def _fatura_listesini_doldur(self):
        self.fatura_tree.delete(*self.fatura_tree.get_children())
        for f in self.faturalar:
            self.fatura_tree.insert("", "end", values=(
                f.get("belge_no") or "", f.get("tarih") or "",
                f.get("satici_vkn") or "", f.get("satici_unvan") or "",
                f.get("matrah") or "", f.get("kdv") or "", f.get("toplam") or "",
                f.get("fatura_tipi") or "",
            ))

    def _fatura_secildi(self, _event):
        secim = self.fatura_tree.selection()
        if not secim:
            return
        indeks = self.fatura_tree.index(secim[0])
        if indeks >= len(self.faturalar):
            return
        f = self.faturalar[indeks]
        for anahtar, girdi in self.fatura_girdiler.items():
            girdi.delete(0, "end")
            girdi.insert(0, str(f.get(anahtar) if f.get(anahtar) is not None else ""))

    def _fatura_kaydet(self):
        secim = self.fatura_tree.selection()
        if not secim:
            messagebox.showwarning("Uyarı", "Önce bir fatura satırı seçin.", parent=self)
            return
        indeks = self.fatura_tree.index(secim[0])
        if indeks >= len(self.faturalar):
            return
        f = self.faturalar[indeks]
        for anahtar, girdi in self.fatura_girdiler.items():
            deger = girdi.get().strip()
            if anahtar in ("matrah", "kdv", "toplam"):
                if deger == "":
                    f[anahtar] = None
                else:
                    sayi = _sayiya_cevir(deger)
                    if sayi is None:
                        messagebox.showerror("Hata", f"Geçersiz sayı: {deger}", parent=self)
                        return
                    f[anahtar] = sayi
            else:
                f[anahtar] = deger
        self.degisen = True
        self._fatura_listesini_doldur()
        messagebox.showinfo("Tamam", "Fatura güncellendi.", parent=self)

    def _fatura_sil(self):
        secim = self.fatura_tree.selection()
        if not secim:
            return
        indeks = self.fatura_tree.index(secim[0])
        if indeks >= len(self.faturalar):
            return
        if not messagebox.askyesno("Sil", "Bu fatura listeden kaldırılsın mı?", parent=self):
            return
        del self.faturalar[indeks]
        self.degisen = True
        self._fatura_listesini_doldur()

    # ---------- Muavin ----------
    def _muavin_listesini_doldur(self):
        self.muavin_tree.delete(*self.muavin_tree.get_children())
        for c in self.cetvel_kayitlari:
            notlar = " / ".join(c.get("notlar") or [])
            self.muavin_tree.insert("", "end", values=(
                c.get("belge_no") or "", c.get("tarih") or "",
                c.get("vkn") or "", c.get("unvan") or "",
                c.get("kdv") or "", notlar,
            ))

    def _muavin_secildi(self, _event):
        secim = self.muavin_tree.selection()
        if not secim:
            return
        indeks = self.muavin_tree.index(secim[0])
        if indeks >= len(self.cetvel_kayitlari):
            return
        c = self.cetvel_kayitlari[indeks]
        for anahtar, girdi in self.muavin_girdiler.items():
            girdi.delete(0, "end")
            girdi.insert(0, str(c.get(anahtar) if c.get(anahtar) is not None else ""))

    def _muavin_kaydet(self):
        secim = self.muavin_tree.selection()
        if not secim:
            messagebox.showwarning("Uyarı", "Önce bir muavin satırı seçin.", parent=self)
            return
        indeks = self.muavin_tree.index(secim[0])
        if indeks >= len(self.cetvel_kayitlari):
            return
        c = self.cetvel_kayitlari[indeks]
        for anahtar, girdi in self.muavin_girdiler.items():
            deger = girdi.get().strip()
            if anahtar in ("matrah", "kdv"):
                if deger == "":
                    c[anahtar] = None
                else:
                    sayi = _sayiya_cevir(deger)
                    if sayi is None:
                        messagebox.showerror("Hata", f"Geçersiz sayı: {deger}", parent=self)
                        return
                    c[anahtar] = sayi
            else:
                c[anahtar] = deger
        self.degisen = True
        self._muavin_listesini_doldur()
        messagebox.showinfo("Tamam", "Muavin kaydı güncellendi.", parent=self)

    def _muavin_yeni(self):
        yeni = {
            "belge_no": self.muavin_girdiler["belge_no"].get().strip(),
            "tarih": self.muavin_girdiler["tarih"].get().strip(),
            "vkn": self.muavin_girdiler["vkn"].get().strip(),
            "unvan": self.muavin_girdiler["unvan"].get().strip(),
            "matrah": _sayiya_cevir(self.muavin_girdiler["matrah"].get()),
            "kdv": _sayiya_cevir(self.muavin_girdiler["kdv"].get()),
            "notlar": ["Elle eklenen kayıt"],
        }
        if not yeni["belge_no"]:
            messagebox.showwarning("Uyarı", "Belge No zorunludur.", parent=self)
            return
        self.cetvel_kayitlari.append(yeni)
        self.degisen = True
        self._muavin_listesini_doldur()
        messagebox.showinfo("Tamam", "Muavin kaydı eklendi.", parent=self)

    def _muavin_sil(self):
        secim = self.muavin_tree.selection()
        if not secim:
            return
        indeks = self.muavin_tree.index(secim[0])
        if indeks >= len(self.cetvel_kayitlari):
            return
        if not messagebox.askyesno("Sil", "Bu muavin kaydı listeden kaldırılsın mı?", parent=self):
            return
        del self.cetvel_kayitlari[indeks]
        self.degisen = True
        self._muavin_listesini_doldur()

    def _yeniden_kontrol(self):
        if not self.degisen:
            messagebox.showinfo("Bilgi", "Kaydedilmiş bir değişiklik yok.", parent=self)
            return
        if self.yeniden_kontrol_callback:
            self.yeniden_kontrol_callback()
        if self.log_callback:
            self.log_callback("Veri düzenlendi, kontrol yeniden hesaplandı.")
        self.degisen = False
        messagebox.showinfo("Tamam", "Kontrol yeniden hesaplandı.", parent=self)
