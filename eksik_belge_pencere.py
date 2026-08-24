"""Eksik Belge Bulucu penceresi: cetvel ↔ fatura eşleştirme sonuçlarını gösterir."""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from openpyxl import Workbook

import utils


def _c_ozet(c):
    kdv = utils.tl_format(c.get("kdv")) if c.get("kdv") is not None else "?"
    return (f"{c.get('tarih') or '??'}  |  "
            f"{(c.get('unvan') or '(unvansız)')[:34]}  |  KDV {kdv}  |  "
            f"belge: {c.get('belge_no') or '-'}")


def _f_ozet(f):
    matrah = utils.tl_format(f.get("matrah")) if \
        f.get("matrah") is not None else "?"
    kdv = utils.tl_format(f.get("kdv")) if f.get("kdv") is not None else "?"
    return (f"{f.get('tarih') or '??'}  |  {(f.get('unvan') or '?')[:34]}  |  "
            f"matrah {matrah}, KDV {kdv}  |  {f.get('belge_no') or '-'}")


class EksikBelgePencere(tk.Toplevel):
    def __init__(self, ust, sonuc, cetvel_kayitlari, fatura_kayitlari):
        super().__init__(ust)
        self.title("Eksik Belge Bulucu")
        self.geometry("900x540")
        self.transient(ust)
        self.sonuc = sonuc
        self.cetvel = cetvel_kayitlari
        self.faturalar = fatura_kayitlari

        e = len(sonuc["eksik"])
        b = len(sonuc["belirsiz"])
        es = len(sonuc["eslesen"])
        fz = len(sonuc["fazla"])
        tk.Label(self, font=("Segoe UI", 10, "bold"), wraplength=860,
                 justify="left",
                 text=(f"Cetvel: {len(cetvel_kayitlari)} kayıt, "
                       f"Fatura: {len(fatura_kayitlari)} belge   —   "
                       f"Eşleşen {es}, Belirsiz {b}, BELGESİZ {e}, "
                       f"Fazla {fz}"),
                 fg="#b91c1c" if e else "#15803d").pack(
            anchor="w", padx=12, pady=(10, 4))

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=6)

        eksik_satir = [_c_ozet(self.cetvel[i]) for i in sonuc["eksik"]]
        belirsiz_satir = []
        for i, adaylar in sonuc["belirsiz"]:
            metinler = "   ⋮   ".join(
                f"{_f_ozet(self.faturalar[j])} (puan {p})"
                for j, p in adaylar)
            belirsiz_satir.append(_c_ozet(self.cetvel[i]) + "   ➜   "
                                  + metinler)
        eslesen_satir = [
            f"{_c_ozet(self.cetvel[i])}   ↔   {_f_ozet(self.faturalar[j])}"
            f"   ({y})" for i, j, y in sonuc["eslesen"]]
        fazla_satir = [_f_ozet(self.faturalar[j])
                       for j in sonuc["fazla"]]

        self._sekme_ekle("eksik", "❌ Cetvelde var, faturası yok",
                         eksik_satir)
        self._sekme_ekle("belirsiz", "🤔 Belirsiz (adaylarla)",
                         belirsiz_satir)
        self._sekme_ekle("eslesen", "✅ Eşleşen", eslesen_satir)
        self._sekme_ekle("fazla", "🔵 Faturada var, cetvelde yok",
                         fazla_satir)
        if eksik_satir:
            self.nb.select(0)

        alt = tk.Frame(self)
        alt.pack(fill="x", padx=10, pady=(0, 10))
        tk.Label(alt, fg="#666666",
                 text="Kritik liste ilk sekmedir: bu kayıtların belgesi "
                      "indirilenler arasında bulunamadı.").pack(side="left")
        tk.Button(alt, text="📤 Excel'e Aktar", relief="flat",
                  bg="#059669", fg="#ffffff", padx=12, pady=3,
                  cursor="hand2", command=self._aktar).pack(side="right")
        tk.Button(alt, text="Kapat", relief="flat", padx=10, pady=3,
                  command=self.destroy).pack(side="right", padx=(0, 8))

    def _sekme_ekle(self, anahtar, ad, satirlar):
        cerceve = tk.Frame(self.nb)
        self.nb.add(cerceve, text=f"{ad} ({len(satirlar)})")
        liste = tk.Listbox(cerceve, font=("Consolas", 9),
                           activestyle="none")
        sb = ttk.Scrollbar(cerceve, command=liste.yview)
        liste.configure(yscrollcommand=sb.set)
        liste.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for s in satirlar:
            liste.insert("end", s)
        if not satirlar:
            liste.insert("end", "(bu grupta kayıt yok)")
        setattr(self, "_liste_" + anahtar, liste)

    def _aktar(self):
        yol = filedialog.asksaveasfilename(
            parent=self, defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile="eksik_belge_raporu.xlsx")
        if not yol:
            return

        def satirlar(liste):
            return [liste.get(i) for i in range(liste.size())]

        gruplar = (
            ("CETVELDE VAR FATURASI YOK",
             satirlar(self._liste_eksik)),
            ("BELIRSIZ", satirlar(self._liste_belirsiz)),
            ("ESLESEN", satirlar(self._liste_eslesen)),
            ("FATURADA VAR CETVELDE YOK",
             satirlar(self._liste_fazla)),
        )
        wb = Workbook()
        wb.remove(wb.active)
        for ad, veriler in gruplar:
            sayfa = wb.create_sheet(ad[:31])
            sayfa.append(["AÇIKLAMA"])
            for s in veriler:
                sayfa.append([s])
            sayfa.column_dimensions["A"].width = 160
        try:
            wb.save(yol)
        except PermissionError:
            messagebox.showerror(
                "Hata", "Dosya açık görünüyor; farklı bir ad deneyin.",
                parent=self)
            return
        try:
            os.startfile(yol)
        except Exception:
            pass


def ac(ust, sonuc, cetvel_kayitlari, fatura_kayitlari):
    return EksikBelgePencere(ust, sonuc, cetvel_kayitlari,
                             fatura_kayitlari)
