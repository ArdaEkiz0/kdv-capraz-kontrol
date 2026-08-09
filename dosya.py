import os

from cetvel import cetvel_parse
from efatura import efatura_parse
from excel_oku import cetvel_excel_parse, fatura_excel_parse, muavin_excel_parse
from xml_oku import fatura_xml_parse

EXCEL_UZANTILARI = (".xlsx", ".xlsm", ".xls")
PDF_UZANTILARI = (".pdf",)
XML_UZANTILARI = (".xml",)


def fatura_dosya_parse(dosya_yolu):
    uzanti = os.path.splitext(dosya_yolu)[1].lower()
    if uzanti in EXCEL_UZANTILARI:
        return fatura_excel_parse(dosya_yolu)
    if uzanti in XML_UZANTILARI:
        return fatura_xml_parse(dosya_yolu)
    return efatura_parse(dosya_yolu)


def cetvel_dosya_parse(dosya_yolu):
    uzanti = os.path.splitext(dosya_yolu)[1].lower()
    if uzanti in EXCEL_UZANTILARI:
        sonuc = cetvel_excel_parse(dosya_yolu)
        if not sonuc["kayitlar"]:
            muavin = muavin_excel_parse(dosya_yolu)
            if muavin["kayitlar"]:
                return muavin
        return sonuc
    return cetvel_parse(dosya_yolu)
