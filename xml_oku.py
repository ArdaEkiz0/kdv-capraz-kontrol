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

    vergi_totalleri = _dogrudan(kok, "TaxTotal")
    belge_vergi = vergi_totalleri[0] if vergi_totalleri else None

    kdv = None
    if belge_vergi is not None:
        toplam = Decimal("0")
        for e in belge_vergi.iter():
            if _yerel_ad(e.tag) == "TaxSubtotal":
                ic = [a for a in e.iter() if _yerel_ad(a.tag) == "TaxAmount"]
                if ic:
                    toplam += _xml_tutar(_metin(ic[0])) or Decimal("0")
        if toplam:
            kdv = toplam.quantize(Decimal("0.01"))
    if kdv is None:
        vergi_toplam = _elemanlar(kok, "TaxAmount")
        if vergi_toplam:
            kdv = _xml_tutar(_metin(vergi_toplam[0]))

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
        for e in belge_vergi.iter():
            if _yerel_ad(e.tag) == "Percent":
                o = _xml_tutar(_metin(e))
                if o is not None and o > 0:
                    oranlar.append(int(o))
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
                satir = {"oran": None, "matrah": None, "kdv": None, "muafiyet": None}
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
                if satir["kdv"] is not None:
                    vergi_detay.append(satir)

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
        beklenen = (matrah + kdv).quantize(Decimal("0.01"))
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
        "oranlar": oranlar,
        "fatura_tipi": tip,
        "vergi_detay": vergi_detay,
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
