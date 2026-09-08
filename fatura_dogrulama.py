"""Fatura doğrulama modülü — FaturaMegaOkuyucu formüllerinden Python'a çevirme.

phobo3s'ın FaturaMegaOkuyucu.html'indeki matematiksel kontrol kurallarını
Python'a uyarlar. Her kontrol bir dict döner: {"ok": bool, "text": str}.

Kullanım:
    from fatura_dogrulama import faturayi_dogrula
    sonuclar = faturayi_dogrula(kayit)
    for s in sonuclar:
        if not s["ok"]:
            print(f"HATA: {s['text']}")
"""

from decimal import Decimal, ROUND_HALF_UP
import re

# GİB'in standart tevkifat kesinti oranları
STANDARD_TEVKIFAT_FRACTIONS = [
    (1, 10), (2, 10), (3, 10), (4, 10),
    (5, 10), (5.5, 10), (7, 10), (9, 10), (10, 10),
]
TEVKIFAT_ORAN_TOLERANS = Decimal("0.015")
VALIDATION_EPS = Decimal("0.05")

# Geçerli KDV oranları
GE_CERLI_KDV_ORANLARI = {0, 1, 8, 10, 18, 20}


def _parse_tutar(deger):
    """Çeşitli formatlardaki tutar değerlerini Decimal'a çevirir.

    - Noktalı binlik, virgüllü ondalık: "1.234.567,89" -> 1234567.89
    - Noktalı ondalık (İngilizce): "1234567.89" -> 1234567.89
    - Saf string: "1234567" -> 1234567.00
    - None veya boş -> None
    """
    if deger is None:
        return None
    if isinstance(deger, (int, float)):
        return Decimal(str(deger)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if isinstance(deger, Decimal):
        return deger.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    s = str(deger).strip()
    if not s:
        return None
    # TL/TRY/para birimi etiketlerini temizle
    s = re.sub(r'\s*(TL|TRY|EUR|USD|GBP)\s*$', '', s, flags=re.IGNORECASE).strip()
    if not s:
        return None
    # Son görülen ayraç ondalık ayracıdır
    last_comma = s.rfind(',')
    last_dot = s.rfind('.')
    if last_comma > last_dot:
        # Türkçe format: nokta binlik, virgül ondalık
        normalized = s.replace('.', '').replace(',', '.')
    elif last_dot > last_comma:
        # İngilizce format: virgül binlik, nokta ondalık
        normalized = s.replace(',', '')
    else:
        normalized = s
    try:
        return Decimal(normalized).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return None


def _fark_bul(a, b):
    """İki Decimal arasındaki mutlak farkı döner."""
    if a is None or b is None:
        return None
    return abs(a - b)


def _tutarli(deger):
    """Decimal'ı Türkçe formatlı string'e çevirir."""
    if deger is None:
        return "—"
    return f"{deger:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def faturayi_dogrula(kayit):
    """Bir fatura kaydını tüm kurallardan geçirir.

    `kayit` sözlüğünde şu alanlar beklenir:
        matrah, kdv, toplam, oranlar (liste), fatura_tipi (str),
        diger_vergi_toplam (Decimal, opsiyonel),
        oran_kalemleri (liste[dict], opsiyonel) — her dict'te:
            {"oran": float, "matrah": float, "kdv": float}

    Dönen liste: [{"ok": bool, "text": str, "kural": str}, ...]
    """
    sonuclar = []

    matrah = kayit.get("matrah")
    kdv = kayit.get("kdv")
    toplam = kayit.get("toplam")
    fatura_tipi = str(kayit.get("fatura_tipi", "")).upper()
    diger_vergi = kayit.get("diger_vergi_toplam") or Decimal("0")
    oran_kalemleri = kayit.get("oran_kalemleri") or []
    oranlar = kayit.get("oranlar") or []

    is_tevkifat = "TEVKIFAT" in fatura_tipi

    # ── Kural 0: Temel matrah + kdv = toplam kontrolü ──
    if matrah is not None and kdv is not None and toplam is not None:
        beklenen = matrah + kdv + diger_vergi
        fark = _fark_bul(beklenen, toplam)
        if fark is not None:
            ok = fark <= VALIDATION_EPS
            sonuclar.append({
                "ok": ok,
                "kural": "matrah_kdv_toplam",
                "text": (f"Matrah ({_tutarli(matrah)}) + KDV ({_tutarli(kdv)}) + "
                         f"Diğer Vergi ({_tutarli(diger_vergi)}) = {_tutarli(beklenen)} "
                         f"{'=' if ok else '≠'} Toplam ({_tutarli(toplam)})"
                         + (f" — fark: {_tutarli(fark)}" if not ok else ""))
            })

    # ── KDV oran kontrolü (oran_kontrol.py mantığı) ──
    if matrah is not None and kdv is not None and kdv > 0:
        if oran_kalemleri:
            # Çok oranlı fatura
            toplam_kdv_hesap = Decimal("0")
            for item in oran_kalemleri:
                oran = Decimal(str(item.get("oran", 0)))
                o_matrah = _parse_tutar(item.get("matrah"))
                o_kdv = _parse_tutar(item.get("kdv"))
                if o_matrah is not None and oran > 0:
                    beklenen_kdv = (o_matrah * oran / Decimal("100")).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP)
                    toplam_kdv_hesap += beklenen_kdv
            fark = _fark_bul(toplam_kdv_hesap, kdv)
            if fark is not None:
                ok = fark <= VALIDATION_EPS
                esittir = "=" if ok else "!="
                sonuclar.append({
                    "ok": ok,
                    "kural": "cok_oranli_kdv",
                    "text": (f"Cok oranli KDV toplami ({_tutarli(toplam_kdv_hesap)}) "
                             f"{esittir} KDV ({_tutarli(kdv)})"
                             + (f" — fark: {_tutarli(fark)}" if not ok else ""))
                })
        elif len(oranlar) == 1:
            oran = Decimal(str(oranlar[0]))
            beklenen_kdv = (matrah * oran / Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP)
            fark = _fark_bul(beklenen_kdv, kdv)
            if fark is not None:
                ok = fark <= VALIDATION_EPS
                esittir = "=" if ok else "!="
                sonuclar.append({
                    "ok": ok,
                    "kural": "tek_oranli_kdv",
                    "text": (f"Matrah ({_tutarli(matrah)}) x %{oran} = "
                             f"{_tutarli(beklenen_kdv)} {esittir} "
                             f"KDV ({_tutarli(kdv)})"
                             + (f" — fark: {_tutarli(fark)}" if not ok else ""))
                })

    # ── Tevkifat faturaları için ek kontroller ──
    if is_tevkifat and toplam is not None:
        # Tevkifat tutarını hesapla (varsaoran_kalemleri'nden)
        tevkifat_toplam = Decimal("0")
        if oran_kalemleri:
            for item in oran_kalemleri:
                t = _parse_tutar(item.get("tevkifat"))
                if t is not None:
                    tevkifat_toplam += t

        if tevkifat_toplam > 0:
            # Kural 3: Tevkifat tutarının tam KDV'ye oranı
            for item in oran_kalemleri:
                oran = Decimal(str(item.get("oran", 0)))
                o_matrah = _parse_tutar(item.get("matrah"))
                if o_matrah is None or oran <= 0:
                    continue
                tam_kdv = (o_matrah * oran / Decimal("100")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP)
                if tam_kdv <= 0:
                    continue
                # Bu orana düşen tevkifat payı (toplamdan orantılı)
                if tevkifat_toplam > 0:
                    oran_fiyati = tam_kdv  # bu oranın payı
                    toplam_tam_kdv = sum(
                        (_parse_tutar(it.get("matrah")) or Decimal("0")) *
                        Decimal(str(it.get("oran", 0))) / Decimal("100")
                        for it in oran_kalemleri
                        if _parse_tutar(it.get("matrah")) is not None
                    )
                    if toplam_tam_kdv > 0:
                        pay = tam_kdv / toplam_tam_kdv
                        bu_orana_dusen_tevkifat = (tevkifat_toplam * pay).quantize(
                            Decimal("0.01"), rounding=ROUND_HALF_UP)
                    else:
                        bu_orana_dusen_tevkifat = tevkifat_toplam
                else:
                    bu_orana_dusen_tevkifat = tevkifat_toplam

                if bu_orana_dusen_tevkifat <= 0:
                    continue

                oran_orani = bu_orana_dusen_tevkifat / tam_kdv
                # En yakın standart fraksiyonu bul
                en_yakin = None
                en_kucuk_fark = Decimal("999")
                for pay, payda in STANDARD_TEVKIFAT_FRACTIONS:
                    standart = Decimal(str(pay)) / Decimal(str(payda))
                    fark = abs(oran_orani - standart)
                    if fark < en_kucuk_fark:
                        en_kucuk_fark = fark
                        en_yakin = (pay, payda)

                ok = en_kucuk_fark <= TEVKIFAT_ORAN_TOLERANS
                oran_yuzde = (oran_orani * 100).quantize(Decimal("0.1"))
                if en_yakin:
                    standart_yuzde = (Decimal(str(en_yakin[0])) /
                                      Decimal(str(en_yakin[1])) * 100).quantize(Decimal("0.1"))
                else:
                    standart_yuzde = Decimal("0")

                sonuclar.append({
                    "ok": ok,
                    "kural": "tevkifat_orani",
                    "text": (f"Tevkifat orani (%{oran} matrah {_tutarli(o_matrah)}) — "
                             f"{_tutarli(bu_orana_dusen_tevkifat)} / {_tutarli(tam_kdv)} = "
                             f"%{oran_yuzde}"
                             + (f" -> standart {en_yakin[0]}/{en_yakin[1]}"
                                f" (%{standart_yuzde}) uyuyor"
                                if ok else
                                f" -> STANDART DEGIL (en yaklasik "
                                f"{en_yakin[0]}/{en_yakin[1]}=%{standart_yuzde})"))
                })

    # ── Bilgi: Olası iskonto ──
    if matrah is not None and toplam is not None:
        # Mal/Hizmet (toplam - kdv - diger_vergi) vs matrah
        mal_hizmet = toplam - kdv - diger_vergi if kdv else None
        if mal_hizmet is not None and mal_hizmet > matrah:
            fark = mal_hizmet - matrah
            sonuclar.append({
                "ok": True,
                "kural": "olasi_iskonto",
                "text": (f"Olasi iskonto: Toplam KDV dahil - KDV - Diger Vergi "
                         f"({_tutarli(mal_hizmet)}) - Matrah ({_tutarli(matrah)}) "
                         f"= {_tutarli(fark)} (tahmin, kesin degil)")
            })

    # Hiç kontrol çalışmadıysa
    if not sonuclar:
        sonuclar.append({
            "ok": True,
            "kural": "yetersiz_veri",
            "text": "Doğrulama için yeterli tutar verisi bulunamadı."
        })

    return sonuclar


def tevkifat_hesapla(toplam, odenecek):
    """Vergiler Dahil Toplam - Ödenecek Tutar = Tevkifat.

    Returns: Decimal veya None
    """
    t = _parse_tutar(toplam)
    o = _parse_tutar(odenecek)
    if t is None or o is None:
        return None
    fark = t - o
    return fark if fark > 0 else Decimal("0")


def ozet_raporu_yaz(kayitlar, dosya_yolu=None):
    """Birden fazla fatura için özet rapor üretir.

    Returns: dict — {
        "toplam_fatura": int,
        "basarili": int,
        "hatali": int,
        "sonuclar": [{"belge_no": str, "kontroller": list}, ...]
    }
    """
    rapor = {
        "toplam_fatura": len(kayitlar),
        "basarili": 0,
        "hatali": 0,
        "sonuclar": [],
    }
    for kayit in kayitlar:
        belge_no = kayit.get("belge_no", "?")
        sonuclar = faturayi_dogrula(kayit)
        hatali = [s for s in sonuclar if not s["ok"]]
        if hatali:
            rapor["hatali"] += 1
        else:
            rapor["basarili"] += 1
        rapor["sonuclar"].append({
            "belge_no": belge_no,
            "kontroller": sonuclar,
        })
    return rapor
