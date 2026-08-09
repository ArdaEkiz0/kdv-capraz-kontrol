"""Birden fazla muavin/Excel/PDF dosyasını tek kontrolde birleştirir."""
import os
from typing import List
from tkinter import filedialog, messagebox


def coklu_cetvel_sec(parent_pencere=None) -> List[str]:
    """Kullanıcıya birden fazla dosya seçtir (filtre ile)."""
    dosyalar = filedialog.askopenfilenames(
        title="KDV Kontrol Cetveli / Muavin Dosyalarını Seçin (çoklu seçim: Ctrl+Click)",
        filetypes=[
            ("Desteklenen Dosyalar", "*.pdf *.xlsx *.xlsm *.xls"),
            ("PDF Dosyaları", "*.pdf"),
            ("Excel Dosyaları", "*.xlsx *.xlsm *.xls"),
        ],
    )
    return list(dosyalar) if dosyalar else []


def klasorden_cetvel_topla(klasor: str) -> List[str]:
    """Bir klasördeki tüm muavin/cetvel dosyalarını topla (alt klasörler dahil)."""
    if not klasor or not os.path.isdir(klasor):
        return []
    dosyalar = []
    uzantilar = (".pdf", ".xlsx", ".xlsm", ".xls")
    for kok, _, alt_dosyalar in os.walk(klasor):
        for d in alt_dosyalar:
            if d.lower().endswith(uzantilar):
                tam_yol = os.path.join(kok, d)
                dosyalar.append(tam_yol)
    return sorted(dosyalar)


def cetvel_klasor_dialog(parent_pencere=None) -> List[str]:
    """Klasör seçtir, içindeki tüm desteklenen dosyaları döndür."""
    klasor = filedialog.askdirectory(
        title="Muavin/Cetvel Klasörünü Seçin (alt klasörler dahil taranır)",
    )
    if not klasor:
        return []
    dosyalar = klasorden_cetvel_topla(klasor)
    if not dosyalar:
        if parent_pencere:
            messagebox.showwarning(
                "Uyarı",
                "Klasörde PDF/Excel dosyası bulunamadı.",
                parent=parent_pencere,
            )
    return dosyalar
