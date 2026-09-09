"""Muavin raporu HTML/metin → Excel dönüştürücü.

Luca muavin dökümünün inner_text veya HTML'inden yapılandırılmış veri
çıkaran ve Excel'e yazan modül. Export butonu çalışmadığında fallback
olarak kullanılır.

Kullanım:
    from muavin_scraper import muavin_html_ayikla, muavin_excel_yaz

    # inner_text'ten
    kayitlar = muavin_html_ayikla(metin=raw_text, hesap="191")

    # HTML'den (daha güvenilir)
    kayitlar = muavin_html_ayikla(html=raw_html, hesap="191")

    # Excel'e yaz
    muavin_excel_yaz(kayitlar, "cikti.xlsx")
"""

import os
import re
from datetime import datetime

# Tarih deseni: dd.mm.yyyy
_TARIH_DESENI = re.compile(
    r'(?<!\d)(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})(?!\d)')

# Sayısal tutar deseni (binlik noktalı veya virgüllü)
_TUTAR_DESENI = re.compile(
    r'(?<!\d)(\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})?|\d+(?:,\d{2})?)(?!\d)')

# Hesap kodu deseni: 191, 191.01, 191.01.001 vb.
_HESAP_DESENI = re.compile(
    r'^(\d{3}(?:\.\d{1,2}){0,2})\s')

# Belge no desenleri (e-fatura, e-arsiv, gider pusulası vb.)
_BELGE_NO_DESENI = re.compile(
    r'([A-Z]{2,3}\d{4,14}|\d{6,14})')

# Fiş tipi kısaltmaları
_FIS_TIP_MAP = {
    'FT': 'FATURA',
    'YN': 'YENİLEN',
    'IP': 'İADE',
    'GP': 'GİDER PUSULASI',
    'TK': 'TAHSİLAT',
    'NA': 'NAKİT',
    'KK': 'KREDİ KARTI',
    'BC': 'BONCUPON',
    'DE': 'DEVİR',
}


def _tutar_oku(metin):
    """Virgüllü/noktalı tutar değerini float'a çevirir."""
    if not metin:
        return None
    s = str(metin).strip()
    if not s or s == '-' or s == '0':
        return None
    # Boşlukları temizle (binlik ayracı)
    s = s.replace(' ', '')
    # Virgül ondalık ayracı mı nokta mı?
    if ',' in s and '.' in s:
        # 1.234,56 formatı
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        # 1234,56 veya 1234,5 formatı
        s = s.replace(',', '.')
    try:
        v = float(s)
        return v if v != 0 else None
    except (ValueError, TypeError):
        return None


def _tarih_oku(metin):
    """dd.mm.yyyy formatındaki tarihi YYYY-MM-DD'ye çevirir."""
    if not metin:
        return None
    m = _TARIH_DESENI.search(str(metin))
    if not m:
        return None
    gun, ay, yil = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if 1 <= ay <= 12 and 1 <= gun <= 31 and 2000 <= yil <= 2099:
        return f"{yil:04d}-{ay:02d}-{gun:02d}"
    return None


def _belge_no_bul(metin):
    """Açıklama satırından belge numarasını çıkarır."""
    if not metin:
        return None
    m = _BELGE_NO_DESENI.search(str(metin))
    return m.group(1) if m else None


def _satir_ayikla(satir, kolon_sayisi):
    """Bir tablo satırını hücrelere böler.

    Hem HTML <td> yapısından gelen分割 hem de düz metin satırlarını
    tab'a göre böler.
    """
    if not satir:
        return []
    # Zaten liste olarak geldiyse (HTML parser'dan)
    if isinstance(satir, list):
        return [str(c).strip() if c else '' for c in satir]
    # Tab ile bölünmüş düz metin
    s = str(satir).strip()
    if '\t' in s:
        return [c.strip() for c in s.split('\t')]
    # Birden fazla boşlukla bölünmüş
    parcalar = s.split()
    if len(parcalar) >= kolon_sayisi:
        return parcalar
    return [s]


def muavin_html_ayikla(html=None, metin=None, hesap=""):
    """HTML veya inner_text'ten muavin kayıtlarını çıkarır.

    Args:
        html: Ham HTML string'i (varsa tercih edilir)
        metin: inner_text string'i (html yoksa)
        hesap: Hesap kodu (ör: "191", "391")

    Returns:
        list[dict]: Her biri şu alanları içerir:
            - tarih: str (YYYY-MM-DD)
            - belge_no: str
            - fis_tipi: str (FT, YN, GP vb.)
            - aciklama: str
            - borc: float|None
            - alacak: float|None
            - hesap: str
    """
    kayitlar = []

    # HTML'den tablo satırlarını çıkar
    satirlar = _htmlden_satirlar_cek(html) if html else []
    if not satirlar and metin:
        satirlar = metin.split('\n')

    if not satirlar:
        return kayitlar

    # Başlık satırını bul ve sütun indekslerini belirle
    baslik_i, kolon_map = _baslik_bul(satirlar)
    if baslik_i is None:
        return kayitlar

    aktif_hesap = hesap
    for i, satir in enumerate(satirlar):
        if i <= baslik_i:
            continue

        # Hesap kodu satırı mı?
        if isinstance(satir, str):
            hm = _HESAP_DESENI.match(satir)
            if hm:
                aktif_hesap = hm.group(1)
                continue

        hucreler = _satir_ayikla(satir, len(kolon_map))
        if not hucreler or all(not h for h in hucreler):
            continue

        # Tarih kontrolü
        tarih = None
        tarih_idx = kolon_map.get("tarih")
        if tarih_idx is not None and tarih_idx < len(hucreler):
            tarih = _tarih_oku(hucreler[tarih_idx])
        if not tarih:
            # İlk hücrede tarih ara
            for h in hucreler[:2]:
                tarih = _tarih_oku(h)
                if tarih:
                    break
        if not tarih:
            continue

        # Belge no
        belge_no = None
        belge_idx = kolon_map.get("belge_no")
        if belge_idx is not None and belge_idx < len(hucreler):
            belge_no = hucreler[belge_idx].strip() if hucreler[belge_idx] else None
        if not belge_no:
            # Açıklama içinden bul
            aciklama_idx = kolon_map.get("aciklama")
            if aciklama_idx is not None and aciklama_idx < len(hucreler):
                belge_no = _belge_no_bul(hucreler[aciklama_idx])

        # Fiş tipi
        fis_tipi = ""
        tip_idx = kolon_map.get("fis_tipi")
        if tip_idx is not None and tip_idx < len(hucreler):
            fis_tipi = hucreler[tip_idx].strip().upper() if hucreler[tip_idx] else ""

        # Açıklama
        aciklama = ""
        aciklama_idx = kolon_map.get("aciklama")
        if aciklama_idx is not None and aciklama_idx < len(hucreler):
            aciklama = hucreler[aciklama_idx].strip() if hucreler[aciklama_idx] else ""

        # Borç / Alacak
        borc = None
        alacak = None
        borc_idx = kolon_map.get("borc")
        alacak_idx = kolon_map.get("alacak")
        if borc_idx is not None and borc_idx < len(hucreler):
            borc = _tutar_oku(hucreler[borc_idx])
        if alacak_idx is not None and alacak_idx < len(hucreler):
            alacak = _tutar_oku(hucreler[alacak_idx])

        # Toplam satırlarını atla
        if aciklama and ('Yekun' in aciklama or 'TOPLAM' in aciklama.upper()):
            continue
        if belge_no and ('TOPLAM' in belge_no.upper()):
            continue

        # En az tarih veya belge_no olmalı
        if not belge_no and borc is None and alacak is None:
            continue

        kayitlar.append({
            "tarih": tarih,
            "belge_no": belge_no or "",
            "fis_tipi": fis_tipi,
            "aciklama": aciklama[:200],
            "borc": borc,
            "alacak": alacak,
            "hesap": aktif_hesap or hesap,
        })

    return kayitlar


def _htmlden_satirlar_cek(html):
    """HTML içinden <tr> satırlarını list olarak döner."""
    if not html:
        return []
    try:
        from html.parser import HTMLParser
    except ImportError:
        return []

    class TabloParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.satirlar = []
            self.aktif_satir = []
            self.aktif_hucre = []
            self.tag_stack = []
            self.in_td = False

        def handle_starttag(self, tag, attrs):
            self.tag_stack.append(tag)
            if tag == 'tr':
                self.aktif_satir = []
            elif tag in ('td', 'th'):
                self.in_td = True
                self.aktif_hucre = []

        def handle_endtag(self, tag):
            if self.tag_stack:
                self.tag_stack.pop()
            if tag in ('td', 'th'):
                self.in_td = False
                self.aktif_satir.append(''.join(self.aktif_hucre))
            elif tag == 'tr':
                if self.aktif_satir:
                    self.satirlar.append(self.aktif_satir)

        def handle_data(self, data):
            if self.in_td:
                self.aktif_hucre.append(data)

    try:
        parser = TabloParser()
        parser.feed(html)
        return parser.satirlar
    except Exception:
        return []


def _baslik_bul(satirlar):
    """Başlık satırını ve sütun haritasını bulur.

    Returns:
        (baslik_indeksi, {kolon_adi: indeks}) veya (None, None)
    """
    anahtar_kelimeler = {
        "tarih": ["TARİH", "TARIH", "TARİHİ"],
        "fis_tipi": ["TÜP", "TİP", "TIP", "FİŞ TİPİ", "FIS TIP"],
        "belge_no": ["FİŞ NO", "FIS NO", "BELGE NO", "BELGE"],
        "aciklama": ["AÇIKLAMA", "ACIKLAMA", "İŞLEM"],
        "borc": ["BORÇ", "BORC", "BORÇ BEDELİ", "BORC BEDELI", "BORÇ TUT.", "BORC TUT"],
        "alacak": ["ALACAK", "ALACAK BEDELİ", "ALACAK BEDELI", "ALACAK TUT.", "ALACAK TUT"],
    }

    for i, satir in enumerate(satirlar):
        hucreler = _satir_ayikla(satir, 10)
        hucre_yuksek = [h.upper().strip() for h in hucreler]

        kolon_map = {}
        for kolon_adi, kelimeler in anahtar_kelimeler.items():
            for j, hucre in enumerate(hucre_yuksek):
                if any(k in hucre for k in kelimeler):
                    kolon_map[kolon_adi] = j
                    break

        # En az tarih ve bir tutar sütunu olmalı
        if "tarih" in kolon_map and ("borc" in kolon_map or "alacak" in kolon_map):
            return i, kolon_map

    return None, None


def muavin_excel_yaz(kayitlar, dosya_yolu, hesap=""):
    """Ayıklanmış muavin kayıtlarını Excel'e yazar.

    Args:
        kayitlar: muavin_html_ayikla() çıktısı
        dosya_yolu: Hedef .xlsx dosya yolu
        hesap: Hesap kodu (başlık için)
    """
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    except ImportError:
        raise ImportError("openpyxl yüklü değil: pip install openpyxl")

    wb = Workbook()
    ws = wb.active
    ws.title = f"Muavin {hesap}" if hesap else "Muavin"

    # Başlık stilleri
    baslik_font = Font(bold=True, color="FFFFFF")
    baslik_dolgu = PatternFill(start_color="4472C4", end_color="4472C4",
                                fill_type="solid")
    sayi_format = '#,##0.00'
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin'),
    )

    # Sütun başlıkları
    basliklar = ["Tarih", "Fiş Tipi", "Belge No", "Açıklama",
                 "Borç", "Alacak", "Hesap"]
    for col, baslik in enumerate(basliklar, 1):
        hucre = ws.cell(row=1, column=col, value=baslik)
        hucre.font = baslik_font
        hucre.fill = baslik_dolgu
        hucre.alignment = Alignment(horizontal="center")
        hucre.border = thin_border

    # Veri satırları
    borc_toplam = 0
    alacak_toplam = 0
    for row_idx, kayit in enumerate(kayitlar, 2):
        tarih_str = kayit.get("tarih", "")
        if tarih_str:
            try:
                tarih_obj = datetime.strptime(tarih_str, "%Y-%m-%d")
                ws.cell(row=row_idx, column=1, value=tarih_obj)
                ws.cell(row=row_idx, column=1).number_format = 'DD.MM.YYYY'
            except ValueError:
                ws.cell(row=row_idx, column=1, value=tarih_str)
        else:
            ws.cell(row=row_idx, column=1, value="")

        ws.cell(row=row_idx, column=2, value=kayit.get("fis_tipi", ""))
        ws.cell(row=row_idx, column=3, value=kayit.get("belge_no", ""))
        ws.cell(row=row_idx, column=4, value=kayit.get("aciklama", ""))

        borc = kayit.get("borc")
        alacak = kayit.get("alacak")
        if borc is not None:
            ws.cell(row=row_idx, column=5, value=borc)
            ws.cell(row=row_idx, column=5).number_format = sayi_format
            borc_toplam += borc
        if alacak is not None:
            ws.cell(row=row_idx, column=6, value=alacak)
            ws.cell(row=row_idx, column=6).number_format = sayi_format
            alacak_toplam += alacak

        ws.cell(row=row_idx, column=7, value=kayit.get("hesap", ""))

        # Sınır ekle
        for col in range(1, 8):
            ws.cell(row=row_idx, column=col).border = thin_border

    # Toplam satırı
    toplam_row = len(kayitlar) + 2
    ws.cell(row=toplam_row, column=4, value="TOPLAM")
    ws.cell(row=toplam_row, column=4).font = Font(bold=True)
    ws.cell(row=toplam_row, column=5, value=borc_toplam)
    ws.cell(row=toplam_row, column=5).number_format = sayi_format
    ws.cell(row=toplam_row, column=5).font = Font(bold=True)
    ws.cell(row=toplam_row, column=6, value=alacak_toplam)
    ws.cell(row=toplam_row, column=6).number_format = sayi_format
    ws.cell(row=toplam_row, column=6).font = Font(bold=True)
    for col in range(1, 8):
        ws.cell(row=toplam_row, column=col).border = thin_border

    # Sütun genişlikleri
    ws.column_dimensions['A'].width = 12
    ws.column_dimensions['B'].width = 8
    ws.column_dimensions['C'].width = 22
    ws.column_dimensions['D'].width = 40
    ws.column_dimensions['E'].width = 15
    ws.column_dimensions['F'].width = 15
    ws.column_dimensions['G'].width = 12

    # Sayfayı dondur (başlık satırı)
    ws.freeze_panes = 'A2'

    os.makedirs(os.path.dirname(dosya_yolu) or '.', exist_ok=True)
    wb.save(dosya_yolu)
    return len(kayitlar)


def muavin_dosyadan_cek(dosya_yolu, hesap=""):
    """HTML veya TXT dosyasından muavin kayıtlarını çıkarır.

    Args:
        dosya_yolu: .html veya .txt dosya yolu
        hesap: Hesap kodu

    Returns:
        list[dict]: Kayıt listesi
    """
    with open(dosya_yolu, 'r', encoding='utf-8', errors='replace') as f:
        icerik = f.read()

    if dosya_yolu.lower().endswith('.html'):
        return muavin_html_ayikla(html=icerik, hesap=hesap)
    else:
        return muavin_html_ayikla(metin=icerik, hesap=hesap)
