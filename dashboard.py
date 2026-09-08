"""Dashboard: KPI kartları ve grafiklerle görsel özet.

matplotlib kullanır. Tkinter canvas'a gömülü.
"""
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional
from decimal import Decimal

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from utils import tl_format
from matcher import (DURUM_OK, DURUM_TUTAR_FARKI, DURUM_VKN_FARKI,
                     DURUM_MUKERRER, DURUM_CETVELDE_YOK, DURUM_FATURADA_YOK,
                     DURUM_PARSE_SORUNU)


class KpiKarti(ttk.Frame):
    """Tek bir KPI kartı (büyük sayı + etiket + renk)."""

    def __init__(self, parent, baslik: str, deger: str, alt_metin: str = "",
                 renk: str = "#4472C4"):
        super().__init__(parent, relief="solid", borderwidth=1, padding=10)
        self.renk = renk

        baslik_label = ttk.Label(
            self, text=baslik, font=("Segoe UI", 9, "bold"),
            foreground="#666"
        )
        baslik_label.pack(anchor="w")

        deger_label = ttk.Label(
            self, text=deger, font=("Segoe UI", 18, "bold"),
            foreground=renk
        )
        deger_label.pack(anchor="w", pady=(4, 0))

        if alt_metin:
            alt = ttk.Label(self, text=alt_metin, font=("Segoe UI", 8), foreground="#888")
            alt.pack(anchor="w")


class DashboardFrame(ttk.Frame):
    """Ana dashboard: üstte KPI kartları, altta 2 grafik."""

    def __init__(self, parent, ozet: Dict, faturalar: List[Dict],
                 cetvel_kayitlari: List[Dict],
                 sonuc_satirlari: List[Dict] = None,
                 db=None):
        super().__init__(parent, padding=8)
        self.ozet = ozet or {}
        self.faturalar = faturalar or []
        self.cetvel_kayitlari = cetvel_kayitlari or []
        self.sonuc_satirlari = sonuc_satirlari or []
        self.db = db

        self._kpi_hesapla()
        self._arayuz_kur()

    def _kpi_hesapla(self):
        """Özet'ten KPI değerlerini hesapla."""
        o = self.ozet
        fatura_adet = max(o.get("fatura_adet", 0), 1)
        self.eslesme_orani = (o.get("eslesen", 0) / fatura_adet) * 100

        self.eksik_kdv = Decimal("0")
        for r in self.sonuc_satirlari:
            if r.get("durum") == DURUM_CETVELDE_YOK:
                kdv = r.get("kdv")
                if kdv is not None:
                    try:
                        self.eksik_kdv += Decimal(str(kdv))
                    except Exception:
                        pass

        sorunlu = (o.get("tutar_farki", 0) + o.get("vkn_farki", 0)
                   + o.get("cetvelde_yok", 0) + o.get("faturada_yok", 0))
        self.risk_skoru = max(
            0,
            min(100, 100 - self.eslesme_orani + sorunlu),
        )

    def _arayuz_kur(self):
        kpi_cerceve = ttk.Frame(self)
        kpi_cerceve.pack(fill="x", pady=(0, 12))

        for i in range(4):
            kpi_cerceve.columnconfigure(i, weight=1)

        o = self.ozet
        sorunlu = (o.get("tutar_farki", 0) + o.get("vkn_farki", 0)
                   + o.get("cetvelde_yok", 0) + o.get("faturada_yok", 0))

        KpiKarti(
            kpi_cerceve, "📈 Eşleşme Oranı",
            f"{self.eslesme_orani:.1f}%",
            f"{o.get('eslesen', 0)}/{o.get('fatura_adet', 0)} fatura",
            renk="#006100" if self.eslesme_orani >= 90 else "#B00000",
        ).grid(row=0, column=0, padx=4, sticky="nsew")

        KpiKarti(
            kpi_cerceve, "💰 Eksik KDV",
            tl_format(self.eksik_kdv) + " TL",
            f"{o.get('cetvelde_yok', 0)} fatura muavinde yok",
            renk="#B00000" if self.eksik_kdv > 0 else "#006100",
        ).grid(row=0, column=1, padx=4, sticky="nsew")

        KpiKarti(
            kpi_cerceve, "⚠️ Sorunlu Kayıt",
            str(sorunlu),
            f"Tutar farkı: {o.get('tutar_farki', 0)}",
            renk="#B00000" if sorunlu > 0 else "#006100",
        ).grid(row=0, column=2, padx=4, sticky="nsew")

        KpiKarti(
            kpi_cerceve, "🎯 Risk Skoru",
            f"{self.risk_skoru:.0f}/100",
            "Düşük" if self.risk_skoru < 30 else ("Orta" if self.risk_skoru < 70 else "Yüksek"),
            renk="#006100" if self.risk_skoru < 30 else ("#FFA500" if self.risk_skoru < 70 else "#B00000"),
        ).grid(row=0, column=3, padx=4, sticky="nsew")

        grafik_cerceve = ttk.Frame(self)
        grafik_cerceve.pack(fill="both", expand=True)
        grafik_cerceve.columnconfigure(0, weight=1)
        grafik_cerceve.columnconfigure(1, weight=1)

        self._durum_pasta_grafik(grafik_cerceve).grid(row=0, column=0, padx=4, sticky="nsew")
        self._aylik_trend_grafik(grafik_cerceve).grid(row=0, column=1, padx=4, sticky="nsew")

    def _durum_pasta_grafik(self, parent):
        cerceve = ttk.LabelFrame(parent, text="📊 Durum Dağılımı", padding=8)

        fig = Figure(figsize=(4, 3), dpi=100)
        ax = fig.add_subplot(111)

        o = self.ozet
        sayilar = {
            "Eşleşti": o.get("eslesen", 0),
            "Tutar Farkı": o.get("tutar_farki", 0),
            "VKN Farkı": o.get("vkn_farki", 0),
            "Mükerrer": o.get("mukerrer", 0),
            "Cetvelde Yok": o.get("cetvelde_yok", 0),
            "Faturalarda Yok": o.get("faturada_yok", 0),
            "Okunamadı": o.get("parse_sorunu", 0),
        }
        etiketler = []
        degerler = []
        for ad, sayi in sayilar.items():
            if sayi > 0:
                etiketler.append(ad)
                degerler.append(sayi)

        if degerler:
            renk_palette = {
                "Eşleşti": "#70AD47",
                "Tutar Farkı": "#C00000",
                "VKN Farkı": "#FFC000",
                "Mükerrer": "#FFC000",
                "Cetvelde Yok": "#C00000",
                "Faturalarda Yok": "#C00000",
                "Okunamadı": "#7030A0",
            }
            renkler = [renk_palette.get(e, "#999999") for e in etiketler]
            ax.pie(
                degerler,
                labels=etiketler,
                colors=renkler,
                autopct=lambda p: f"{p * sum(degerler) / 100:.0f}",
                startangle=90,
                textprops={"fontsize": 8},
            )
            ax.axis("equal")
        else:
            ax.text(0.5, 0.5, "Veri yok", ha="center", va="center")
            ax.axis("off")

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=cerceve)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        return cerceve

    def _aylik_trend_grafik(self, parent):
        cerceve = ttk.LabelFrame(parent, text="  Aylık Trend", padding=8)

        fig = Figure(figsize=(4, 3), dpi=100)
        ax = fig.add_subplot(111)

        if self.db is not None:
            try:
                trend = self.db.trend_aylik(ay_sayisi=12)
            except Exception:
                trend = []
            if trend:
                tarihler = [k["zaman"][:7] for k in trend]
                eslesme = [k["eslesen"] for k in trend]
                eksik = [float(k.get("eksik_kdv", 0) or 0) for k in trend]
                ax.bar(tarihler, eslesme, color="#4472C4", label="Eşleşen")
                ax2 = ax.twinx()
                ax2.plot(tarihler, eksik, color="#B00000", marker="o", label="Eksik KDV")
                ax.set_xticklabels(tarihler, rotation=45, fontsize=7)
                ax.legend(loc="upper left", fontsize=7)
                ax2.legend(loc="upper right", fontsize=7)
            else:
                ax.text(0.5, 0.5, "Henüz geçmiş veri yok", ha="center", va="center")
                ax.axis("off")
        else:
            ax.text(0.5, 0.5, "DB bağlı değil", ha="center", va="center")
            ax.axis("off")

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=cerceve)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        return cerceve
