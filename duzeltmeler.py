"""Düzeltme sözlüğü, gürültü desenleri ve KDV kuralları.

phobo3s'in PTAReceiptParser/Hledger-Excel repolarındaki kalıplarından
esinlenerek e-Fatura verileri için uyarlandı. İzin: issue #1 comment
5584822477.

Kullanım:
    from duzeltmeler import metni_duzelt, gurultu_mu, kdv_kurali_kontrol
"""

import re
from decimal import Decimal, ROUND_HALF_UP

# ── 1. Düzeltme Sözlüğü ─────────────────────────────────────────────────────
# e-Fatura HTML'indeki metin hatalarını düzeltir.
# Her entry: (hatalı desen, doğru karşılık) — regex replace ile uygulanır.
# Sıra önemli: önce uzun/özgün desenler, sonra kısa/genel desenler.

DUZELTME_LISTESI = [
    # ── Türkçe karakter hataları (OCR / HTML encoding) ──
    (r'\bI\b(?!\.)', 'İ'),                   # Bağımsız I → İ (sadece nokta yoksa)
    (r'\bi\b', 'İ'),                          # bağımsız i → İ
    (r'STl\.', 'ŞTİ.'),                       # STl. → ŞTİ.
    (r'ST\.?I\.', 'ŞTİ.'),                    # STI. → ŞTİ.
    (r'LTD\.?STl\.', 'LTD.ŞTİ.'),            # LTD.STl. → LTD.ŞTİ.
    (r'INS\.', 'İNŞ.'),                       # INS. → İNŞ.
    (r'TIC\.', 'TİC.'),                       # TIC. → TİC.
    (r'VERGI', 'VERGİ'),                      # VERGI → VERGİ
    (r'DAIRESI', 'DAİRESİ'),                  # DAIRESİ → DAİRESİ
    (r'MUD\.', 'MÜD.'),                       # MUD. → MÜD.
    (r'UNIVERSITESI', 'ÜNİVERSİTESİ'),        # UNIVERSITESI → ÜNİVERSİTESİ
    (r'FILIZI', 'FİLİZİ'),                    # FILIZİ → FİLİZİ
    (r'IZMIR', 'İZMİR'),                      # IZMİR → İZMİR
    (r'BORNOVA', 'BORNOVA'),                  # BORNOVA (değişiklik yok, doğrulama)
    (r'SANAYI', 'SANAYİ'),                    # SANAYI → SANAYİ
    (r'SATIS', 'SATIŞ'),                      # SATIS → SATIŞ
    (r'KREDI', 'KREDİ'),                      # KREDI → KREDİ
    (r'ISLEM', 'İŞLEM'),                      # ISLEM → İŞLEM
    (r'FiS', 'FİŞ'),                          # FiS → FİŞ
    (r'TARIH', 'TARİH'),                      # TARIH → TARİH
    (r'YIYECEK', 'YİYECEK'),                  # YIYECEK → YİYECEK
    (r'SATTS', 'SATIŞ'),                      # SATTS → SATIŞ (OCR)

    # ── Firma adı düzeltmeleri ──
    (r'BIM BIRLESIK', 'BİM BİRLEŞİK'),        # BİM market
    (r'SOK MARKETLER', 'ŞOK MARKETLER'),       # ŞOK market
    (r'KOVAN BAR TURIZH', 'KOVAN BAR TURİZM'), # KOVAN BAR
    (r'TASBAHCE', 'TAŞBAHÇE'),                # TAŞBAHÇE

    # ── Sayısal düzeltmeler ──
    (r'(\d{2})\.(\d{2})\.(\d{4})', r'\1.\2.\3'),  # Tarih formatı korunur
    (r'(\d{2})\.(\d{2})\.(\d{2})\b', r'\1.\2.20\3'),  # 2 haneli yıl → 4 haneli

    # ── Para birimi normalleştirmesi ──
    (r'[￥¥§¢€£₹₽=]', '*'),                  # Garip para sembolleri → *
    (r'%[0-9A-Fa-f]{2}', ' '),                # URL encoding: %20 → boşluk
]

# Kompilasyon (performans için)
_DUZELTME_KOMPILE = [(re.compile(pattern, re.IGNORECASE), replacement)
                     for pattern, replacement in DUZELTME_LISTESI]


def metni_duzelt(metin):
    """e-Fatura metnindeki bilinen hataları düzeltir.

    Args:
        metin: Düzeltilecek metin string'i

    Returns:
        Düzeltme uygulanmış metin
    """
    if not metin:
        return metin
    sonuc = metin
    for pattern, replacement in _DUZELTME_KOMPILE:
        sonuc = pattern.sub(replacement, sonuc)
    return sonuc


# ── 2. Gürültü Desenleri ─────────────────────────────────────────────────────
# e-Fatura HTML'inden çekilen verilerdeki gereksiz/gürültü satırları.
# Bu desenlere uyan satırlar işlenmez.

GURULTU_DESENLERI = [
    # ── Belge başlık bilgileri ──
    r'^TCKN\b',
    r'^ETTN\b',
    r'^FATURA\s+(NO|TARİH|TİPİ)',
    r'^E-[Aa]rşiv',
    r'^Sira\s+No',
    r'^Buyuk\s+Mukellef',
    r'^VKN\b',

    # ── KDV özet satırları ──
    r'^TOPLAM\s*K[OD]V',
    r'^KDV\s+(MATRAH|TUTAR|DAHIL)',
    r'^(KDV|MATRAH|KOV\s+TUTAR|KOV\s+DAH)',
    r'^TOPK[DO][VU]',
    r'^TOPKUV',
    r'^TOPLAM\s+K[OD]',

    # ── Ödeme bilgileri ──
    r'^Odenecek',
    r'^Banka\b',
    r'^GARANTI',
    r'^Onay',
    r'^Ref\.?\s*No',
    r'^POS:',
    r'^GS\s+No',
    r'^KREDI\s+KARTI',
    r'^KART\s+NO',
    r'^RRN:',
    r'^ACQU[Iİ]RER',
    r'^EFT-[PF]OS',
    r'^Nakit\b',
    r'^Kredi\s+Kartı\b',

    # ── Tarih/saat satırları ──
    r'^\d{2}\.\d{2}\.\d{4}',                     # 31.12.2026
    r'^\d{2}\.\d{2}\.\d{2}\b',                   # 31.12.26

    # ── Barkod / POS sistem satırları ──
    r'^\d{15,}$',                                 # Uzun barkod numaraları
    r'^#+\s',                                     # ## BarkoPOS
    r'^[BI]:[\d]+',                               # B:706 S:9638
    r'^\d{4,6}\*+\d{4}$',                         # Kart numarası
    r'^\*{5,}',                                   # ****2911
    r'^\*{3,}\d{1,4}$',                           # ***2911

    # ── KDV kodu satırları ──
    r'^%[\s\d]+\s*$',                             # %1, %20

    # ── OCR gürültüsü ──
    r'^\$[\d]*\.?$',                              # $0.
    r'^[\$各\\]',                                  # Saçma karakterler
    r'^\d+\.$',                                   # Sadece "1."
    r'^[\d）]+\)$',                                # Parantez içi sayı

    # ── Ara toplam satırları ──
    r'^AFATOPLAM',
    r'^ARATOPLAM',
    r'^ARATOPLAN',
    r'^APATOPLAM',
    r'^TOP(LAH|PLAH)?$',
    r'^JOPLAM',
    r'^ARA\s+TOPLAM',

    # ── Fatura detay bilgileri ──
    r'^MERKEZ:',
    r'^OLUŞTURMA\s+TARİHİ',
    r'^FİİLİ\s+SEVK\s+TARİHİ',
    r'^METRO\s+FATURA\s+NO',
    r'^İŞLEM\s+NO',
    r'^KASİYER\s+NO',
    r'^MÜŞTERI\s+NO',
    r'^TEL[:\s：]',
    r'^FAX[:\s：]',
    r'^www\.',
    r'^ww\.',

    # ── Hizmet/teşekkür satırları ──
    r'^TUTAR\s+KARŞILAŞTIRI',
    r'^HİZMET\s+ALINDI',
    r'^BU\s+BEL',
    r'^TEŞEKKÜR',

    # ── Ürün/koli bilgileri ──
    r'^Toplam\s+Koli\s+Mik\.:',
    r'^BROT\s+GIDA',
    r'^BRUT\s+GIDA',
    r'^(NET|ODEME|ÖDEM|ÖDEME)\s+TUTARI',
    r'^\d{3}\s+\d+[\.,]\d{2}',                   # Ödeme kodu + tutar
]

# Kompilasyon
_GURULTU_KOMPILE = [re.compile(pattern, re.IGNORECASE)
                    for pattern in GURULTU_DESENLERI]


def gurultu_mu(satir):
    """Bir satırın gürültü (işlenmemesi gereken) olup olmadığını söyler.

    Args:
        satir: Kontrol edilecek satır

    Returns:
        True ise bu satır atlanmalı
    """
    if not satir:
        return True
    temiz = satir.strip()
    if not temiz:
        return True
    for pattern in _GURULTU_KOMPILE:
        if pattern.search(temiz):
            return True
    return False


# ── 3. KDV Kuralları ─────────────────────────────────────────────────────────
# rules.py pattern'inden esinlenerek KDV hesaplama kuralları.
# Her kural: bir dict — {"kural": str, "aciklama": str, "kontrol": callable}

GE_CERLI_KDV_ORANLARI = {0, 1, 8, 10, 18, 20}
STANDARD_TEVKIFAT_FRACTIONS = [
    (1, 10), (2, 10), (3, 10), (4, 10),
    (5, 10), (5.5, 10), (7, 10), (9, 10), (10, 10),
]


def _parse_tutar(deger):
    """Çeşitli formatlardaki tutar değerlerini Decimal'a çevirir."""
    if deger is None:
        return None
    if isinstance(deger, (int, float)):
        return Decimal(str(deger)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if isinstance(deger, Decimal):
        return deger.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    s = str(deger).strip()
    if not s:
        return None
    s = re.sub(r'\s*(TL|TRY|EUR|USD|GBP)\s*$', '', s, flags=re.IGNORECASE).strip()
    if not s:
        return None
    last_comma = s.rfind(',')
    last_dot = s.rfind('.')
    if last_comma > last_dot:
        normalized = s.replace('.', '').replace(',', '.')
    elif last_dot > last_comma:
        normalized = s.replace(',', '')
    else:
        normalized = s
    try:
        return Decimal(normalized).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return None


def kdv_orani_kontrol(matrah, kdv, oranlar=None):
    """Matrah × Oran / 100 = KDV hesabını doğrular.

    Args:
        matrah: Matrah tutarı (Decimal, float, str)
        kdv: KDV tutarı
        oranlar: KDV oranları listesi (örn: [20] veya [10, 20])

    Returns:
        dict: {"ok": bool, "text": str, "oran": float}
    """
    m = _parse_tutar(matrah)
    k = _parse_tutar(kdv)
    if m is None or k is None or k <= 0:
        return {"ok": True, "text": "KDV tutarı bulunamadı, atlanıyor.", "oran": None}

    if not oranlar:
        # Oran bilinmiyorsa, ters hesapla
        if m > 0:
            bulunan_oran = (k / m * 100).quantize(Decimal("0.1"))
            return {
                "ok": int(bulunan_oran) in GE_CERLI_KDV_ORANLARI,
                "text": f"KDV/Matrah oranı: %{bulunan_oran}"
                        + ("" if int(bulunan_oran) in GE_CERLI_KDV_ORANLARI
                           else f" — geçerli bir KDV oranı değil!"),
                "oran": float(bulunan_oran),
            }
        return {"ok": True, "text": "Matrah sıfır, kontrol yapılamıyor.", "oran": None}

    # Tek oranlı fatura
    if len(oranlar) == 1:
        oran = Decimal(str(oranlar[0]))
        beklenen = (m * oran / Decimal("100")).quantize(Decimal("0.01"))
        fark = abs(beklenen - k)
        ok = fark <= Decimal("0.05")
        return {
            "ok": ok,
            "text": (f"Matrah ({m:,.2f}) × %{oran} = {beklenen:,.2f}"
                     f" {'=' if ok else '≠'} KDV ({k:,.2f})"
                     + (f" — fark: {fark:,.2f}" if not ok else "")),
            "oran": float(oran),
        }

    # Çok oranlı fatura — toplam kontrol
    toplam_beklenen = Decimal("0")
    for oran in oranlar:
        o = Decimal(str(oran))
        toplam_beklenen += (m * o / Decimal("100")).quantize(Decimal("0.01"))
    fark = abs(toplam_beklenen - k)
    ok = fark <= Decimal("0.05")
    return {
        "ok": ok,
        "text": (f"Çok oranlı KDV toplamı: {toplam_beklenen:,.2f}"
                 f" {'=' if ok else '≠'} KDV ({k:,.2f})"
                 + (f" — fark: {fark:,.2f}" if not ok else "")),
        "oran": float(sum(oranlar)),
    }


def tevkifat_orani_kontrol(tevkifat_tutar, kdv_tutar):
    """Tevkifat tutarının KDV'ye oranını GİB standart fraksiyonlarıyla karşılaştırır.

    Returns:
        dict: {"ok": bool, "text": str, "oran": str}
    """
    t = _parse_tutar(tevkifat_tutar)
    k = _parse_tutar(kdv_tutar)
    if t is None or k is None or k <= 0 or t <= 0:
        return {"ok": True, "text": "Tevkifat/KDV verisi yetersiz.", "oran": None}

    oran_orani = t / k
    en_yakin = None
    en_kucuk_fark = Decimal("999")
    for pay, payda in STANDARD_TEVKIFAT_FRACTIONS:
        standart = Decimal(str(pay)) / Decimal(str(payda))
        fark = abs(oran_orani - standart)
        if fark < en_kucuk_fark:
            en_kucuk_fark = fark
            en_yakin = (pay, payda)

    ok = en_kucuk_fark <= Decimal("0.015")
    oran_yuzde = (oran_orani * 100).quantize(Decimal("0.1"))
    if en_yakin:
        standart_yuzde = (Decimal(str(en_yakin[0])) /
                          Decimal(str(en_yakin[1])) * 100).quantize(Decimal("0.1"))
    else:
        standart_yuzde = Decimal("0")

    return {
        "ok": ok,
        "text": (f"Tevkifat: {t:,.2f} / KDV: {k:,.2f} = %{oran_yuzde}"
                 + (f" → standart {en_yakin[0]}/{en_yakin[1]} (%{standart_yuzde}) uyuyor"
                    if ok else
                    f" → STANDART DEĞİL (en yaklaştırık "
                    f"{en_yakin[0]}/{en_yakin[1]}=%{standart_yuzde})")),
        "oran": f"{en_yakin[0]}/{en_yakin[1]}" if en_yakin else None,
    }


def matrah_toplam_kontrol(matrah, kdv, diger_vergi=0, toplam=0):
    """Matrah + KDV + Diğer Vergi = Toplam kontrolü.

    Returns:
        dict: {"ok": bool, "text": str}
    """
    m = _parse_tutar(matrah)
    k = _parse_tutar(kdv)
    d = _parse_tutar(diger_vergi) or Decimal("0")
    t = _parse_tutar(toplam)
    if m is None or k is None or t is None:
        return {"ok": True, "text": "Yetersiz veri, kontrol yapılamıyor."}

    beklenen = m + k + d
    fark = abs(beklenen - t)
    ok = fark <= Decimal("0.05")
    return {
        "ok": ok,
        "text": (f"Matrah ({m:,.2f}) + KDV ({k:,.2f}) + Diğer Vergi ({d:,.2f}) "
                 f"= {beklenen:,.2f} {'=' if ok else '≠'} Toplam ({t:,.2f})"
                 + (f" — fark: {fark:,.2f}" if not ok else "")),
    }


def gecerli_kdv_orani_mi(oran):
    """Verilen KDV oranının GİB tarafından tanınıp tanınmadığını söyler.

    Returns:
        bool
    """
    try:
        o = int(Decimal(str(oran)))
        return o in GE_CERLI_KDV_ORANLARI
    except Exception:
        return False
