"""Veri İncele & Düzelt penceresi: arama, sıralama, sorunlu filtre ve düzenleme."""
import os
import subprocess
from decimal import Decimal, InvalidOperation

import tkinter as tk
from tkinter import messagebox, ttk

from matcher import SORUNLU_DURUMLAR
from utils import rakamlara_cevir


def _sayiya_cevir(metin):
    metin = (metin or "").strip().replace(",", ".")
    if not metin:
        return None
    try:
        return Decimal(metin)
    except InvalidOperation:
        return None


def _arama_metni(*parcalar):
    return rakamlara_cevir(" ".join(str(p or "") for p in parcalar)).upper()


def _sorunlu_mu(durum):
    if durum in SORUNLU_DURUMLAR:
        return True
    if durum.startswith("İADE"):
        return durum not in ("İADE EŞLEŞTİ", "İADE TEVKİFATLI")
    return False


class VeriIncelePenceresi(tk.Toplevel):
    """Faturaları ve muavin kayıtlarını arayıp bulan, inceleyip düzelten pencere."""

    def __init__(self, parent, faturalar, cetvel_kayitlari,
                 yeniden_kontrol_callback=None, log_callback=None,
                 sonuc_satirlari=None):
        super().__init__(parent)
        self.faturalar = faturalar
        self.cetvel_kayitlari = cetvel_kayitlari
        self.yeniden_kontrol_callback = yeniden_kontrol_callback
        self.log_callback = log_callback
        self.degisen = False

        self._fatura_durumlari = {}
        self._muavin_durumlari = {}
        for r in (sonuc_satirlari or []):
            anahtar = (r.get("belge_no") or "").upper()
            if not anahtar:
                continue
            hedef = self._fatura_durumlari if str(r.get("kaynak") or "").startswith("Fatura") \
                else self._muavin_durumlari
            mevcut = hedef.get(anahtar)
            if mevcut is None or (_sorunlu_mu(r["durum"]) and not _sorunlu_mu(mevcut)):
                hedef[anahtar] = r["durum"]

        self.title("Veriyi İncele & Düzelt")
        self.geometry("1150x680")
        self.transient(parent)
        self._arayuz_kur()

    def _arayuz_kur(self):
        ana = ttk.Frame(self, padding=8)
        ana.pack(fill="both", expand=True)

        aciklama = ttk.Label(
            ana,
            text=("Arama kutusuna belge no / VKN / ünvan / tutar yazın (O ile 0, I ile 1 fark etmez). "
                  "Başlık tıklayınca o kolona göre sıralanır. Satır seçip sağdaki alanlardan düzeltin."),
            background="#DDEBF7", padding=6, anchor="w",
        )
        aciklama.pack(fill="x", pady=(0, 6))

        self.notebook = ttk.Notebook(ana)
        self.notebook.pack(fill="both", expand=True)

        self._fatura_sekmesi(self.notebook)
        self._muavin_sekmesi(self.notebook)

        alt = ttk.Frame(ana)
        alt.pack(fill="x", pady=(6, 0))
        ttk.Button(alt, text="Kontrolü Yeniden Çalıştır", command=self._yeniden_kontrol).pack(side="left")
        ttk.Label(alt, text="Değişiklikler bellek içinde uygulanır.", foreground="#666666").pack(
            side="left", padx=10)

    def _arama_cubugu(self, ebeveyn, geri_cagri):
        cubuk = ttk.Frame(ebeveyn)
        cubuk.pack(fill="x", pady=(0, 5))
        ttk.Label(cubuk, text="🔍 Ara:").pack(side="left")
        arama = tk.StringVar()
        girdi = ttk.Entry(cubuk, textvariable=arama, width=32)
        girdi.pack(side="left", padx=(4, 10))
        sadece_sorunlu = tk.BooleanVar(value=False)
        ttk.Checkbutton(cubuk, text="Sadece sorunlu satırlar",
                        variable=sadece_sorunlu, command=geri_cagri).pack(side="left")
        sayac = ttk.Label(cubuk, text="", foreground="#444444")
        sayac.pack(side="right")

        def tetikleyici(*_args):
            geri_cagri()

        arama.trace_add("write", tetikleyici)
        return {"sorgu": arama, "sorunlu": sadece_sorunlu, "sayac": sayac}

    # ---------- Faturalar ----------
    def _fatura_sekmesi(self, notebook):
        sekme = ttk.Frame(notebook, padding=6)
        notebook.add(sekme, text="Faturalar")
        self._fatura_sekme = sekme

        sol = ttk.Frame(sekme)
        sol.pack(side="left", fill="both", expand=True)

        self._fatura_arama = self._arama_cubugu(sol, self._fatura_listesini_doldur)

        kolonlar = ("belge_no", "tarih", "vkn", "unvan", "matrah", "kdv", "toplam", "tip", "durum")
        basliklar = {
            "belge_no": "Belge No", "tarih": "Tarih", "vkn": "VKN", "unvan": "Satıcı",
            "matrah": "Matrah", "kdv": "KDV", "toplam": "Toplam", "tip": "Tip",
            "durum": "Durum",
        }
        self._fatura_siralama = ("", False)

        self.fatura_tree = ttk.Treeview(sol, columns=kolonlar, show="headings", height=16)
        for kolon in kolonlar:
            genislik = 130 if kolon == "unvan" else (110 if kolon == "belge_no" else 88)
            self.fatura_tree.heading(
                kolon, text=basliklar[kolon],
                command=lambda k=kolon: self._fatura_sirala(k))
            self.fatura_tree.column(kolon, width=genislik,
                                    anchor="e" if kolon in ("matrah", "kdv", "toplam") else "w")
        self.fatura_tree.pack(side="left", fill="both", expand=True)
        kaydirma = ttk.Scrollbar(sol, orient="vertical", command=self.fatura_tree.yview)
        self.fatura_tree.configure(yscrollcommand=kaydirma.set)
        kaydirma.pack(side="right", fill="y")
        self.fatura_tree.bind("<<TreeviewSelect>>", self._fatura_secildi)
        self.fatura_tree.bind("<Double-1>", lambda e: self._fatura_dosya_ac())

        self._fatura_iid = {}

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
        satir = len(alanlar)
        ttk.Button(form, text="Kaydet", command=self._fatura_kaydet).grid(row=satir, column=0, sticky="we", pady=4, padx=(0, 3))
        ttk.Button(form, text="Satırı Sil", command=self._fatura_sil).grid(row=satir, column=1, sticky="we", pady=4)
        self._fatura_dosya_buton = ttk.Button(form, text="📂 Kaynak Dosyayı Aç",
                                              command=self._fatura_dosya_ac, state="disabled")
        self._fatura_dosya_buton.grid(row=satir + 1, column=0, columnspan=2, sticky="we", pady=2)
        self.fatura_form = form
        self._fatura_listesini_doldur()

    def _fatura_filtreli_liste(self):
        sorgu = _arama_metni(self._fatura_arama["sorgu"].get())
        sadece = self._fatura_arama["sorunlu"].get()
        liste = []
        for f in self.faturalar:
            durum = self._fatura_durumlari.get((f.get("belge_no") or "").upper(), "")
            if sadece and not _sorunlu_mu(durum):
                continue
            if sorgu:
                yigin = _arama_metni(f.get("belge_no"), f.get("satici_vkn"),
                                     f.get("satici_unvan"), f.get("tarih"),
                                     f.get("matrah"), f.get("kdv"), f.get("toplam"))
                if sorgu not in yigin:
                    continue
            liste.append(f)
        siralama_kolonu, ters = self._fatura_siralama
        if siralama_kolonu:
            alan = {"vkn": "satici_vkn", "unvan": "satici_unvan"}.get(siralama_kolonu, siralama_kolonu)
            sayisal = siralama_kolonu in ("matrah", "kdv", "toplam")

            def _anahtar(fa):
                if alan == "durum":
                    deger = self._fatura_durumlari.get((fa.get("belge_no") or "").upper(), "")
                else:
                    deger = fa.get(alan)
                if sayisal:
                    return (deger is None, float(deger or 0))
                return str(deger or "").lower()
            liste.sort(key=_anahtar, reverse=ters)
        return liste

    def _fatura_listesini_doldur(self):
        self.fatura_tree.delete(*self.fatura_tree.get_children())
        self._fatura_iid.clear()
        liste = self._fatura_filtreli_liste()
        for n, fa in enumerate(liste):
            durum = self._fatura_durumlari.get((fa.get("belge_no") or "").upper(), "")
            iid = f"f{n}"
            self._fatura_iid[iid] = fa
            etiketler = (
                fa.get("belge_no") or "", fa.get("tarih") or "",
                fa.get("satici_vkn") or "", fa.get("satici_unvan") or "",
                fa.get("matrah") or "", fa.get("kdv") or "", fa.get("toplam") or "",
                fa.get("fatura_tipi") or "", durum,
            )
            self.fatura_tree.insert("", "end", iid=iid, values=etiketler)
            if durum and _sorunlu_mu(durum):
                self.fatura_tree.tag_configure("sorunlu", foreground="#B00000")
                self.fatura_tree.item(iid, tags=("sorunlu",))
        toplam = len(self.faturalar)
        self.notebook.tab(self._fatura_sekme, text=f"Faturalar ({len(liste)}/{toplam})")
        self._fatura_arama["sayac"].configure(text=f"{len(liste)} kayıt")

    def _fatura_sirala(self, kolon):
        eski_kolon, eski_ters = self._fatura_siralama
        ters = (kolon == eski_kolon) and not eski_ters
        self._fatura_siralama = (kolon, ters)
        isaret = " ▼" if ters else " ▲"
        for k in self.fatura_tree["columns"]:
            metin = {"belge_no": "Belge No", "tarih": "Tarih", "vkn": "VKN",
                     "unvan": "Satıcı", "matrah": "Matrah", "kdv": "KDV",
                     "toplam": "Toplam", "tip": "Tip", "durum": "Durum"}[k]
            self.fatura_tree.heading(k, text=metin + (isaret if k == kolon else ""))
        self._fatura_listesini_doldur()

    def _secili_fatura(self):
        secim = self.fatura_tree.selection()
        if not secim:
            return None
        return self._fatura_iid.get(secim[0])

    def _fatura_secildi(self, _event):
        f = self._secili_fatura()
        if f is None:
            return
        for anahtar, girdi in self.fatura_girdiler.items():
            girdi.delete(0, "end")
            girdi.insert(0, str(f.get(anahtar) if f.get(anahtar) is not None else ""))
        self._fatura_dosya_buton.configure(state="normal" if f.get("dosya") else "disabled")

    def _fatura_kaydet(self):
        f = self._secili_fatura()
        if f is None:
            messagebox.showwarning("Uyarı", "Önce bir fatura satırı seçin.", parent=self)
            return
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
        f = self._secili_fatura()
        if f is None:
            return
        if not messagebox.askyesno("Sil", "Bu fatura listeden kaldırılsın mı?", parent=self):
            return
        self.faturalar.remove(f)
        self.degisen = True
        self._fatura_listesini_doldur()

    def _fatura_dosya_ac(self):
        f = self._secili_fatura()
        yol = (f or {}).get("dosya")
        if not yol or not os.path.exists(yol):
            messagebox.showwarning("Uyarı", "Kaynak dosya bulunamadı.", parent=self)
            return
        try:
            subprocess.Popen(["explorer", "/select,", os.path.normpath(yol)])
        except Exception:
            os.startfile(os.path.dirname(yol))

    # ---------- Muavin ----------
    def _muavin_sekmesi(self, notebook):
        sekme = ttk.Frame(notebook, padding=6)
        notebook.add(sekme, text="Muavin")
        self._muavin_sekme = sekme

        sol = ttk.Frame(sekme)
        sol.pack(side="left", fill="both", expand=True)

        self._muavin_arama = self._arama_cubugu(sol, self._muavin_listesini_doldur)

        kolonlar = ("belge_no", "tarih", "vkn", "unvan", "kdv", "durum", "notlar")
        basliklar = {
            "belge_no": "Belge No", "tarih": "Tarih", "vkn": "VKN",
            "unvan": "Ünvan", "kdv": "KDV", "durum": "Durum", "notlar": "Notlar",
        }
        self._muavin_siralama = ("", False)

        self.muavin_tree = ttk.Treeview(sol, columns=kolonlar, show="headings", height=16)
        for kolon in kolonlar:
            genislik = 130 if kolon == "unvan" else (110 if kolon == "belge_no" else 88)
            if kolon == "notlar":
                genislik = 160
            self.muavin_tree.heading(
                kolon, text=basliklar[kolon],
                command=lambda k=kolon: self._muavin_sirala(k))
            self.muavin_tree.column(kolon, width=genislik,
                                    anchor="e" if kolon == "kdv" else "w")
        self.muavin_tree.pack(side="left", fill="both", expand=True)
        kaydirma = ttk.Scrollbar(sol, orient="vertical", command=self.muavin_tree.yview)
        self.muavin_tree.configure(yscrollcommand=kaydirma.set)
        kaydirma.pack(side="right", fill="y")
        self.muavin_tree.bind("<<TreeviewSelect>>", self._muavin_secildi)

        self._muavin_iid = {}

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

    def _muavin_filtreli_liste(self):
        sorgu = _arama_metni(self._muavin_arama["sorgu"].get())
        sadece = self._muavin_arama["sorunlu"].get()
        liste = []
        for c in self.cetvel_kayitlari:
            durum = self._muavin_durumlari.get((c.get("belge_no") or "").upper(), "")
            if sadece and not _sorunlu_mu(durum):
                continue
            if sorgu:
                yigin = _arama_metni(c.get("belge_no"), c.get("vkn"), c.get("unvan"),
                                     c.get("tarih"), c.get("matrah"), c.get("kdv"))
                if sorgu not in yigin:
                    continue
            liste.append(c)
        siralama_kolonu, ters = self._muavin_siralama
        if siralama_kolonu:
            alan = siralama_kolonu
            sayisal = siralama_kolonu == "kdv"

            def _anahtar(ca):
                if alan == "durum":
                    deger = self._muavin_durumlari.get((ca.get("belge_no") or "").upper(), "")
                else:
                    deger = ca.get(alan)
                if sayisal:
                    return (deger is None, float(deger or 0))
                return str(deger or "").lower()
            liste.sort(key=_anahtar, reverse=ters)
        return liste

    def _muavin_listesini_doldur(self):
        self.muavin_tree.delete(*self.muavin_tree.get_children())
        self._muavin_iid.clear()
        liste = self._muavin_filtreli_liste()
        for n, ca in enumerate(liste):
            durum = self._muavin_durumlari.get((ca.get("belge_no") or "").upper(), "")
            notlar = " / ".join(ca.get("notlar") or [])
            iid = f"m{n}"
            self._muavin_iid[iid] = ca
            iid_etiket = (
                ca.get("belge_no") or "", ca.get("tarih") or "",
                ca.get("vkn") or "", ca.get("unvan") or "",
                ca.get("kdv") or "", durum, notlar,
            )
            self.muavin_tree.insert("", "end", iid=iid, values=iid_etiket)
            if durum and _sorunlu_mu(durum):
                self.muavin_tree.tag_configure("sorunlu", foreground="#B00000")
                self.muavin_tree.item(iid, tags=("sorunlu",))
        toplam = len(self.cetvel_kayitlari)
        self.notebook.tab(self._muavin_sekme, text=f"Muavin ({len(liste)}/{toplam})")
        self._muavin_arama["sayac"].configure(text=f"{len(liste)} kayıt")

    def _muavin_sirala(self, kolon):
        eski_kolon, eski_ters = self._muavin_siralama
        ters = (kolon == eski_kolon) and not eski_ters
        self._muavin_siralama = (kolon, ters)
        isaret = " ▼" if ters else " ▲"
        for k in self.muavin_tree["columns"]:
            metin = {"belge_no": "Belge No", "tarih": "Tarih", "vkn": "VKN",
                     "unvan": "Ünvan", "kdv": "KDV", "durum": "Durum",
                     "notlar": "Notlar"}[k]
            self.muavin_tree.heading(k, text=metin + (isaret if k == kolon else ""))
        self._muavin_listesini_doldur()

    def _secili_muavin(self):
        secim = self.muavin_tree.selection()
        if not secim:
            return None
        return self._muavin_iid.get(secim[0])

    def _muavin_secildi(self, _event):
        c = self._secili_muavin()
        if c is None:
            return
        for anahtar, girdi in self.muavin_girdiler.items():
            girdi.delete(0, "end")
            girdi.insert(0, str(c.get(anahtar) if c.get(anahtar) is not None else ""))

    def _muavin_kaydet(self):
        c = self._secili_muavin()
        if c is None:
            messagebox.showwarning("Uyarı", "Önce bir muavin satırı seçin.", parent=self)
            return
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
        c = self._secili_muavin()
        if c is None:
            return
        if not messagebox.askyesno("Sil", "Bu muavin kaydı listeden kaldırılsın mı?", parent=self):
            return
        self.cetvel_kayitlari.remove(c)
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
