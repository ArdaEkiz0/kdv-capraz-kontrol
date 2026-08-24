import os
import zipfile

from cetvel import cetvel_parse
from efatura import efatura_parse
from excel_oku import (cetvel_excel_parse, fatura_excel_parse, fatura_gelen_parse,
                       fatura_gib_arsiv_liste_parse, muavin_excel_parse,
                       muavin_191_parse, muavin_391_parse, muavin_zenom_parse,
                       muavin_genel_parse)
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
        sonuc = fatura_gib_arsiv_liste_parse(dosya_yolu)
        if sonuc is not None:
            return sonuc
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
    """Gerçek mükerrer fatura kopyalarını tek kayıda indirir.

    Aynı faturanın birden fazla XML dosyasında bulunması (iki kez indirme /
    düzeltme kopyası) "iki kez taranıp mükerrer gösterimi" yaratıyordu.
    İçeriği birebir aynı olan kopyalar (belge + tarih + VKN + matrah + kdv +
    toplam) tekilleştirilir.

    Aynı belge numarasını farklı tarih/tutarda kullanan FARKLI faturalar
    (belge numarası çakışması) ise ayrı kalır; bunları toplamak yanlış
    eşleşmeye yol açıyordu. Her biri kendi muavin kaydıyla eşleşir.
    """
    from decimal import Decimal

    def _esit(a, b):
        if a is None and b is None:
            return True
        if a is None or b is None:
            return False
        try:
            return abs(a - b) < Decimal("0.005")
        except TypeError:
            return str(a) == str(b)

    gruplar = {}
    sonuc = []
    for k in faturalar:
        anahtar = (k["belge_no"] or "").upper()
        if not anahtar:
            sonuc.append(k)
            continue
        imza = (k.get("tarih") or "", k.get("satici_vkn") or "")
        liste = gruplar.setdefault(anahtar, [])
        for kayit in liste:
            g = kayit["g"]
            if imza == kayit["imza"] \
                    and _esit(g.get("matrah"), k.get("matrah")) \
                    and _esit(g.get("kdv"), k.get("kdv")) \
                    and _esit(g.get("toplam"), k.get("toplam")):
                for n in k.get("notlar") or []:
                    if n not in g["notlar"]:
                        g["notlar"].append(n)
                break
        else:
            g = dict(k)
            g["notlar"] = list(k.get("notlar") or [])
            liste.append({"g": g, "imza": imza})
            sonuc.append(g)
    return sonuc


def _guvenli_parse(parse_fn, dosya_yolu):
    """Parser çökerse uygulama durmasın; notla boş sonuç dönsün."""
    try:
        return parse_fn(dosya_yolu)
    except Exception as hata:
        return {"dosya": dosya_yolu, "kayitlar": [], "notlar": [
            f"{parse_fn.__name__} hata verdi: {hata}"]}


def _kullanilabilir_mi(sonuc):
    """Parser sonucu gerçekten eşleşmede kullanılabilir mi?

    Belge numarası ve tutarı olan en az bir kayıt ararız; yoksa o parser
    bu dosyayı tanımamış sayılır ve sıradaki denemeye geçilir.
    """
    if not sonuc or not sonuc.get("kayitlar"):
        return False
    for k in sonuc["kayitlar"]:
        if k.get("belge_no") and k.get("kdv"):
            return True
    return False


def cetvel_dosya_parse(dosya_yolu):
    uzanti = os.path.splitext(dosya_yolu)[1].lower()
    if uzanti in EXCEL_UZANTILARI:
        dzenom = _guvenli_parse(muavin_zenom_parse, dosya_yolu)
        if _kullanilabilir_mi(dzenom):
            return dzenom
        d191 = _guvenli_parse(muavin_191_parse, dosya_yolu)
        if _kullanilabilir_mi(d191):
            return d191
        d391 = _guvenli_parse(muavin_391_parse, dosya_yolu)
        if _kullanilabilir_mi(d391):
            return d391
        sonuc = _guvenli_parse(cetvel_excel_parse, dosya_yolu)
        if not _kullanilabilir_mi(sonuc):
            muavin = _guvenli_parse(muavin_excel_parse, dosya_yolu)
            if _kullanilabilir_mi(muavin):
                return muavin
        if not _kullanilabilir_mi(sonuc):
            # Bilinen formatlardan hiçbiri tanımadıysa genel otomatik
            # tanıma devreye girer (yeni cetvel türleri için).
            genel = _guvenli_parse(muavin_genel_parse, dosya_yolu)
            if _kullanilabilir_mi(genel):
                return genel
        return sonuc
    if uzanti in PDF_UZANTILARI:
        try:
            sonuc = fis_listesi_cetvel_parse(dosya_yolu)
            if sonuc is not None:
                return sonuc
        except Exception:
            pass
    return cetvel_parse(dosya_yolu)

def faturalari_toplu_parse(dosyalar, ilerleme=None, iptal=None,
                           isci_sayisi=None, fis_parse_fn=None):
    """Fatura listesini paralel okur. Donus:
    {"faturalar": [...], "fis_hesap_kayitlari": [...], "hatalar": [(yol, hata)]}

    ilerleme(tamamlanan, toplam, dosya_adi, hata) her dosya bitisinde cagrilir.
    iptal (threading.Event) set edilir kalan isler dusurulur.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    dosyalar = list(dosyalar)
    toplam = len(dosyalar)
    fatura_sonuclari = [None] * toplam
    fis_sonuclari = [None] * toplam
    hata_listesi = [None] * toplam

    def tek_is(indeks, yol):
        fatura = []
        fis = None
        try:
            fatura = fatura_dosya_parse(yol)
        except Exception as hata:
            hata_listesi[indeks] = (yol, str(hata))
        if fis_parse_fn is not None and yol.lower().endswith(".pdf"):
            try:
                fis = fis_parse_fn(yol) or None
            except Exception:
                fis = None
        return indeks, fatura, fis

    isci = max(1, isci_sayisi or min(4, os.cpu_count() or 4))
    tamamlanan = 0
    with ThreadPoolExecutor(max_workers=isci) as havuz:
        gelecekler = [havuz.submit(tek_is, i, y) for i, y in enumerate(dosyalar)]
        for g in as_completed(gelecekler):
            indeks, fatura, fis = g.result()
            fatura_sonuclari[indeks] = fatura or []
            fis_sonuclari[indeks] = fis
            tamamlanan += 1
            if ilerleme is not None:
                try:
                    ilerleme(tamamlanan, toplam,
                             os.path.basename(dosyalar[indeks]), hata_listesi[indeks])
                except Exception:
                    pass
            if iptal is not None and iptal.is_set():
                for kalan in gelecekler:
                    kalan.cancel()
                break

    faturalar = []
    for liste in fatura_sonuclari:
        faturalar.extend(liste or [])
    fisler = []
    for liste in fis_sonuclari:
        if liste:
            fisler.extend(liste)
    return {"faturalar": faturalar, "fis_hesap_kayitlari": fisler,
            "hatalar": [h for h in hata_listesi if h]}
