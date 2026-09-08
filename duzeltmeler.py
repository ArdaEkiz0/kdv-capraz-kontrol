"""e-Fatura metin düzeltmeleri, gürültü desenleri ve KDV kuralları.

phobo3s'in PTAReceiptParser/Hledger-Excel repolarındaki kalıplarından
esinlenerek e-Fatura verileri için uyarlandı (izin: issue #1).

İçerik:
- Düzeltme sözlüğü — e-Fatura metin hatalarını düzeltir (Türkçe karakter,
  firma adı, para birimi)
- Gürültü desenleri — İşlenmemesi gereken satırları tespit eder
  (TCKN, ETTN, KDV özeti, POS satırları)
- KDV kuralları — Matrah × Oran = KDV, tevkifat oranı,
  matrah + KDV = toplam kontrolleri
"""
import re
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

# ─── Düzeltme Sözlüğü ──────────────────────────────────────────────

# Yaygın e-Fatura OCR/parse hataları: (yanlış → doğru)
DUZELTME_SOZLUGU = {
    # Türkçe karakter hataları
    "İSTANBUL": "ISTANBUL",
    "İZMIR": "IZMIR",
    "ANKARA": "ANKARA",
    "ANTALYA": "ANTALYA",
    "ADANA": "ADANA",
    "BURSA": "BURSA",
    "KONYA": "KONYA",
    "GAZiANTEP": "GAZIANTEP",
    "MERSiN": "MERSIN",
    "TRABZON": "TRABZON",

    # Firma adı düzeltmeleri (yaygın okuma hataları)
    "A.Ş.": "A.S.",
    "LTD.ŞTİ.": "LTD.STI.",
    "LİMİTED": "LIMITED",
    "TİCARET": "TICARET",
    "SANAYİ": "SANAYI",
    "PAZARLAMA": "PAZARLAMA",
    "HİZMET": "HIZMET",
    "İNŞAAT": "INSAAT",
    "TAŞIMACILIK": "TASIMACILIK",
    "DAĞITIM": "DAGITIM",
    "ELEKTRONİK": "ELEKTRONIK",
    "MEŞRUBAT": "MESRUBAT",
    "KURUYEMİŞ": "KURUYEMIS",
    "GIDAÇILIK": "GIDACILIK",

    # Para birimi hataları
    "TL": "TL",
    "TRY": "TL",
    "₺": "TL",
    "YTL": "TL",
}

# ─── Gürültü Desenleri ──────────────────────────────────────────────

# İşlenmemesi gereken satırları tespit eden regex desenleri
GURULTU_DESENLERI = [
    # TCKN (TC Kimlik Numarası) — 11 haneli, fatura satırı değil
    re.compile(r"\b[1-9]\d{10}\b"),
    # ETTN (Elektronik Tebligat Takip Numarası) — 36 karakter UUID
    re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"),
    # KDV özeti satırları ("KDV Dahil Toplam", "Vergi Toplamı" vb.)
    re.compile(r"(?i)(kdv\s*(dahil|hariç)?\s*toplam|vergi\s*toplam[ıi]|toplam\s*vergi|genel\s*toplam|ara\s*toplam)"),
    # POS/ödeme satırları
    re.compile(r"(?i)(pos\s*no|ödeme\s*no|kredi\s*kart|banka\s*kart|nakit|para\s*üstü)"),
    # Barkod/QR satırları
    re.compile(r"(?i)( barkod|qr\s*kod|kare\s*kod|e-fatura\s*no )"),
    # Sayfa numarası
    re.compile(r"(?i)(sayfa\s*\d+|page\s*\d+|\d+\s*/\s*\d+)"),
    # Tarih/saat damgası (fatura içi olmayan)
    re.compile(r"(?i)(basım\s*tarihi|yazdırma\s*tarihi|oluşturulma|print\s*date)"),
    # Onay/mühür satırları
    re.compile(r"(?i)(onay\s*kodu|mühür|imza|imzalayan|imza\s*tarafından)"),
]


def gurultu_mu(metin: str) -> bool:
    """Verilen metin gürültü (işlenmemesi gereken satır) mu?"""
    if not metin or not metin.strip():
        return True
    metin = metin.strip()
    if len(metin) < 3:
        return True
    for desen in GURULTU_DESENLERI:
        if desen.search(metin):
            return True
    return False


def metni_duzelt(metin: str) -> str:
    """e-Fatura metnindeki yaygın hataları düzeltir."""
    if not metin:
        return metin
    sonuc = metin
    for eski, yeni in DUZELTME_SOZLUGU.items():
        sonuc = sonuc.replace(eski, yeni)
    # Fazla boşlukları temizle
    sonuc = re.sub(r"\s+", " ", sonuc).strip()
    return sonuc


# ─── KDV Kuralları ──────────────────────────────────────────────────

KDV_ORANLARI = (Decimal("1"), Decimal("5"), Decimal("10"), Decimal("20"))


def kdv_matrah_dogrula(matrah: Decimal, kdv: Decimal,
                       oran: Decimal) -> dict:
    """Matrah × Oran = KDV kontrolü yapar.

    Args:
        matrah: Fatura matrahı
        kdv: KDV tutarı
        oran: KDV oranı (%1, %5, %10, %20)

    Returns:
        {"ok": bool, "beklenen": Decimal, "fark": Decimal, "mesaj": str}
    """
    if matrah is None or kdv is None or oran is None:
        return {"ok": False, "beklenen": None, "fark": None,
                "mesaj": "Eksik değer"}
    try:
        beklenen = (Decimal(str(matrah)) * Decimal(str(oran))
                    / Decimal("100")).quantize(Decimal("0.01"),
                                               rounding=ROUND_HALF_UP)
        fark = abs(Decimal(str(kdv)) - beklenen)
        tolerans = Decimal("0.02")
        return {
            "ok": fark <= tolerans,
            "beklenen": beklenen,
            "fark": fark,
            "mesaj": (f"OK ({oran}%)" if fark <= tolerans
                      else f"FARK: beklenen {beklenen}, bulunan {kdv}"),
        }
    except (InvalidOperation, ValueError):
        return {"ok": False, "beklenen": None, "fark": None,
                "mesaj": "Hesaplama hatası"}


def toplam_dogrula(matrah: Decimal, kdv: Decimal,
                   toplam: Decimal) -> dict:
    """Matrah + KDV = Toplam kontrolü yapar."""
    if matrah is None or kdv is None or toplam is None:
        return {"ok": False, "beklenen": None, "fark": None,
                "mesaj": "Eksik değer"}
    try:
        beklenen = Decimal(str(matrah)) + Decimal(str(kdv))
        fark = abs(Decimal(str(toplam)) - beklenen)
        tolerans = Decimal("0.02")
        return {
            "ok": fark <= tolerans,
            "beklenen": beklenen,
            "fark": fark,
            "mesaj": (f"OK" if fark <= tolerans
                      else f"FARK: beklenen {beklenen}, bulunan {toplam}"),
        }
    except (InvalidOperation, ValueError):
        return {"ok": False, "beklenen": None, "fark": None,
                "mesaj": "Hesaplama hatası"}


def tevkifat_orani_bul(fatura_kdv: Decimal,
                       muavin_kdv: Decimal) -> dict | None:
    """Fatura KDV'si ile muavin KDV'si arasındaki tevkifat oranını bulur.

    Klasik yön: fatura tam KDV, muavinde tevkifat sonrası kalan.
    Ters yön: fatura özeti tevkifat sonrası, muavin tam KDV.

    Returns:
        {"oran": Decimal, "yön": "klasik"|"ters", "yüzde": int} veya None
    """
    if not fatura_kdv or not muavin_kdv or fatura_kdv == 0:
        return None
    f = Decimal(str(abs(fatura_kdv)))
    m = Decimal(str(abs(muavin_kdv)))
    tolerans = Decimal("0.03")

    # Klasik yön: fatura tam, muavin kalan
    klasik_oranlar = [
        Decimal("0.70"), Decimal("0.60"), Decimal("0.50"),
        Decimal("0.40"), Decimal("0.30"), Decimal("0.20"),
        Decimal("0.10"), Decimal("0.95"),
    ]
    for oran in klasik_oranlar:
        beklenen = f * oran
        if abs(m - beklenen) <= tolerans * f:
            yuzde = int(round((1 - float(oran)) * 100))
            return {"oran": oran, "yön": "klasik", "yüzde": yuzde}

    # Ters yön: muavin tam, fatura kalan
    ters_carpanlar = [
        Decimal("1.25"), Decimal("1.4286"), Decimal("1.5"),
        Decimal("1.667"), Decimal("2.0"), Decimal("2.5"),
        Decimal("3.333"), Decimal("5.0"), Decimal("10.0"),
        Decimal("1.1111"), Decimal("1.0526"),
    ]
    for carpan in ters_carpanlar:
        beklenen = f * carpan
        if abs(m - beklenen) <= tolerans * f:
            tevkifat_oran = 1 - 1 / float(carpan)
            yuzde = int(round(tevkifat_oran * 100))
            return {"oran": Decimal(str(tevkifat_oran)),
                    "yön": "ters", "yüzde": yuzde}

    return None


def metin_listesi_temizle(satirlar: list[str]) -> list[str]:
    """Gürültü satırlarını listeden çıkarır, düzeltmeleri uygular."""
    sonuc = []
    for satir in satirlar:
        if gurultu_mu(satir):
            continue
        temiz = metni_duzelt(satir)
        if temiz:
            sonuc.append(temiz)
    return sonuc
