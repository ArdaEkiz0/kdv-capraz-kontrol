"""Mükellefler paneli: profiller, yerel şifreli saklama ve otomatik GİB/Luca çekimi."""
import calendar
import os
import threading
import tkinter as tk
from datetime import date
from tkinter import filedialog, messagebox, ttk

import gib_cekme
import luca_cekme
import mukellefler

AYLAR = [(str(a), a) for a in range(1, 13)]
ENT_KURUMLAR = ["", "NetteFatura (İşNet)", "Luca / Türmob", "Diğer"]


def ac(uygulama):
    return MukellefPaneli(uygulama)


class MukellefPaneli(tk.Toplevel):
    def __init__(self, uygulama):
        super().__init__(uygulama.kok)
        self.uygulama = uygulama
        self.title("Mükellefler")
        self.geometry("900x620")
        self.minsize(820, 560)
        self.mukellefler = []
        self.secili_id = None

        ust = tk.Frame(self, bg="#1e3a8a")
        ust.pack(fill="x")
        tk.Label(ust, text="👥 Mükellefler", font=("Segoe UI", 12, "bold"),
                 bg="#1e3a8a", fg="#ffffff").pack(side="left", padx=12, pady=8)
        tk.Label(ust, text="Şifreler yalnız bu bilgisayarda şifreli saklanır",
                 font=("Segoe UI", 9), bg="#1e3a8a",
                 fg="#bfdbfe").pack(side="right", padx=12)

        govde = tk.Frame(self)
        govde.pack(fill="both", expand=True)

        sol = tk.Frame(govde, padx=8, pady=8)
        sol.pack(side="left", fill="both", expand=False)
        sutunlar = ("ad", "vkn")
        self.liste = ttk.Treeview(sol, columns=sutunlar, show="headings", height=14)
        self.liste.heading("ad", text="Unvan / Ad")
        self.liste.heading("vkn", text="VKN / TC")
        self.liste.column("ad", width=200)
        self.liste.column("vkn", width=110)
        self.liste.pack(fill="both", expand=True)
        self.liste.bind("<<TreeviewSelect>>", lambda e: self._secim_yukle())
        dugmeler = tk.Frame(sol)
        dugmeler.pack(fill="x", pady=(6, 0))
        ttk.Button(dugmeler, text="➕ Yeni", command=self._yeni,
                   style="Arac.TButton").pack(side="left", padx=(0, 4))
        ttk.Button(dugmeler, text="🗑 Sil", command=self._sil,
                   style="Arac.TButton").pack(side="left")

        sag = tk.Frame(govde, padx=4, pady=8)
        sag.pack(side="left", fill="both", expand=True)
        self.alanlar = {}
        satirlar = [
            ("ad", "Unvan / Ad *", ""),
            ("vkn", "VKN / TC", ""),
            ("gib_tc", "GİB (DVD) TC / Kullanıcı", ""),
            ("gib_sifre", "GİB (DVD) Şifre", "•"),
            ("ivd_kod", "IVD Kullanıcı Kodu (opsiyonel)", ""),
            ("ivd_sifre", "IVD Şifre", "•"),
            ("__ent_kurum__", "Entegratör", ""),
            ("ent_kullanici", "Entegratör Kullanıcı", ""),
            ("ent_sifre", "Entegratör Şifre", "•"),
            ("luca_uye", "Luca Üye Numarası", ""),
            ("not", "Not", ""),
        ]
        for i, (anahtar, etiket, maske) in enumerate(satirlar):
            ttk.Label(sag, text=etiket).grid(row=i, column=0, sticky="w",
                                             pady=2, padx=(0, 8))
            if anahtar == "__ent_kurum__":
                # Entegratör kurum seçimi kendi satırinda; altindaki
                # kullanici/sifre alanlarinin uzerine binmesin.
                self.ent_kurum = ttk.Combobox(sag, values=ENT_KURUMLAR,
                                              width=38, state="readonly")
                self.ent_kurum.set("")
                self.ent_kurum.grid(row=i, column=1, sticky="ew", pady=2)
                continue
            giris = ttk.Entry(sag, width=38, show=maske)
            giris.grid(row=i, column=1, sticky="ew", pady=2)
            self.alanlar[anahtar] = giris
        sag.columnconfigure(1, weight=1)
        ttk.Button(sag, text="💾 Kaydet", command=self._kaydet,
                   style="Primary.TButton").grid(row=len(satirlar), column=1,
                                                 sticky="e", pady=(10, 0))

        alt = tk.Frame(self, pady=8)
        alt.pack(fill="x", side="bottom")
        kart = tk.Frame(alt, bd=1, relief="solid", padx=10, pady=8)
        kart.pack(fill="x", padx=10)
        tk.Label(kart, text="Otomatik Fatura Çekme (e-Arşiv alış)",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(kart, text=("GİB'ten yalnız e-Arşiv alış faturaları otomatik "
                             "çekilir (e-Fatura için e-İmza/entegratör gerekir). "
                             "Sorgu geriye en fazla 2 ay. Entegratör 'Luca / "
                             "Türmob' seçiliyse 191/391 muavini Luca'dan "
                             "çekilir."), wraplength=700,
                 justify="left", fg="#555555").pack(anchor="w")
        satir = tk.Frame(kart)
        satir.pack(fill="x", pady=(6, 0))
        tk.Label(satir, text="Ay:").pack(side="left")
        self.ay = ttk.Combobox(satir, values=[a[0] for a in AYLAR], width=4,
                               state="readonly")
        self.ay.set(str(date.today().month))
        self.ay.pack(side="left", padx=(2, 12))
        tk.Label(satir, text="Yıl:").pack(side="left")
        self.yil = ttk.Spinbox(satir, from_=2010, to=date.today().year + 1,
                               width=6)
        self.yil.set(date.today().year)
        self.yil.pack(side="left", padx=(2, 16))
        self.kayitli_muavin = tk.BooleanVar(value=True)
        ttk.Checkbutton(satir, text="Kayıtlı muavinleri otomatik kullan",
                        variable=self.kayitli_muavin).pack(side="left",
                                                           padx=(0, 10))
        self.durum = tk.Label(satir, text="", fg="#2563eb", wraplength=300,
                              justify="left")
        self.durum.pack(side="left", fill="x", expand=True)
        self.cek_butonu = tk.Button(satir, text="📥 Faturaları Çek ve Kontrol Et",
                                    font=("Segoe UI", 9, "bold"), relief="flat",
                                    bg="#2563eb", fg="#ffffff", padx=12, pady=4,
                                    cursor="hand2", command=self._cek_ve_kontrol)
        self.cek_butonu.pack(side="right")
        self.eksik_butonu = tk.Button(satir,
                                      text="🔍 Eksik Belge Bulucu",
                                      font=("Segoe UI", 9), relief="flat",
                                      bg="#64748b", fg="#ffffff", padx=10,
                                      pady=4, cursor="hand2",
                                      command=self._eksik_belge_kontrol)
        self.eksik_butonu.pack(side="right", padx=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._liste_yenile()

    # ---------- liste ve form ----------

    def _liste_yenile(self):
        self.mukellefler = mukellefler.yukle()
        self.liste.delete(*self.liste.get_children())
        for m in self.mukellefler:
            self.liste.insert("", "end", iid=m["id"],
                              values=(m.get("ad") or "(adsız)", m.get("vkn") or ""))

    def _secim_yukle(self):
        secim = self.liste.selection()
        if not secim:
            return
        self.secili_id = secim[0]
        m = next((x for x in self.mukellefler if x["id"] == self.secili_id), None)
        if not m:
            return
        cozulmus = mukellefler.coz_ve_getir(m)
        for anahtar, giris in self.alanlar.items():
            giris.delete(0, "end")
            giris.insert(0, str(cozulmus.get(anahtar) or ""))
        self.ent_kurum.set(cozulmus.get("ent_kurum") or "")

    def _form_degerleri(self):
        degerler = {anahtar: giris.get().strip()
                    for anahtar, giris in self.alanlar.items()}
        degerler["ent_kurum"] = self.ent_kurum.get().strip()
        return degerler

    def _yeni(self):
        self.secili_id = None
        for giris in self.alanlar.values():
            giris.delete(0, "end")
        self.ent_kurum.set("")
        self.liste.selection_remove(self.liste.selection())

    def _sil(self):
        if not self.secili_id:
            messagebox.showinfo("Bilgi", "Önce listeden bir mükellef seçin.",
                                parent=self)
            return
        if not messagebox.askyesno("Onay", "Seçili mükellefi silmek istiyor "
                                   "musunuz?", parent=self):
            return
        self.mukellefler = [m for m in self.mukellefler
                            if m["id"] != self.secili_id]
        mukellefler.kaydet(self.mukellefler)
        self._yeni()
        self._liste_yenile()

    def _kaydet(self):
        degerler = self._form_degerleri()
        if not degerler["ad"]:
            messagebox.showwarning("Uyarı", "Unvan / Ad zorunludur.",
                                   parent=self)
            return
        mevcut = next((m for m in self.mukellefler
                       if m["id"] == self.secili_id), None)
        kayit = mevcut or mukellefler.yeni_mukellef()
        kayit.update({
            "ad": degerler["ad"], "vkn": degerler["vkn"],
            "gib_tc": degerler["gib_tc"],
            "gib_sifre": mukellefler.sifrele(degerler["gib_sifre"]),
            "ivd_kod": degerler["ivd_kod"],
            "ivd_sifre": mukellefler.sifrele(degerler["ivd_sifre"]),
            "ent_kurum": degerler["ent_kurum"],
            "ent_kullanici": degerler["ent_kullanici"],
            "ent_sifre": mukellefler.sifrele(degerler["ent_sifre"]),
            "luca_uye": degerler["luca_uye"],
            "not": degerler["not"],
        })
        if not mevcut:
            self.mukellefler.append(kayit)
            self.secili_id = kayit["id"]
        mukellefler.kaydet(self.mukellefler)
        self._liste_yenile()
        if self.secili_id:
            children = self.liste.get_children()
            if self.secili_id in children:
                self.liste.selection_set(self.secili_id)
                self.liste.see(self.secili_id)

    # ---------- muavin hatirlama ----------

    def _secili_kayit(self, degerler):
        if self.secili_id:
            for m in self.mukellefler:
                if m["id"] == self.secili_id:
                    return m
        kimlik = degerler.get("vkn") or degerler.get("gib_tc")
        for m in self.mukellefler:
            if (degerler.get("vkn") and m.get("vkn") == degerler["vkn"]) or \
               (kimlik and (m.get("vkn") == kimlik
                            or m.get("gib_tc") == kimlik)):
                return m
        return None

    def _kayitli_cetveller(self, kayit, donem_anahtari):
        if not kayit:
            return []
        tumu = kayit.get("cetveller") or {}
        yollar = [y for y in (tumu.get(donem_anahtari) or [])
                  if os.path.exists(y)]
        return yollar

    def _cetvel_hatirla(self, kayit, donem_anahtari, yollar):
        """Seçilen muavin dosyalarını bu mükellef+dönem için saklar."""
        if not kayit:
            return
        try:
            tumu = dict(kayit.get("cetveller") or {})
            if yollar:
                tumu[donem_anahtari] = list(yollar)
            else:
                tumu.pop(donem_anahtari, None)
            kayit["cetveller"] = tumu
            mukellefler.kaydet(self.mukellefler)
        except Exception:
            pass

    # ---------- otomatik cekim ----------

    def _durum_yaz(self, metin):
        self.durum.configure(text=metin)

    def _logla(self, metin):
        try:
            self.uygulama.kok.after(0, lambda m=metin: self.uygulama._log_yaz(m))
            self.after(0, lambda m=metin: self._durum_yaz(m))
        except Exception:
            pass

    def _cek_ve_kontrol(self):
        if getattr(self.uygulama, "_islem_devam", False):
            messagebox.showwarning("Uyarı", "Devam eden bir işlem var, "
                                   "lütfen bekleyin.", parent=self)
            return
        degerler = self._form_degerleri()
        if not degerler["gib_tc"] or not degerler["gib_sifre"]:
            messagebox.showwarning(
                "Uyarı", "GİB (DVD) kullanıcı ve şifre alanlarını doldurun.",
                parent=self)
            return
        try:
            ay = int(self.ay.get())
            yil = int(self.yil.get())
        except ValueError:
            messagebox.showwarning("Uyarı", "Ay/Yıl geçersiz.", parent=self)
            return
        bas = date(yil, ay, 1)
        bit = date(yil, ay, calendar.monthrange(yil, ay)[1])
        bugun = date.today()
        sinir = date(bugun.year, bugun.month, 1)
        for _ in range(2):
            onceki_yil = sinir.year - (sinir.month == 1)
            onceki_ay = 12 if sinir.month == 1 else sinir.month - 1
            sinir = date(onceki_yil, onceki_ay, 1)
        if bit < sinir:
            devam = messagebox.askyesno(
                "Uyarı", "Seçilen dönem GİB'in 'son 2 ay' sınırının dışında;\n"
                "sorgu büyük olasılıkla boş döner. Yine de denensin mi?",
                parent=self)
            if not devam:
                return
        if not gib_cekme.internet_var_mi():
            messagebox.showerror("Hata", "İnternet bağlantısı yok veya GİB'e "
                                 "erişilemiyor.", parent=self)
            return

        kimlik = degerler["vkn"] or degerler["gib_tc"]
        hedef_klasor = mukellefler.coz_klasor(kimlik, yil, ay)
        kayit = self._secili_kayit(degerler)
        donem = f"{yil}-{ay:02d}"

        luca_planli = (degerler.get("ent_kurum") == "Luca / Türmob"
                       and degerler.get("luca_uye")
                       and degerler.get("ent_kullanici")
                       and degerler.get("ent_sifre"))
        if degerler.get("ent_kurum") == "Luca / Türmob" and not luca_planli:
            messagebox.showinfo(
                "Bilgi", "Entegratör 'Luca / Türmob' seçili ancak Luca Üye "
                "Numarası / Kullanıcı / Şifre eksik.\nMuavin dosyalarını elle "
                "seçerek devam edebilirsiniz.", parent=self)

        muavin_klasoru = os.path.join(hedef_klasor, "muavin")
        cetvel_dosyalari = []
        if not luca_planli:
            if self.kayitli_muavin.get():
                cetvel_dosyalari = self._kayitli_cetveller(kayit, donem)
            if not cetvel_dosyalari:
                cetvel_dosyalari = list(filedialog.askopenfilenames(
                    parent=self,
                    title="Muavin cetvel dosyalarını seçin (191 / 391)",
                    filetypes=[("Desteklenen dosyalar",
                                "*.pdf *.xlsx *.xlsm *.xls"),
                               ("Tüm dosyalar", "*.*")]))
                if not cetvel_dosyalari:
                    return
                self._cetvel_hatirla(kayit, donem, cetvel_dosyalari)

        ozet = ", ".join(os.path.basename(y) for y in cetvel_dosyalari[:2])
        ekstra = f" ve {len(cetvel_dosyalari) - 2} dosya daha" \
            if len(cetvel_dosyalari) > 2 else ""
        mesaj = (f"{degerler['ad']} ({bas.strftime('%m.%Y')}) için e-Arşiv "
                 "alış faturaları GİB'den indirilecek.\n\n"
                 + ("Muavin Luca'dan otomatik çekilecek.\n" if luca_planli
                    else f"Kullanılacak cetveller: {ozet}{ekstra}\n")
                 + "\nÇapraz kontrol otomatik başlayacak. Devam edilsin mi?")
        if not messagebox.askyesno("Onay", mesaj, parent=self):
            return

        self.cek_butonu.configure(state="disabled", bg="#64748b")
        self._durum_yaz("GİB'e bağlanılıyor...")

        def is_parcasi():
            try:
                kullanilacak = list(cetvel_dosyalari)
                luca_yedek = []
                if luca_planli:
                    self._logla(f"Luca'ya giriş yapılıyor "
                                f"(üye {degerler.get('luca_uye')})...")
                    try:
                        indirilen = luca_cekme.cek_muavin(
                            degerler["luca_uye"], degerler["ent_kullanici"],
                            degerler["ent_sifre"], bas, bit, muavin_klasoru,
                            firma_adi=degerler.get("ad", ""),
                            ilerleme=self._logla)
                        kullanilacak = indirilen
                        self.after(0, lambda k=kayit, y=list(indirilen):
                                   self._cetvel_hatirla(k, donem, y))
                    except luca_cekme.LucaHata as lhata:
                        yedek = self._kayitli_cetveller(kayit, donem)
                        if yedek:
                            kullanilacak = yedek
                            self._logla(f"Luca hatası: {str(lhata)[:80]} — "
                                        "kayıtlı muavinlerle devam ediliyor.")
                        else:
                            self.after(0, lambda h="Luca muavin çekimi "
                                       f"başarısız: {lhata}": self._cek_hata(h))
                            return
                    # Luca'dan e-Belgeler (e-Fatura/e-Arşiv ALIŞ) da
                    # indirilir; GİB çekimi başarısız olursa yedek olur.
                    try:
                        belge_sonuc = luca_cekme.cek_luca_belgeleri(
                            degerler["luca_uye"], degerler["ent_kullanici"],
                            degerler["ent_sifre"], bas, bit, hedef_klasor,
                            kategoriler=("earsiv_alis", "efatura_alis"),
                            ilerleme=self._logla,
                            firma_adi=degerler.get("ad", ""))
                        luca_ozetler = [v.get("ozet") for v in
                                        (belge_sonuc or {}).values()
                                        if v.get("ozet")]
                        if luca_ozetler:
                            self._logla(f"Luca'dan {len(luca_ozetler)} "
                                        "belge kümesi indirildi.")
                            luca_yedek.extend(luca_ozetler)
                    except luca_cekme.LucaHata as bhata:
                        self._logla(f"Luca belge çekimi atlandı: "
                                    f"{str(bhata)[:80]}")
                try:
                    yollar = gib_cekme.cek_e_arsiv_alis(
                        degerler["gib_tc"], degerler["gib_sifre"], bas, bit,
                        hedef_klasor, ilerleme=self._logla,
                        ivd_kod=degerler.get("ivd_kod"),
                        ivd_sifre=degerler.get("ivd_sifre"))
                except gib_cekme.GibHata as ghata:
                    if luca_yedek:
                        yollar = list(luca_yedek)
                        self._logla(f"GİB çekimi başarısız "
                                    f"({str(ghata)[:60]}) — Luca'dan "
                                    f"indirilen {len(yollar)} belge kümesi "
                                    "kullanılıyor.")
                    else:
                        raise
            except gib_cekme.GibHata as hata:
                self.after(0, lambda h=str(hata): self._cek_hata(h))
                return
            except Exception as hata:
                self.after(0, lambda h=f"Beklenmeyen hata: {hata}":
                           self._cek_hata(h))
                return
            self.after(0, lambda y=yollar, c=kullanilacak:
                       self._cek_bitti(y, c))
            # Uçtan uca akış: çapraz kontrol bitince eksik belge
            # bulucu otomatik koşar.
            self.after(0, lambda: getattr(self.uygulama,
                        "kontrol_sonu_gorevleri", []).append(
                        self._eksik_belge_otomatik))

        threading.Thread(target=is_parcasi, daemon=True).start()

    def _eksik_belge_kontrol(self):
        degerler = self._form_degerleri()
        try:
            ay = int(self.ay.get())
            yil = int(self.yil.get())
        except ValueError:
            messagebox.showwarning("Uyarı", "Ay/Yıl geçersiz.", parent=self)
            return
        kimlik = degerler["vkn"] or degerler["gib_tc"]
        if not kimlik:
            messagebox.showwarning(
                "Uyarı", "Mükellef seçin veya VKN/TC alanını doldurun.",
                parent=self)
            return
        klasor = mukellefler.coz_klasor(kimlik, yil, ay)
        fatura_onekleri = ("earsiv_alis", "luca_efatura_alis",
                           "luca_earsiv_alis")
        fatura_dosyalari = sorted(
            os.path.join(klasor, ad) for ad in os.listdir(klasor)
            if ad.lower().startswith(fatura_onekleri)
            and ad.lower().endswith(".xlsx")) \
            if os.path.isdir(klasor) else []
        if not fatura_dosyalari:
            messagebox.showinfo(
                "Bilgi",
                f"{klasor} altında indirilmiş e-Arşiv dosyası yok.\n"
                "Önce 'Faturaları Çek ve Kontrol Et' çalıştırın.",
                parent=self)
            return
        kayit = self._secili_kayit(degerler)
        donem = f"{yil}-{ay:02d}"
        cetvel_dosyalari = (self.kayitli_muavin.get()
                            and self._kayitli_cetveller(kayit, donem)) or []
        if not cetvel_dosyalari:
            cetvel_dosyalari = list(filedialog.askopenfilenames(
                parent=self,
                title="Muavin cetvel dosyalarını seçin (191 / 391)",
                filetypes=[("Desteklenen dosyalar",
                            "*.pdf *.xlsx *.xlsm *.xls"),
                           ("Tüm dosyalar", "*.*")]))
            if not cetvel_dosyalari:
                return

        import excel_oku
        import eksik_belge
        import eksik_belge_pencere
        fatura_kayitlari = []
        for d in fatura_dosyalari:
            try:
                kayitlar = excel_oku.fatura_luca_ozet_parse(d) or []
            except Exception:
                kayitlar = []
            if not kayitlar:
                try:
                    kayitlar = \
                        excel_oku.fatura_gib_arsiv_liste_parse(d) or []
                except Exception:
                    kayitlar = []
            if not kayitlar:
                try:
                    genel = excel_oku.muavin_genel_parse(d)
                    kayitlar = [k for k in (genel.get("kayitlar") or [])
                                if k.get("kdv") is not None]
                    for k in kayitlar:
                        k.setdefault("satici_vkn", k.get("vkn") or "")
                except Exception:
                    kayitlar = []
            fatura_kayitlari.extend(kayitlar)
        cetvel_kayitlari = []
        for d in cetvel_dosyalari:
            sonuc_d = excel_oku.muavin_genel_parse(d)
            cetvel_kayitlari.extend(sonuc_d.get("kayitlar") or [])
        if not cetvel_kayitlari:
            messagebox.showwarning(
                "Uyarı", "Cetvel dosyalarından satır okunamadı.",
                parent=self)
            return
        sonuc = eksik_belge.eslestir(cetvel_kayitlari, fatura_kayitlari)
        eksik_belge_pencere.ac(self, sonuc, cetvel_kayitlari,
                               fatura_kayitlari)

    def _eksik_belge_otomatik(self):
        """Çekim + çapraz kontrol sonrası sessizce çalışır: indirilen
        e-Arşiv dosyalarıyla kayıtlı muavin cetvellerini eşleştirip
        sonuç penceresini açar. Hata olursa sadece loglar."""
        try:
            degerler = self._form_degerleri()
            ay = int(self.ay.get())
            yil = int(self.yil.get())
        except Exception:
            return
        kimlik = degerler.get("vkn") or degerler.get("gib_tc")
        if not kimlik:
            return
        klasor = mukellefler.coz_klasor(kimlik, yil, ay)
        fatura_onekleri = ("earsiv_alis", "luca_efatura_alis",
                           "luca_earsiv_alis")
        fatura_dosyalari = sorted(
            os.path.join(klasor, ad) for ad in os.listdir(klasor)
            if ad.lower().startswith(fatura_onekleri)
            and ad.lower().endswith(".xlsx")) \
            if os.path.isdir(klasor) else []
        kayit = self._secili_kayit(degerler)
        donem = f"{yil}-{ay:02d}"
        cetvel_dosyalari = self._kayitli_cetveller(kayit, donem)
        if not fatura_dosyalari or not cetvel_dosyalari:
            return
        try:
            import excel_oku
            import eksik_belge
            fatura_kayitlari = []
            for d in fatura_dosyalari:
                kayitlar = []
                for okuyucu in (excel_oku.fatura_luca_ozet_parse,
                                excel_oku.fatura_gib_arsiv_liste_parse):
                    try:
                        kayitlar = okuyucu(d) or []
                    except Exception:
                        kayitlar = []
                    if kayitlar:
                        break
                if not kayitlar:
                    try:
                        genel = excel_oku.muavin_genel_parse(d)
                        kayitlar = [k for k in
                                    (genel.get("kayitlar") or [])
                                    if k.get("kdv") is not None]
                        for k in kayitlar:
                            k.setdefault("satici_vkn", k.get("vkn") or "")
                    except Exception:
                        kayitlar = []
                fatura_kayitlari.extend(kayitlar)
            cetvel_kayitlari = []
            for d in cetvel_dosyalari:
                sonuc_d = excel_oku.muavin_genel_parse(d)
                cetvel_kayitlari.extend(sonuc_d.get("kayitlar") or [])
            if not cetvel_kayitlari or not fatura_kayitlari:
                return
            sonuc = eksik_belge.eslestir(cetvel_kayitlari,
                                         fatura_kayitlari)
            kritik = len(sonuc.get("cetvelde_var_faturasi_yok") or [])
            self._logla(f"Eksik belge taraması: {kritik} kayıt için "
                        "fatura bulunamadı." if kritik else
                        "Eksik belge taraması tamamlandı.")
            import eksik_belge_pencere
            eksik_belge_pencere.ac(self, sonuc, cetvel_kayitlari,
                                   fatura_kayitlari)
        except Exception as hata:
            self._logla(f"Eksik belge taraması atlandı: {str(hata)[:100]}")

    def _cek_hata(self, mesaj):
        self.cek_butonu.configure(state="normal", bg="#2563eb")
        self._durum_yaz("Hata: " + mesaj[:120])
        messagebox.showerror("GİB Çekim Hatası", mesaj, parent=self)

    def _cek_bitti(self, yollar, cetvel_dosyalari):
        self.cek_butonu.configure(state="normal", bg="#2563eb")
        self._durum_yaz(f"{len(yollar)} dosya indirildi, kontrol başlıyor...")
        self.uygulama.fatura_dosyalari = yollar
        self.uygulama.cetvel_dosyalari = cetvel_dosyalari
        if getattr(self.uygulama, "ayarlar", None):
            try:
                self.uygulama.ayarlar.toplu_kaydet(
                    son_faturalar=yollar, son_cetveller=cetvel_dosyalari)
            except Exception:
                pass
        self.uygulama._dosya_etiketi_guncelle()
        self.uygulama.kontrol_baslat()
