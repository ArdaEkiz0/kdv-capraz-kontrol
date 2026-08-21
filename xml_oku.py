import gzip
import io
import xml.etree.ElementTree as ET
from decimal import Decimal, ROUND_HALF_UP

from utils import fatura_no_temizle, tarih_parse, tutar_parse, vkn_temizle


def _xml_tutar(deger):
    if deger is None:
        return None
    metin = str(deger).strip().replace(" ", "")
    if not metin:
        return None
    try:
        d = Decimal(metin)
    except Exception:
        return tutar_parse(metin)
    if not d.is_finite():
        return None
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _yerel_ad(etiket):
    if "}" in etiket:
        return etiket.split("}", 1)[1]
    return etiket


def _elemanlar(kok, yerel_ad):
    return [e for e in kok.iter() if _yerel_ad(e.tag) == yerel_ad]


def _metin(eleman):
    if eleman is None or eleman.text is None:
        return None
    return eleman.text.strip()


def _alt_eleman(kok, ust_ad, alt_ad):
    for e in kok.iter():
        if _yerel_ad(e.tag) == ust_ad:
            for a in e.iter():
                if _yerel_ad(a.tag) == alt_ad:
                    return a
    return None


def _dogrudan(kok, yerel_ad):
    return [e for e in kok if _yerel_ad(e.tag) == yerel_ad]


def _icerikleri_oku(ham_veri):
    kok = ET.fromstring(ham_veri)

    belge = None
    for e in _dogrudan(kok, "ID"):
        belge = _metin(e)
        break
    belge = fatura_no_temizle(belge)

    tarih = None
    for e in _elemanlar(kok, "IssueDate"):
        tarih = tarih_parse(_metin(e))
        break

    satici = _alt_eleman(kok, "AccountingSupplierParty", "ID")
    alici = _alt_eleman(kok, "AccountingCustomerParty", "ID")
    satici_vkn = vkn_temizle(_metin(satici))
    alici_vkn = vkn_temizle(_metin(alici))

    satici_unvan = ""
    for e in _elemanlar(kok, "AccountingSupplierParty"):
        for a in _dogrudan(e, "Party"):
            ad = _alt_eleman(a, "PartyName", "Name")
            if ad is not None and _metin(ad):
                satici_unvan = _metin(ad)
                break
            ad = _alt_eleman(a, "PartyLegalEntity", "RegistrationName")
            if ad is not None and _metin(ad):
                satici_unvan = _metin(ad)
                break
    satici_unvan = (satici_unvan or "").strip()

    matrah = None
    vergi_haric = _elemanlar(kok, "TaxExclusiveAmount")
    if vergi_haric:
        matrah = _xml_tutar(_metin(vergi_haric[0]))
    if matrah is None:
        satir_toplam = _elemanlar(kok, "LineExtensionAmount")
        if satir_toplam:
            toplam_satir = sum((_xml_tutar(_metin(e)) or Decimal("0")) for e in satir_toplam)
            if toplam_satir:
                matrah = toplam_satir.quantize(Decimal("0.01"))

# Özel indirim (AllowanceCharge, charge=false) — matrahı düşülmüş indirim
    # tutarını ayrı tutup, fatura dikkate alınması için kayıtta saklar.
    indirim_toplam = Decimal("0")
    for e in kok.iter():
        if _yerel_ad(e.tag) != "AllowanceCharge":
            continue
        ind = None
        amt = None
        for a in e.iter():
            n = _yerel_ad(a.tag)
            if n == "ChargeIndicator" and ind is None:
                ind = _metin(a)
            elif n == "Amount" and amt is None:
                amt = _xml_tutar(_metin(a))
        if ind is None or amt is None:
            continue
        if ind.strip().lower() == "false":
            indirim_toplam += amt
    indirim_toplam = indirim_toplam.quantize(Decimal("0.01"))

    vergi_totalleri = _dogrudan(kok, "TaxTotal")
    belge_vergi = vergi_totalleri[0] if vergi_totalleri else None
    belge_vergi = vergi_totalleri[0] if vergi_totalleri else None

    # Saf KDV (kod 0015) ve diğer vergileri (OİV/TRT vb.) ayrıştır.
    # Kontroli — KDV hesabı sadece 0015 üzerinden olmalı, OİV katılmameli.
    kdv = None
    diger_vergi_toplam = Decimal("0")
    kdv_ayrik = None
    if belge_vergi is not None:
        for e in belge_vergi.iter():
            if _yerel_ad(e.tag) != "TaxSubtotal":
                continue
            kod = ""
            amt = None
            for a in e.iter():
                n = _yerel_ad(a.tag)
                if n == "TaxTypeCode":
                    kod = (_metin(a) or "").strip()
                elif n == "TaxAmount" and amt is None:
                    amt = _xml_tutar(_metin(a))
            if amt is None:
                continue
            if kod == "0015" or (kod == "" and kdv is None):
                if kdv_ayrik is None:
                    kdv_ayrik = Decimal("0")
                kdv_ayrik += amt
            else:
                diger_vergi_toplam += amt
        if kdv_ayrik is not None:
            kdv = kdv_ayrik.quantize(Decimal("0.01"))
    if kdv is None:
        vergi_toplam = _elemanlar(kok, "TaxAmount")
        if vergi_toplam:
            kdv = _xml_tutar(_metin(vergi_toplam[0]))
    diger_vergi_toplam = diger_vergi_toplam.quantize(Decimal("0.01"))

    toplam = None
    vergi_dahil = _elemanlar(kok, "TaxInclusiveAmount")
    if vergi_dahil:
        toplam = _xml_tutar(_metin(vergi_dahil[0]))
    if toplam is None:
        odenecek = _elemanlar(kok, "PayableAmount")
        if odenecek:
            toplam = _xml_tutar(_metin(odenecek[0]))

    oranlar = []
    if belge_vergi is not None:
        # KDV kod (0015 veya kod boş) oranlarina ayır
        for e in belge_vergi.iter():
            if _yerel_ad(e.tag) != "TaxSubtotal":
                continue
            kod = ""
            oran_o = None
            for a in e.iter():
                n = _yerel_ad(a.tag)
                if n == "TaxTypeCode":
                    kod = (_metin(a) or "").strip()
                elif n == "Percent" and oran_o is None:
                    oran_o = _xml_tutar(_metin(a))
            if oran_o is None:
                continue
            if kod and kod != "0015":
                continue
            o = int(oran_o)
            if o > 0:
                oranlar.append(o)
    oranlar = sorted(set(oranlar))

    tip = ""
    for e in _elemanlar(kok, "InvoiceTypeCode"):
        tip = (_metin(e) or "").strip().upper()
        break
    TIP_ADLARI = {
        "SATIS": "SATIS", "IADE": "IADE", "OZELMATRAH": "OZEL MATRAH",
        "TEVKIFAT": "TEVKIFAT", "ISTISNA": "ISTISNA", "IMALAT": "IMALAT",
    }
    tip = TIP_ADLARI.get(tip, tip or "")

    vergi_detay = []
    if belge_vergi is not None:
        for e in belge_vergi.iter():
            if _yerel_ad(e.tag) == "TaxSubtotal":
                satir = {"oran": None, "matrah": None, "kdv": None, "muafiyet": None,
                         "ad": None, "kod": None}
                for a in e.iter():
                    n = _yerel_ad(a.tag)
                    if n == "Percent":
                        o = _xml_tutar(_metin(a))
                        if o is not None:
                            satir["oran"] = int(o)
                    elif n == "TaxableAmount":
                        satir["matrah"] = _xml_tutar(_metin(a))
                    elif n == "TaxAmount":
                        satir["kdv"] = _xml_tutar(_metin(a))
                    elif n == "TaxExemptionReason":
                        satir["muafiyet"] = _metin(a)
                    elif n == "TaxTypeCode":
                        satir["kod"] = (_metin(a) or "").strip()
                    elif n == "Name" and satir["ad"] is None:
                        metin = (_metin(a) or "").strip()
                        if metin and not any(k in metin.upper() for k in ("SUPPLIER", "CUSTOMER", "ACCOUNTING")):
                            satir["ad"] = metin
                if satir["kdv"] is not None:
                    if satir["ad"] is None and satir["kod"]:
                        satir["ad"] = "KDV" if satir["kod"] == "0015" else f"Vergi ({satir['kod']})"
                    vergi_detay.append(satir)

    # Saf KDV (0015) ve diğer vergileri ayrıştır
    kdv_ayrik = None
    diger_vergi_toplam = Decimal("0")
    for st in vergi_detay:
        if st.get("kod") == "0015" or (st.get("ad") or "").upper().startswith("KDV"):
            if kdv_ayrik is None:
                kdv_ayrik = Decimal("0")
            kdv_ayrik += st["kdv"] or Decimal("0")
        else:
            diger_vergi_toplam += st["kdv"] or Decimal("0")
    if kdv_ayrik is not None:
        kdv_ayrik = kdv_ayrik.quantize(Decimal("0.01"))
    diger_vergi_toplam = diger_vergi_toplam.quantize(Decimal("0.01"))

    # Sektör tanıma (telekom / elektrik)
    sektor = ""
    unvan_ust = satici_unvan.upper()
    TELEKOM_ANAHTAR = ("TURKCELL", "VODAFONE", "TURK TELEKOM", "TTNET", "AVEA",
                       "TURKCELL ILETISIM", "VODAFONE TELEKOM")
    ELEKTRIK_ANAHTAR = ("ELEKTRIK", "ELEKTRİK", "GEDIZ", "GEDİZ", "AKSA", "TOROSLAR EDA",
                        "AYDED", "ULUDAG ELEKTRIK", "KOLIN", "ENERJISA")
    for a in TELEKOM_ANAHTAR:
        if a in unvan_ust:
            sektor = "TELECOM"
            break
    if not sektor:
        for a in ELEKTRIK_ANAHTAR:
            if a in unvan_ust:
                sektor = "ELEKTRIK"
                break

    notlar = []
    oran_kontrol = ""
    if tip in ("SATIS", "IADE") and len(oranlar) == 1 and matrah is not None and kdv is not None:
        beklenen = (matrah * Decimal(oranlar[0]) / Decimal("100")).quantize(Decimal("0.01"))
        if abs(beklenen - kdv) > Decimal("0.02"):
            oran_kontrol = "FARK"
            notlar.append(f"Matrah×Oran ≠ KDV (beklenen {beklenen})")
        else:
            oran_kontrol = "OK"
    elif tip in ("SATIS", "IADE") and len(oranlar) > 1:
        oran_kontrol = "COK ORANLI"
    if matrah is None or kdv is None:
        notlar.append("Matrah/KDV tutarları bulunamadı, manuel kontrol edin")
    elif toplam is not None:
        beklenen = (matrah + kdv + diger_vergi_toplam).quantize(Decimal("0.01"))
        if abs(beklenen - toplam) > Decimal("0.02"):
            notlar.append("Matrah+KDV ≠ Toplam (XML tutarları tutarsız görünüyor)")

    return {
        "belge_no": belge,
        "tarih": tarih,
        "satici_vkn": satici_vkn,
        "alici_vkn": alici_vkn,
        "satici_unvan": satici_unvan,
        "matrah": matrah,
        "kdv": kdv,
        "toplam": toplam,
        "indirim_toplam": indirim_toplam,
        "oranlar": oranlar,
        "fatura_tipi": tip,
        "vergi_detay": vergi_detay,
        "kdv_ayrik": kdv_ayrik,
        "diger_vergi_toplam": diger_vergi_toplam,
        "sektor": sektor,
        "oran_kontrol": oran_kontrol,
        "notlar": notlar,
    }


def fatura_xml_parse(dosya_yolu):
    try:
        with open(dosya_yolu, "rb") as f:
            ham = f.read()
        try:
            icerik = _icerikleri_oku(ham)
        except ET.ParseError:
            try:
                icerik = _icerikleri_oku(gzip.decompress(ham))
            except Exception:
                icerik = None
        if icerik is None:
            raise ValueError("XML çözümlenemedi")
    except Exception as hata:
        return [{
            "dosya": dosya_yolu, "tip": "xml", "sayfa": 1,
            "belge_no": None, "tarih": None, "satici_vkn": None, "alici_vkn": None,
            "matrah": None, "kdv": None, "toplam": None, "oranlar": [],
            "notlar": [f"XML okunamadı: {hata}"],
        }]
    icerik["dosya"] = dosya_yolu
    icerik["tip"] = "xml"
    icerik["sayfa"] = 1
    return [icerik]
