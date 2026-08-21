import os
import zipfile

from cetvel import cetvel_parse
from efatura import efatura_parse
from excel_oku import (cetvel_excel_parse, fatura_excel_parse, fatura_gelen_parse,
                       muavin_excel_parse, muavin_191_parse, muavin_391_parse)
from fis_listesi import fis_listesi_cetvel_parse, fis_listesi_parse
from xml_oku import fatura_xml_parse

EXCEL_UZANTILARI = (".xlsx", ".xlsm", ".xls")
PDF_UZANTILARI = (".pdf",)
XML_UZANTILARI = (".xml",)
ZIP_UZANTILARI = (".zip",)


def _zip_xml_faturalar(zip_yolu):
    """Zip arşiv içindeki e-fatura XML'lerini okuyup birleştirir.

    (örn. GEDİZ ELEKTRİK XML Fatura Listesi). Arşivde XML yoksa None döner.
    """
    import tempfile
    sonuc = []
    try:
        arsiv = zipfile.ZipFile(zip_yolu)
    except Exception:
        return None
    xml_listesi = [n for n in arsiv.namelist() if n.lower().endswith(".xml")]
    if not xml_listesi:
        return None
    gecici = tempfile.mkdtemp()
    try:
        for n in xml_listesi:
            try:
                ham = arsiv.read(n)
            except Exception:
                continue
            yol = os.path.join(gecici, os.path.basename(n))
            with open(yol, "wb") as f:
                f.write(ham)
            for kayit in fatura_xml_parse(yol):
                kayit["kaynak_zip"] = os.path.basename(zip_yolu)
                sonuc.append(kayit)
    finally:
        import shutil
        shutil.rmtree(gecici, ignore_errors=True)
    return sonuc


def fatura_dosya_parse(dosya_yolu):
    uzanti = os.path.splitext(dosya_yolu)[1].lower()
    if uzanti in ZIP_UZANTILARI or (uzanti == "" and _zip_mi(dosya_yolu)):
        sonuc = _zip_xml_faturalar(dosya_yolu)
        if sonuc is not None:
            return sonuc
    if uzanti in EXCEL_UZANTILARI:
        sonuc = fatura_gelen_parse(dosya_yolu)
        if sonuc is not None:
            return sonuc
        return fatura_excel_parse(dosya_yolu)
    if uzanti in XML_UZANTILARI:
        return fatura_xml_parse(dosya_yolu)
    if uzanti in PDF_UZANTILARI:
        sonuc = fis_listesi_parse(dosya_yolu)
        if sonuc is not None:
            return sonuc
    return efatura_parse(dosya_yolu)


def _zip_mi(dosya_yolu):
    try:
        with open(dosya_yolu, "rb") as f:
            return f.read(4) == b"PK\x03\x04"
    except Exception:
        return False


def fatura_birlestir(faturalar):
    """Aynı belge numarasına sahip faturaları tek kayıtta birleştirir.

    Muavin tarafında (_muavin_birlestir) aynı belge numarası tek satıra
    toplanırken, fatura XML'lerinde aynı belge birden fazla dosyada
    (düzeltme/zeyil/parça) bulunabildığı için burada da kdv/matrah/toplam
    toplanıp tek faturaya indirilir. Böylece çapraz kontrolde "iki kez
    taranıp" mükerrer/tutar farkı gösterilmesinin önüne geçilir.
    """
    from decimal import Decimal
    gruplar = {}
    for k in faturalar:
        anahtar = (k["belge_no"] or "").upper()
        if not anahtar:
            gruplar[id(k)] = k
            continue
        if anahtar in gruplar:
            g = gruplar[anahtar]
            for alan in ("matrah", "kdv", "toplam"):
                gd = g.get(alan)
                kd = k.get(alan)
                if gd is None:
                    g[alan] = kd
                elif kd is not None:
                    g[alan] = gd + kd
            for n in k.get("notlar") or []:
                if n not in g["notlar"]:
                    g["notlar"].append(n)
            if g.get("tarih") is None and k.get("tarih"):
                g["tarih"] = k["tarih"]
        else:
            g = dict(k)
            g["notlar"] = list(k.get("notlar") or [])
            gruplar[anahtar] = g
    sonuc = []
    for g in gruplar.values():
        for alan in ("matrah", "kdv", "toplam"):
            if g.get(alan) is not None:
                g[alan] = g[alan].quantize(Decimal("0.01"))
        sonuc.append(g)
    return sonuc


def cetvel_dosya_parse(dosya_yolu):
    uzanti = os.path.splitext(dosya_yolu)[1].lower()
    if uzanti in EXCEL_UZANTILARI:
        d191 = muavin_191_parse(dosya_yolu)
        if d191["kayitlar"]:
            return d191
        d391 = muavin_391_parse(dosya_yolu)
        if d391["kayitlar"]:
            return d391
        sonuc = cetvel_excel_parse(dosya_yolu)
        if not sonuc["kayitlar"]:
            muavin = muavin_excel_parse(dosya_yolu)
            if muavin["kayitlar"]:
                return muavin
        return sonuc
    if uzanti in PDF_UZANTILARI:
        sonuc = fis_listesi_cetvel_parse(dosya_yolu)
        if sonuc is not None:
            return sonuc
    return cetvel_parse(dosya_yolu)
