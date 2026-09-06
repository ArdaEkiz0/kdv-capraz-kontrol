"""Regresyon testi: paralel ZIP indirme sarmalı (luca_cekme).

`_zip_tek_indir_hizli` / `_zip_hizli_toplu_indir` sıralı `_zip_tikla_indir`
çekimini hızlandırmak için eklenen paralel HTTP yoludur. Bu test, sahte
frame/sayfa + sahte `urllib.urlopen` ile:

  1. oturum sabitlerinin (sirket_id, donem_id, gib kullanıcı/şifre, çerez)
     tek turda toplandığını,
  2. POST gövdesinin orijinal `_zip_tikla_indir` sarmalıyla aynı biçimde
     (JSON: {sirket_id, donem_id, params{...ettn...}}) kurulduğunu,
  3. ZIP yanıtının doğru yazılıp UBL özetinin (matrah/KDV/toplam/para)
     belge dict'ine işlendiğini,
  4. çoklu belgenin ThreadPoolExecutor'da hatasız indiğini,
  5. HTTP hatasının temiz RuntimeException'a dönüştüğünü

doğrular. Canlı Luca oturumu gerektirmez.
"""
import io
import os
import sys
import urllib.error
import urllib.request
import zipfile

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

YOL = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, YOL)

import luca_cekme  # noqa: E402

LUKA_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" '
    'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:'
    'CommonBasicComponents-2" '
    'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:'
    'CommonAggregateComponents-2">'
    '<cac:TaxTotal><cbc:TaxAmount currencyID="TRY">143.10</cbc:TaxAmount>'
    '<cac:TaxSubtotal>'
    '<cbc:TaxableAmount currencyID="TRY">1430.97</cbc:TaxableAmount>'
    '<cbc:Percent>10</cbc:Percent>'
    '<cbc:TaxAmount currencyID="TRY">143.10</cbc:TaxAmount>'
    '</cac:TaxSubtotal></cac:TaxTotal>'
    '<cac:LegalMonetaryTotal>'
    '<cbc:TaxExclusiveAmount currencyID="TRY">1430.97'
    '</cbc:TaxExclusiveAmount>'
    '<cbc:TaxInclusiveAmount currencyID="TRY">1574.07'
    '</cbc:TaxInclusiveAmount>'
    '<cbc:PayableAmount currencyID="TRY">1574.07'
    '</cbc:PayableAmount></cac:LegalMonetaryTotal>'
    '</Invoice>'
)

BASARILI = True


def kontrol(ad, kosul, detay=""):
    global BASARILI
    durum = "TAMAM" if kosul else "HATA"
    if not kosul:
        BASARILI = False
    print(f"  [{durum}] {ad} {detay}")


def _zip_uret():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("fatura.xml", LUKA_XML)
    return buf.getvalue()


class _SanliYanit:
    def __init__(self, veri):
        self._v = veri
        self.status = 200

    def read(self):
        return self._v

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


# --- Sahte tarayıcı katmanı ---
captured = {}


class FakeCerceve:
    def evaluate(self, js, *args):
        if "menu_tur" in js:
            return "gib_efatura_alis"
        if "SIRKET_ID" in js:
            return "1234"
        if "DONEM_ID" in js:
            return "5678"
        if "gib_kullanici_adi" in js:
            return "kkk"
        if "gib_sifre" in js:
            return "sss"
        return None


class FakeSayfa:
    url = "https://auygs.luca.com.tr/Luca/gib530.do?tur=efatura_alis"

    class context:
        @staticmethod
        def cookies():
            return [{"name": "JSESSIONID", "value": "OTURUM123"},
                    {"name": "other", "value": "v"}]


def _sahte_urlopen(istek, timeout=None):
    captured["url"] = istek.full_url
    captured["body"] = istek.data.decode("utf-8")
    captured["headers"] = dict(istek.headers)
    return _SanliYanit(_zip_uret())


def _sayacli_urlopen(istek, timeout=None):
    captured["sayac"] = captured.get("sayac", 0) + 1
    return _sahte_urlopen(istek, timeout=timeout)


def test_oturum_bilgisi():
    ot = luca_cekme._zip_oturum_bilgisi(FakeCerceve(), FakeSayfa(),
                                        "efatura_alis")
    kontrol("menü türü doğru url",
            ot["url"].endswith("/gib530/gib_efatura_alis.jq"),
            ot["url"])
    kontrol("sirket/donem okundu",
            ot["sirket_id"] == "1234" and ot["donem_id"] == "5678")
    kontrol("gib kullanıcı/sifre okundu",
            ot["gkk"] == "kkk" and ot["gks"] == "sss")
    kontrol("çerez başlığı kuruldu",
            "JSESSIONID=OTURUM123" in ot["cookie"], ot["cookie"])
    return ot


def test_tek_indir(ot):
    belge = {
        "ettn": "d2815be8-383f-43c1-8abc",
        "belge_numarasi": "A022026260557307",
        "belge_turu": "FATURA",
        "onay_durumu": "Onaylandı",
        "bayi_no": "7",
        "url": "gib_efatura_alis.jq?ettn=x",
    }
    zip_yol = os.path.join(YOL, "_test_paralel.zip")
    try:
        luca_cekme._zip_tek_indir_hizli(ot, belge, zip_yol, YOL)
    finally:
        pass
    kontrol("ZIP dosyası yazıldı ve geçerli",
            os.path.exists(zip_yol) and zipfile.is_zipfile(zip_yol))
    kontrol("POST gövdesi JSON ve ettn içeriyor",
            captured.get("body") and
            "d2815be8-383f-43c1-8abc" in captured["body"] and
            captured["body"].lstrip().startswith("{"))
    kontrol("sirket_id sarmalda",
            'sirket_id": "1234' in captured.get("body", ""))
    kontrol("belge UBL özetiyle zenginleşti",
            belge.get("matrah") == 1430.97 and
            belge.get("kdv_toplam") == 143.10 and
            belge.get("genel_toplam") == 1574.07 and
            belge.get("para") == "TRY",
            f"matrah={belge.get('matrah')}")
    kontrol("oran kalemleri dolduruldu",
            isinstance(belge.get("oran_kalemleri"), list)
            and belge.get("oran_kalemleri"))
    if os.path.exists(zip_yol):
        os.remove(zip_yol)
    return belge


def test_toplu_paralel(ot):
    plan = []
    for i in range(6):
        plan.append(({
            "ettn": f"ettn-{i}",
            "belge_numarasi": f"B{i:08d}",
            "belge_turu": "FATURA",
        }, os.path.join(YOL, f"_test_p_{i}.zip")))
    captured["sayac"] = 0
    hatalar = luca_cekme._zip_hizli_toplu_indir(
        FakeCerceve(), FakeSayfa(), plan, "efatura_alis", klasor=YOL,
        esler=4)
    kontrol("6 belge de indirildi, hata yok",
            not hatalar, f"hatalar={hatalar}")
    inen = [p for _, p in plan if os.path.exists(p)]
    kontrol("hepsi zip olarak inmiş", len(inen) == 6)
    kontrol("toplu paralel POST sayısı 6", captured.get("sayac", 0) == 6)
    for _, p in plan:
        if os.path.exists(p):
            os.remove(p)


def test_hata_durumu(ot):
    plan = [({"ettn": "x-1", "belge_numarasi": "H1"},
             os.path.join(YOL, "_test_h.zip"))]

    def _hata_veren(istek, timeout=None):
        raise urllib.error.HTTPError(istek.full_url, 503, "Servis yok",
                                     {}, None)

    eski = urllib.request.urlopen
    urllib.request.urlopen = _hata_veren
    try:
        try:
            luca_cekme._zip_tek_indir_hizli(ot, plan[0][0], plan[0][1], YOL)
            kontrol("hata beklenirken indi", False)
        except Exception as e:
            kontrol("HTTP hatası temiz içerir",
                    "HTTP 503" in str(e), str(e)[:80])
    finally:
        urllib.request.urlopen = eski
    if os.path.exists(plan[0][1]):
        os.remove(plan[0][1])


if __name__ == "__main__":
    urllib.request.urlopen = _sayacli_urlopen
    print("== paralel zip sarmalı (offline) ==")
    ot = test_oturum_bilgisi()
    test_tek_indir(ot)
    test_toplu_paralel(ot)
    test_hata_durumu(ot)
    print()
    print("SONUÇ: TÜM TESTLER TAMAM" if BASARILI
          else "SONUÇ: BAŞARISIZ")
    sys.exit(0 if BASARILI else 1)