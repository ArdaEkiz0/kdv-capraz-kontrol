"""Firma kuralları düzenleme penceresi."""
import tkinter as tk
from tkinter import ttk, messagebox
from decimal import Decimal, InvalidOperation

from kurallar import kurallari_kaydet


class KurallarPenceresi(tk.Toplevel):
    def __init__(self, ust, kurallar, kaydet_callback=None):
        super().__init__(ust)
        self.title("Firma Kuralları")
        self.geometry("640x430")
        self.minsize(560, 380)
        self.transient(ust)
        self.grab_set()

        self.kurallar = [dict(k) for k in (kurallar or [])]
        self.kaydet_callback = kaydet_callback
        self.secili_indeks = None

        ana = ttk.Frame(self, padding=10)
        ana.pack(fill="both", expand=True)

        ust = ttk.Frame(ana)
        ust.pack(fill="both", expand=True)

        # ---- Sol: kural listesi ----
        sol = ttk.Frame(ust)
        sol.pack(side="left", fill="both", expand=True, padx=(0, 10))
        ttk.Label(sol, text="Kurallar", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        liste_cerceve = ttk.Frame(sol)
        liste_cerceve.pack(fill="both", expand=True, pady=(4, 0))
        self.liste = tk.Listbox(liste_cerceve, activestyle="none", font=("Segoe UI", 9))
        kaydirma = ttk.Scrollbar(liste_cerceve, orient="vertical", command=self.liste.yview)
        self.liste.configure(yscrollcommand=kaydirma.set)
        self.liste.pack(side="left", fill="both", expand=True)
        kaydirma.pack(side="right", fill="y")
        self.liste.bind("<<ListboxSelect>>", lambda e: self._liste_secildi())

        buton_sol = ttk.Frame(sol)
        buton_sol.pack(fill="x", pady=(6, 0))
        ttk.Button(buton_sol, text="➕ Yeni Kural", command=self._yeni).pack(side="left", padx=(0, 4))
        ttk.Button(buton_sol, text="🗑 Sil", command=self._sil).pack(side="left")

        # ---- Sağ: form ----
        sag = ttk.Frame(ust)
        sag.pack(side="left", fill="both")

        self.v_ad = tk.StringVar()
        self.v_eslesme = tk.StringVar()
        self.v_oran = tk.StringVar()
        self.v_onayla = tk.BooleanVar(value=False)

        def satir(etiket, degisken, genislik=26, aciklama=""):
            cerceve = ttk.Frame(sag)
            cerceve.pack(fill="x", pady=(0, 8))
            ttk.Label(cerceve, text=etiket, width=16).pack(side="left")
            girdi = ttk.Entry(cerceve, textvariable=degisken, width=genislik)
            girdi.pack(side="left")
            if aciklama:
                ttk.Label(cerceve, text="  " + aciklama,
                          foreground="#64748b").pack(side="left")
            return girdi

        ttk.Label(sag, text="Kural Detayı", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        satir("Ad:", self.v_ad, aciklama="(isteğe bağlı)")
        satir("Eşleştirme:", self.v_eslesme, aciklama="ünvan / VKN / belge no'da aranır")
        satir("Tevkifat oranı:", self.v_oran, aciklama='örn. "0,90" = %90 kesinti')
        ttk.Checkbutton(sag, text="Bu firmanın farklarını onaylı işaretle",
                        variable=self.v_onayla).pack(anchor="w", pady=(2, 10))

        ttk.Label(sag, foreground="#64748b", justify="left", wraplength=280,
                  text="Onaylı işaretlenen firmaların sorunlu satırları\n"
                       "'ONAYLI FARK' olur ve sorun sayılmaz.\n"
                       "Oran girilirse o kesintiyle tevkifat eşleşmesi kabul edilir\n"
                       '(örn. "0,90" = muavinde fatura KDV\'sinin %10\'u beklenir).').pack(anchor="w")

        # ---- Alt: kaydet/kapat ----
        alt = ttk.Frame(ana)
        alt.pack(fill="x", pady=(10, 0))
        ttk.Button(alt, text="💾 Kaydet", style="Primary.TButton",
                   command=self._kaydet).pack(side="right")
        ttk.Button(alt, text="Kapat", command=self.destroy).pack(side="right", padx=(0, 6))

        self._listeyi_doldur()
        if self.kurallar:
            self.liste.selection_set(0)
            self._liste_secildi()

    # ---------- yardımcılar ----------
    def _satir_metni(self, k):
        parcalar = [k.get("ad") or "(ad yok)", f'"{k.get("eslesme")}"']
        if k.get("oran"):
            parcalar.append(f"oran %{int(Decimal(str(k['oran'])) * 100)}")
        if k.get("onayla"):
            parcalar.append("onaylı")
        return " — ".join(parcalar)

    def _listeyi_doldur(self):
        self.liste.delete(0, "end")
        for k in self.kurallar:
            self.liste.insert("end", self._satir_metni(k))

    def _liste_secildi(self):
        secim = self.liste.curselection()
        if not secim:
            return
        self.secili_indeks = secim[0]
        k = self.kurallar[self.secili_indeks]
        self.v_ad.set(k.get("ad") or "")
        self.v_eslesme.set(k.get("eslesme") or "")
        self.v_oran.set(k.get("oran") or "")
        self.v_onayla.set(bool(k.get("onayla")))

    def _yeni(self):
        self.liste.selection_clear(0, "end")
        self.secili_indeks = None
        self.v_ad.set("")
        self.v_eslesme.set("")
        self.v_oran.set("")
        self.v_onayla.set(False)

    def _sil(self):
        if self.secili_indeks is None or not (0 <= self.secili_indeks < len(self.kurallar)):
            messagebox.showinfo("Bilgi", "Silinecek kuralı listeden seçin.", parent=self)
            return
        del self.kurallar[self.secili_indeks]
        self.secili_indeks = None
        self._listeyi_doldur()
        self._yeni()
        self._disa_kaydet()

    # ---------- kaydet ----------
    def _formdan_kural(self):
        eslesme = self.v_eslesme.get().strip()
        if not eslesme:
            messagebox.showwarning("Uyarı", "'Eşleştirme' alanı boş olamaz.", parent=self)
            return None
        oran = self.v_oran.get().strip().replace(",", ".")
        if oran:
            try:
                deger = Decimal(oran)
                if not (Decimal("0") < deger < Decimal("1")):
                    raise ValueError
            except (InvalidOperation, ValueError):
                messagebox.showwarning("Uyarı",
                                       'Tevkifat oranı 0 ile 1 arasında olmalı (örn. "0,90").',
                                       parent=self)
                return None
        return {
            "ad": self.v_ad.get().strip(),
            "eslesme": eslesme,
            "oran": oran,
            "onayla": bool(self.v_onayla.get()),
        }

    def _disa_kaydet(self):
        temiz = kurallari_kaydet(self.kurallar)
        self.kurallar = temiz
        self._listeyi_doldur()
        if self.kaydet_callback:
            try:
                self.kaydet_callback(list(temiz))
            except Exception:
                pass

    def _kaydet(self):
        kural = self._formdan_kural()
        if kural is None:
            return
        if self.secili_indeks is not None and 0 <= self.secili_indeks < len(self.kurallar):
            self.kurallar[self.secili_indeks] = kural
        else:
            self.kurallar.append(kural)
            self.secili_indeks = len(self.kurallar) - 1
        self._disa_kaydet()
        self.liste.selection_set(self.secili_indeks)
