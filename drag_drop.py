"""Sürükle-bırak dosya desteği.

tkinter için basit sürükle-bırak dosya yükleme.
Windows'ta windnd kütüphanesi kullanır (yüklü değilse fallback).

Kullanım:
    from drag_drop import DragDropDestesi
    dd = DragDropDestesi(pencere, dosya_callback)
"""

import os
import sys
import tkinter as tk


class DragDropDestesi:
    """Widget'a sürükle-bırak desteği ekler."""

    def __init__(self, widget, callback):
        """
        Args:
            widget: Sürükle-bırak desteklenecek widget (genellikle ana pencere)
            callback: Dosya yolları listesi alan fonksiyon
        """
        self.widget = widget
        self.callback = callback
        self._aktif = False

        # windnd kütüphanesi dene
        if self._windnd_kur():
            self._aktif = True
            return

        # Fallback: Dosya seçme penceresi ile entegrasyon
        self._fallback_kur()

    def _windnd_kur(self):
        """windnd kütüphanesini kurmaya çalışır."""
        try:
            import windnd
            windnd.hook_dropfiles(self.widget, func=self._dosyalar_geldi)
            return True
        except ImportError:
            return False
        except Exception:
            return False

    def _dosyalar_geldi(self, dosyalar):
        """windnd callback'i — dosya yollarını işler."""
        try:
            # windnd byte listesi döner
            if isinstance(dosyalar, list):
                yollar = []
                for d in dosyalar:
                    if isinstance(d, bytes):
                        yollar.append(d.decode("utf-8"))
                    else:
                        yollar.append(str(d))
            else:
                yollar = [str(dosyalar)]
            if yollar:
                self.callback(yollar)
        except Exception:
            pass

    def _fallback_kur(self):
        """Fallback: Pencere üzerine tıklandığında dosya seçme."""
        # Sürükle-bırak desteklenmiyor, sadece kod yapısını koru
        self._aktif = False

    @property
    def aktif_mi(self):
        """Sürükle-bırak aktif mi?"""
        return self._aktif


def dosya_uzantilari():
    """Desteklenen dosya uzantılarını döner."""
    return [
        ("Tüm Desteklenen", "*.pdf *.xlsx *.xlsm *.xls *.xml *.zip"),
        ("PDF Dosyaları", "*.pdf"),
        ("Excel Dosyaları", "*.xlsx *.xlsm *.xls"),
        ("XML Dosyaları", "*.xml"),
        ("Zip Arşiv", "*.zip"),
    ]
