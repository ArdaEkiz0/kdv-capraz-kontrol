import os
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, simpledialog, ttk

from ayarlar import ayarlar_al
from cetvel import cetvel_parse
from dashboard import DashboardFrame
from db import db_al
from dosya import cetvel_dosya_parse, fatura_dosya_parse
from efatura import efatura_parse
from email_gonder import mail_icerigi_olustur, outlook_ile_gonder, smtp_ile_gonder
from fatura_detay_pencere import FaturaDetayPencere
from filtre_dialog import GelismisFiltreDialog, filtre_uygula
from iade_ayristirici import iade_ayristirici_ozet
from matcher import (DURUM_CETVELDE_YOK, DURUM_FATURADA_YOK, DURUM_MUKERRER,
                     DURUM_OK, DURUM_PARSE_SORUNU, DURUM_TUTAR_FARKI,
                     DURUM_VKN_FARKI, SORUNLU_DURUMLAR, capraz_kontrol,
                     capraz_kontrol_iade_destekli)
from muavin_coklu import cetvel_klasor_dialog
from muhtasar_ba_formu import ba_formu_olustur
from report import rapor_olustur
from report_pdf import rapor_pdf_olustur
from utils import tl_format

DESTEKLENEN_DOSYALAR = [("Desteklenen Dosyalar", "*.pdf *.xlsx *.xlsm *.xls *.xml"),
                        ("PDF Dosyaları", "*.pdf"),
                        ("Excel Dosyaları", "*.xlsx *.xlsm *.xls"),
                        ("XML Dosyaları", "*.xml")]

DURUM_RENKLER = {
    DURUM_OK: "#C6EFCE",
    DURUM_TUTAR_FARKI: "#FFC7CE",
    DURUM_VKN_FARKI: "#FFEB9C",
    DURUM_MUKERRER: "#FFEB9C",
    DURUM_CETVELDE_YOK: "#FFC7CE",
    DURUM_FATURADA_YOK: "#FFC7CE",
    DURUM_PARSE_SORUNU: "#FFC7CE",
}

KOLONLAR = ("durum", "belge_no", "vkn", "tarih", "matrah", "kdv", "kaynak", "detay")
BASLIKLAR = {
    "durum": "Durum", "belge_no": "Belge No", "vkn": "VKN", "tarih": "Tarih",
    "matrah": "Matrah", "kdv": "KDV", "kaynak": "Kaynak", "detay": "Detay",
}


class KdvKontrolApp:
    def __init__(self, kok):
        self.kok = kok
        kok.title("KDV Çapraz Kontrol | Geliştirici: Arda M. Ekiz")
        kok.geometry("1280x780")
        kok.minsize(1000, 600)

        self.fatura_dosyalari = []
        self.cetvel_dosyalari = []
        self.sonuc_satirlari = []
        self.ozet = None
        self.faturalar = []
        self.cetvel_kayitlari = []
        self.filtre = "Tumu"
        self.aktif_filtre = None

        try:
            self.db = db_al()
        except Exception as hata:
            self.db = None
            print(f"DB bağlanamadı: {hata}")

        try:
            self.ayarlar = ayarlar_al()
            boyut = self.ayarlar.al("pencere_boyut", "1280x780")
            kok.geometry(boyut)
            self.son_faturalar = self.ayarlar.al("son_faturalar", [])
            self.son_cetveller = self.ayarlar.al("son_cetveller", [])
        except Exception as hata:
            self.ayarlar = None
            print(f"Ayarlar yüklenemedi: {hata}")

        self._arayuz_kur()

    def _arayuz_kur(self):
        bilgi = ttk.Label(
            self.kok,
            text=("Kullanım: 1) Fatura dosyalarını seçin (e-fatura XML/PDF veya Excel)  2) KDV kontrol cetvelini seçin   "
                  "3) 'Kontrolü Başlat' ile çapraz kontrol yapın  4) Excel raporunu kaydedin"),
            background="#DDEBF7", padding=8, anchor="w",
        )
        bilgi.pack(fill="x")

        ust = ttk.Frame(self.kok, padding=(8, 6))
        ust.pack(fill="x")

        ttk.Button(ust, text="Fatura Dosyaları Seç", command=self.fatura_sec).pack(side="left", padx=(0, 6))
        ttk.Button(ust, text="Fatura Klasörü Seç", command=self.fatura_klasoru_sec).pack(side="left", padx=(0, 6))
        ttk.Button(ust, text="Kontrol Cetveli Seç", command=self.cetvel_sec).pack(side="left", padx=(0, 6))
        ttk.Button(ust, text="Kontrolü Başlat", command=self.kontrol_baslat).pack(side="left", padx=(0, 6))
        ttk.Button(ust, text="📊 Dashboard", command=self.dashboard_goster).pack(side="left", padx=(0, 6))
        ttk.Button(ust, text="🔎 Gelişmiş Filtre", command=self.gelismis_filtre_ac).pack(side="left", padx=(0, 6))
        ttk.Button(ust, text="📂 Klasör Cetvel", command=self.cetvel_klasor_ac).pack(side="left", padx=(0, 6))
        ttk.Button(ust, text="Excel Raporunu Kaydet", command=self.rapor_kaydet).pack(side="left", padx=(0, 6))
        ttk.Button(ust, text="PDF Raporunu Kaydet", command=self.rapor_pdf_kaydet).pack(side="left", padx=(0, 6))
        ttk.Button(ust, text="📊 Ba/Bs Formu", command=self.muhtasar_kaydet).pack(side="left", padx=(0, 6))
        ttk.Button(ust, text="📧 Mail Gönder", command=self.mail_gonder_ac).pack(side="left", padx=(0, 6))
        ttk.Button(ust, text="ℹ️ Hakkında", command=self.hakkinda_pencere_ac).pack(side="left", padx=(0, 6))

        self.dosya_etiketi = ttk.Label(ust, text="Fatura: (seçilmedi) | Cetvel: (seçilmedi)")
        self.dosya_etiketi.pack(side="left", padx=(12, 0))

        filtre = ttk.Frame(self.kok, padding=(8, 0))
        filtre.pack(fill="x")
        self.filtre_degisken = tk.StringVar(value="Tumu")
        for metin, deger in [("Tümü", "Tumu"), ("Sorunlu", "Sorunlu"), ("Eşleşen", "Eslenen")]:
            ttk.Radiobutton(filtre, text=metin, value=deger, variable=self.filtre_degisken,
                            command=self._filtre_uygula).pack(side="left", padx=(0, 10))

        tablo_kapsayici = ttk.Frame(self.kok, padding=(8, 6))
        tablo_kapsayici.pack(fill="both", expand=True)

        self.tablo = ttk.Treeview(tablo_kapsayici, columns=KOLONLAR, show="headings", height=18)
        for kolon in KOLONLAR:
            self.tablo.heading(kolon, text=BASLIKLAR[kolon])
            genislik = {"durum": 110, "belge_no": 180, "vkn": 110, "tarih": 90,
                        "matrah": 90, "kdv": 90, "kaynak": 60, "detay": 420}[kolon]
            self.tablo.column(kolon, width=genislik, anchor="w" if kolon in ("detay", "belge_no") else "center")

        self.tablo.bind("<Double-1>", self._satir_detay_goster)

        kaydirma_y = ttk.Scrollbar(tablo_kapsayici, orient="vertical", command=self.tablo.yview)
        kaydirma_x = ttk.Scrollbar(tablo_kapsayici, orient="horizontal", command=self.tablo.xview)
        self.tablo.configure(yscrollcommand=kaydirma_y.set, xscrollcommand=kaydirma_x.set)
        self.tablo.grid(row=0, column=0, sticky="nsew")
        kaydirma_y.grid(row=0, column=1, sticky="ns")
        kaydirma_x.grid(row=1, column=0, sticky="ew")
        tablo_kapsayici.rowconfigure(0, weight=1)
        tablo_kapsayici.columnconfigure(0, weight=1)

        self.ozet_etiketi = ttk.Label(self.kok, text="", padding=(8, 4))
        self.ozet_etiketi.pack(fill="x")

        log_kapsayici = ttk.Frame(self.kok, padding=(8, 0))
        log_kapsayici.pack(fill="x", side="bottom")
        self.log = tk.Text(log_kapsayici, height=5, state="disabled", wrap="word")
        log_kaydirma = ttk.Scrollbar(log_kapsayici, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=log_kaydirma.set)
        self.log.pack(side="left", fill="x", expand=True)
        log_kaydirma.pack(side="right", fill="y")

    def _log_yaz(self, metin):
        self.log.configure(state="normal")
        self.log.insert("end", metin + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def fatura_sec(self):
        dosyalar = filedialog.askopenfilenames(
            title="Fatura Dosyalarını Seçin (XML, PDF veya Excel)", filetypes=DESTEKLENEN_DOSYALAR)
        if dosyalar:
            self.fatura_dosyalari = list(dosyalar)
            if self.ayarlar:
                self.ayarlar.toplu_kaydet(son_faturalar=self.fatura_dosyalari)
            self._dosya_etiketi_guncelle()

    def fatura_klasoru_sec(self):
        klasor = filedialog.askdirectory(title="Faturaların Bulunduğu Klasörü Seçin")
        if klasor:
            dosyalar = []
            uzantilar = (".pdf", ".xlsx", ".xlsm", ".xls", ".xml")
            for kok, _, dosyalar_alt in os.walk(klasor):
                for dosya in dosyalar_alt:
                    if dosya.lower().endswith(uzantilar):
                        dosyalar.append(os.path.join(kok, dosya))
            if not dosyalar:
                messagebox.showwarning("Uyarı", "Klasörde PDF, Excel veya XML dosyası bulunamadı.")
                return
            self.fatura_dosyalari = dosyalar
            if self.ayarlar:
                self.ayarlar.toplu_kaydet(son_faturalar=self.fatura_dosyalari,
                                           son_fatura_klasor=klasor)
            self._dosya_etiketi_guncelle()

    def cetvel_sec(self):
        dosyalar = filedialog.askopenfilenames(
            title="KDV Kontrol Cetveli Dosyalarını Seçin (PDF veya Excel)", filetypes=DESTEKLENEN_DOSYALAR)
        if dosyalar:
            self.cetvel_dosyalari = list(dosyalar)
            if self.ayarlar:
                self.ayarlar.toplu_kaydet(son_cetveller=self.cetvel_dosyalari)
            self._dosya_etiketi_guncelle()

    def cetvel_klasor_ac(self):
        dosyalar = cetvel_klasor_dialog(self.kok)
        if dosyalar:
            self.cetvel_dosyalari = list(dosyalar)
            if self.ayarlar:
                self.ayarlar.toplu_kaydet(
                    son_cetveller=self.cetvel_dosyalari,
                    son_cetvel_klasor=os.path.dirname(dosyalar[0]),
                )
            self._dosya_etiketi_guncelle()
            self._log_yaz(f"Klasörden {len(dosyalar)} cetvel/muavin dosyası eklendi")

    def _dosya_etiketi_guncelle(self):
        f_metin = f"{len(self.fatura_dosyalari)} dosya" if self.fatura_dosyalari else "(seçilmedi)"
        c_metin = f"{len(self.cetvel_dosyalari)} dosya" if self.cetvel_dosyalari else "(seçilmedi)"
        self.dosya_etiketi.configure(text=f"Fatura: {f_metin} | Cetvel: {c_metin}")

    def kontrol_baslat(self):
        if not self.fatura_dosyalari and not self.cetvel_dosyalari:
            messagebox.showwarning("Uyarı", "Önce fatura ve/veya cetvel dosyalarını seçin.")
            return
        self.kok.configure(cursor="watch")
        self.kok.update_idletasks()
        try:
            self.faturalar = []
            self.cetvel_kayitlari = []
            for i, dosya in enumerate(self.fatura_dosyalari, start=1):
                faturalar = fatura_dosya_parse(dosya)
                self.faturalar.extend(faturalar)
                self.kok.update_idletasks()
            for dosya in self.cetvel_dosyalari:
                c = cetvel_dosya_parse(dosya)
                self.cetvel_kayitlari.extend(c["kayitlar"])
                if c["notlar"]:
                    self._log_yaz(f"[Cetvel] {os.path.basename(dosya)}: {'; '.join(c['notlar'])}")

            self.sonuc_satirlari, self.ozet = capraz_kontrol_iade_destekli(
                self.faturalar, self.cetvel_kayitlari
            )
            self.aktif_filtre = None
            self._filtre_uygula()
            self._ozet_guncelle()
            self._parse_sorunlarini_bildir()
            self._db_kaydet()
            self._log_yaz(f"Kontrol tamamlandı: {len(self.faturalar)} fatura, {len(self.cetvel_kayitlari)} cetvel satırı, "
                          f"{len(self.sonuc_satirlari)} sonuç satırı.")
            if self.ozet.get("iade_adet", 0):
                self._log_yaz(f"İade faturası: {self.ozet['iade_adet']} adet, toplam KDV: {tl_format(self.ozet.get('iade_kdv_toplam'))} TL")
        finally:
            self.kok.configure(cursor="")

    def _satir_detay_goster(self, event):
        secili = self.tablo.selection()
        if not secili:
            return
        degerler = self.tablo.item(secili[0])["values"]
        if not degerler or len(degerler) < 2:
            return
        belge_no = degerler[1]
        if not belge_no:
            return

        sonuc = next((r for r in self.sonuc_satirlari if r["belge_no"] == belge_no), None)
        fatura = next((f for f in self.faturalar if f.get("belge_no") == belge_no), None)
        if not sonuc or not fatura:
            messagebox.showinfo("Bilgi", "Bu kayıt için detay bulunamadı.")
            return

        FaturaDetayPencere(self.kok, fatura, sonuc)

    def _db_kaydet(self):
        if not self.db or not self.ozet:
            return
        try:
            eksik_belgeler = [
                {
                    "belge_no": r["belge_no"],
                    "vkn": r["vkn"],
                    "unvan": r["unvan"],
                    "kdv": r["kdv"],
                    "tarih": r["tarih"],
                }
                for r in self.sonuc_satirlari
                if r["durum"] == DURUM_CETVELDE_YOK
            ]
            donem = ""
            tarihler = [r.get("tarih") for r in self.sonuc_satirlari if r.get("tarih")]
            if tarihler:
                donem = tarihler[0][:7]

            kontrol_id = self.db.kontrol_kaydet(self.ozet, eksik_belgeler, donem)
            self._log_yaz(f"Veritabanına kaydedildi (kontrol #{kontrol_id})")
        except Exception as hata:
            self._log_yaz(f"DB kayıt hatası: {hata}")

    def _fatura_adi(self, f):
        ad = os.path.basename(f["dosya"])
        if f.get("tip") == "excel" and f.get("satir"):
            return f"{ad} (satır {f['satir']})"
        if f.get("sayfa") and f["sayfa"] > 1:
            return f"{ad} (sayfa {f['sayfa']})"
        return ad

    def _parse_sorunlarini_bildir(self):
        for f in self.faturalar:
            if f["notlar"]:
                self._log_yaz(f"[Fatura] {self._fatura_adi(f)}: {'; '.join(f['notlar'])}")

    def _ozet_guncelle(self):
        if not self.ozet:
            return
        o = self.ozet
        metin = (f"Fatura: {o['fatura_adet']}  |  Cetvel: {o['cetvel_adet']}  |  Eşleşen: {o['eslesen']}  |  "
                 f"Tutar Farkı: {o['tutar_farki']}  |  VKN Farkı: {o['vkn_farki']}  |  Cetvelde Yok: {o['cetvelde_yok']}  |  "
                 f"Faturalarda Yok: {o['faturada_yok']}  |  Mükerrer: {o['mukerrer']}  |  Okunamayan: {o['parse_sorunu']}")
        iade_metin = ""
        if o.get("iade_adet", 0):
            iade_metin = f"  |  İade: {o['iade_adet']}"
        self.ozet_etiketi.configure(
            text=metin + iade_metin,
            foreground="#B00000" if o["cetvelde_yok"] + o["faturada_yok"] + o["tutar_farki"] else "#006100",
        )

    def _filtre_uygula(self):
        secim = self.filtre_degisken.get()
        self.tablo.delete(*self.tablo.get_children())

        satirlar = []
        for satir in self.sonuc_satirlari:
            if secim == "Sorunlu" and satir["durum"] not in SORUNLU_DURUMLAR:
                continue
            if secim == "Eslenen" and satir["durum"] != DURUM_OK:
                continue
            satirlar.append(satir)

        if self.aktif_filtre:
            satirlar = filtre_uygula(satirlar, self.aktif_filtre)

        for satir in satirlar:
            tag = satir["durum"]
            self.tablo.insert("", "end", tags=(tag,), values=(
                satir["durum"],
                satir["belge_no"] or "",
                satir["vkn"] or "",
                satir["tarih"] or "",
                tl_format(satir["matrah"]),
                tl_format(satir["kdv"]),
                satir["kaynak"] or "",
                satir["detay"] or "",
            ))
        for durum, renk in DURUM_RENKLER.items():
            self.tablo.tag_configure(durum, background=renk)

    def dashboard_goster(self):
        if not self.ozet:
            messagebox.showwarning("Uyarı", "Önce kontrol çalıştırın.")
            return
        pencere = tk.Toplevel(self.kok)
        pencere.title("📊 Dashboard")
        pencere.geometry("1100x550")
        DashboardFrame(
            pencere, self.ozet, self.faturalar,
            self.cetvel_kayitlari, self.sonuc_satirlari,
            db=self.db,
        ).pack(fill="both", expand=True)

    def gelismis_filtre_ac(self):
        if not self.sonuc_satirlari:
            messagebox.showwarning("Uyarı", "Önce kontrol çalıştırın.")
            return
        GelismisFiltreDialog(
            self.kok, self.sonuc_satirlari, self._gelismis_filtre_uygula
        )

    def _gelismis_filtre_uygula(self, filtre):
        self.aktif_filtre = filtre
        self._filtre_uygula()
        ozet = []
        if filtre.get("tarih_baslangic"):
            ozet.append(f"📅 {filtre['tarih_baslangic'].strftime('%d.%m.%Y')}")
        if filtre.get("tarih_bitis"):
            ozet.append(f"→ {filtre['tarih_bitis'].strftime('%d.%m.%Y')}")
        if filtre.get("vkn"):
            ozet.append(f"VKN:{filtre['vkn']}")
        if filtre.get("min_tutar") is not None:
            ozet.append(f"Min:{filtre['min_tutar']}₺")
        if filtre.get("max_tutar") is not None:
            ozet.append(f"Max:{filtre['max_tutar']}₺")
        if filtre.get("durumlar"):
            ozet.append(f"Durum:{len(filtre['durumlar'])} seçili")
        filtre_acik = " | ".join(ozet) if ozet else "tümü"
        self._log_yaz(f"Gelişmiş filtre aktif: {filtre_acik}")

    def muhtasar_kaydet(self):
        if not self.faturalar:
            messagebox.showwarning("Uyarı", "Önce kontrol çalıştırın.")
            return
        varsayilan = f"KDV_BaBs_Formu_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        hedef = filedialog.asksaveasfilename(
            title="Ba/Bs Formu Kaydet",
            defaultextension=".xlsx",
            initialfile=varsayilan,
            filetypes=[("Excel Dosyası", "*.xlsx")],
        )
        if not hedef:
            return
        try:
            donem = ""
            tarihler = [f.get("tarih") for f in self.faturalar if f.get("tarih")]
            if tarihler:
                donem = tarihler[0][:7]
            ba_formu_olustur(self.faturalar, self.cetvel_kayitlari, hedef, donem)
            messagebox.showinfo("Başarılı", f"Ba/Bs formu kaydedildi:\n{hedef}")
            self._log_yaz(f"Ba/Bs formu: {hedef}")
        except Exception as hata:
            messagebox.showerror("Hata", f"Form oluşturulamadı:\n{hata}")

    def mail_gonder_ac(self):
        """Mail gönder."""
        if not self.sonuc_satirlari:
            messagebox.showwarning("Uyarı", "Önce kontrol çalıştırın.")
            return

        alici = ""
        if self.ayarlar:
            alici = self.ayarlar.al("email_alici", "")
        if not alici:
            alici = simpledialog.askstring("Alıcı", "Alıcı e-posta adresi:", parent=self.kok)
            if not alici:
                return
            if self.ayarlar:
                self.ayarlar.kaydet("email_alici", alici)

        ekler = []
        if self.sonuc_satirlari and self.ozet:
            try:
                import tempfile
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                tmp_xlsx = os.path.join(tempfile.gettempdir(), f"KDV_Rapor_{ts}.xlsx")
                tmp_pdf = os.path.join(tempfile.gettempdir(), f"KDV_Rapor_{ts}.pdf")
                rapor_olustur(self.sonuc_satirlari, self.ozet, self.faturalar,
                              self.cetvel_kayitlari, tmp_xlsx)
                ekler.append(tmp_xlsx)
                try:
                    rapor_pdf_olustur(self.sonuc_satirlari, self.ozet, self.faturalar,
                                      self.cetvel_kayitlari, tmp_pdf)
                    ekler.append(tmp_pdf)
                except Exception:
                    pass
            except Exception as hata:
                self._log_yaz(f"Rapor oluşturma hatası: {hata}")

        donem = ""
        tarihler = [r.get("tarih") for r in self.sonuc_satirlari if r.get("tarih")]
        if tarihler:
            donem = tarihler[0][:7]

        konu, html, text = mail_icerigi_olustur(self.ozet, donem)

        if outlook_ile_gonder(ekler, konu, html, alici):
            self._log_yaz(f"Outlook açıldı, mail hazır: {alici}")
            messagebox.showinfo("Bilgi", "Outlook'ta mail penceresi açıldı. Gönder'e basın.")
            return

        smtp_server = "smtp.gmail.com"
        smtp_user = ""
        smtp_pass = ""
        if self.ayarlar:
            smtp_server = self.ayarlar.al("smtp_server", "smtp.gmail.com")
            smtp_user = self.ayarlar.al("smtp_user", "")
            smtp_pass = self.ayarlar.al("smtp_pass", "")

        if not smtp_user:
            if messagebox.askyesno("SMTP Kurulumu", "Outlook bulunamadı. SMTP ayarlarını girmek ister misiniz?"):
                smtp_server = simpledialog.askstring("SMTP Sunucu", "SMTP sunucu:", initialvalue="smtp.gmail.com", parent=self.kok) or "smtp.gmail.com"
                smtp_user = simpledialog.askstring("SMTP Kullanıcı", "E-posta:", parent=self.kok) or ""
                smtp_pass = simpledialog.askstring("SMTP Şifre", "Şifre (uygulama şifresi):", show="*", parent=self.kok) or ""
                if smtp_user and smtp_pass and self.ayarlar:
                    self.ayarlar.toplu_kaydet(smtp_server=smtp_server, smtp_user=smtp_user, smtp_pass=smtp_pass)

        if smtp_user and smtp_pass:
            basarili, mesaj = smtp_ile_gonder(ekler, konu, html, alici, smtp_server, 587, smtp_user, smtp_pass)
            if basarili:
                messagebox.showinfo("Başarılı", "Mail gönderildi!")
                self._log_yaz(f"Mail gönderildi: {alici}")
            else:
                messagebox.showerror("Hata", f"Mail gönderilemedi: {mesaj}")

    def hakkinda_pencere_ac(self):
        """Hakkında penceresi — sosyal medya bağlantılarıyla."""
        import webbrowser

        pencere = tk.Toplevel(self.kok)
        pencere.title("Hakkında")
        pencere.geometry("500x500")
        pencere.resizable(False, False)
        pencere.transient(self.kok)
        pencere.grab_set()

        ana = ttk.Frame(pencere, padding=20)
        ana.pack(fill="both", expand=True)

        ttk.Label(
            ana,
            text="📊 KDV Çapraz Kontrol",
            font=("Segoe UI", 16, "bold"),
            foreground="#4472C4",
        ).pack(pady=(0, 10))

        ttk.Label(
            ana,
            text="e-Fatura, PDF ve Excel faturaları ile\nKDV kontrol cetvellerini çapraz kontrol eder.",
            justify="center",
        ).pack(pady=(0, 15))

        ayrac = ttk.Separator(ana, orient="horizontal")
        ayrac.pack(fill="x", pady=10)

        bilgi = [
            ("Sürüm", "2.0"),
            ("Geliştirici", "Arda M. Ekiz"),
            ("Tarih", "2026"),
            ("Lisans", "MIT (Kişisel Kullanım)"),
        ]
        for etiket, deger in bilgi:
            cerceve = ttk.Frame(ana)
            cerceve.pack(fill="x", pady=2)
            ttk.Label(cerceve, text=etiket + ":", font=("Segoe UI", 9, "bold"), width=12, anchor="w").pack(side="left")
            ttk.Label(cerceve, text=deger).pack(side="left")

        ayrac2 = ttk.Separator(ana, orient="horizontal")
        ayrac2.pack(fill="x", pady=10)

        ttk.Label(
            ana,
            text="⚠️ Bu program geliştirici izni olmadan\ndeğiştirilemez, kopyalanamaz veya dağıtılamaz.",
            foreground="#B00000",
            justify="center",
            font=("Segoe UI", 9, "italic"),
        ).pack(pady=10)

        ayrac3 = ttk.Separator(ana, orient="horizontal")
        ayrac3.pack(fill="x", pady=10)

        # Sosyal medya bağlantıları
        ttk.Label(
            ana,
            text="📱 Sosyal Medya",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", padx=10, pady=(0, 4))

        sosyal_frame = ttk.Frame(ana)
        sosyal_frame.pack(anchor="w", padx=10, pady=(0, 8))

        for platform, url in [
            ("🐙 GitHub", "https://github.com/ArdaEkiz0"),
            ("🔗 LinkedIn", "https://www.linkedin.com/in/arda-mehmet-ekiz-107640333/"),
            ("📷 Instagram", "https://www.instagram.com/ardaaekiz/"),
            ("📧 E-posta", "mailto:ardaekiz72@gmail.com"),
        ]:
            ttk.Button(
                sosyal_frame,
                text=platform,
                command=lambda u=url: webbrowser.open(u),
                width=14,
            ).pack(side="left", padx=2)

        ttk.Button(ana, text="Kapat", command=pencere.destroy).pack(pady=(8, 0))

    def rapor_kaydet(self):
        if not self.sonuc_satirlari:
            messagebox.showwarning("Uyarı", "Önce kontrol çalıştırın.")
            return
        varsayilan = f"KDV_Kontrol_Raporu_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        hedef = filedialog.asksaveasfilename(
            title="Excel Raporunu Kaydet", defaultextension=".xlsx",
            initialfile=varsayilan, filetypes=[("Excel Dosyası", "*.xlsx")])
        if not hedef:
            return
        try:
            if self.ayarlar:
                self.ayarlar.kaydet("son_rapor_klasor", os.path.dirname(hedef))
            rapor_olustur(self.sonuc_satirlari, self.ozet, self.faturalar, self.cetvel_kayitlari, hedef)
            messagebox.showinfo("Başarılı", f"Rapor kaydedildi:\n{hedef}")
            self._log_yaz(f"Excel raporu kaydedildi: {hedef}")
        except Exception as hata:
            messagebox.showerror("Hata", f"Rapor kaydedilemedi:\n{hata}")

    def rapor_pdf_kaydet(self):
        if not self.sonuc_satirlari:
            messagebox.showwarning("Uyarı", "Önce kontrol çalıştırın.")
            return
        varsayilan = f"KDV_Kontrol_Raporu_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        hedef = filedialog.asksaveasfilename(
            title="PDF Raporunu Kaydet", defaultextension=".pdf",
            initialfile=varsayilan, filetypes=[("PDF Dosyası", "*.pdf")])
        if not hedef:
            return
        try:
            if self.ayarlar:
                self.ayarlar.kaydet("son_rapor_klasor", os.path.dirname(hedef))
            rapor_pdf_olustur(self.sonuc_satirlari, self.ozet, self.faturalar, self.cetvel_kayitlari, hedef)
            messagebox.showinfo("Başarılı", f"PDF raporu kaydedildi:\n{hedef}")
            self._log_yaz(f"PDF raporu kaydedildi: {hedef}")
            if messagebox.askyesno("Aç", "PDF dosyası şimdi açılsın mı?"):
                os.startfile(hedef)
        except Exception as hata:
            messagebox.showerror("Hata", f"PDF raporu kaydedilemedi:\n{hata}")


def main():
    try:
        kok = tk.Tk()
        KdvKontrolApp(kok)
        kok.mainloop()
    except Exception:
        import os
        import traceback
        log_yolu = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hata.log")
        with open(log_yolu, "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        raise


if __name__ == "__main__":
    main()
