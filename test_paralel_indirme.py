"""Regresyon testi: sayfa-içi paralel ZIP indirme sarmalı (luca_cekme).

Canlı deney öğretti: doğrudan urllib POST, Luca sunucusu tarafından TLS
parmak izi yüzünden reddediliyor. Bu yüzden paralellik sayfanın kendi
origin'inde 8 işçili fetch havuzu (`_zip_hizli_toplu_indir`) ile yapılır.
Bu test sahte frame/sayfa ile şunları doğrular:

  1. oturum sabitlerinin (sirket_id, donem_id, gib kullanıcı/şifre, çerez)
     tek turda toplandığını,
  2. `_zip_body_uret` POST gövdesinin `_zip_tikla_indir` sarmalıyla aynı
     anahtarları taşıdığını (islem/ettn/bayiNo/...),
  3. sahte `evaluate`'ün döndürdüğü base64 ZIP'lerin doğru yazılıp UBL
     özetinin (matrah/KDV/toplam/para) belge dict'ine işlendiğini,
  4. çoklu belgenin tek evaluate turunda 6/6 hatasız indiğini,
  5. değerli yanıt dönmeyen (ör. 503 ya da sayfa gitti) durumlarda belgenin
     `{zip_yol: hata}` ile çağırıcıya (sıralı yedeğe) düştüğünü.

Canlı Luca oturumu gerektirmez.
"""
import base64
import io
import os
import sys
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
        arg = args[0]
        url, istekler = arg["url"], arg["list"]
        captured["url"] = url
        captured["istekler"] = istekler
        yanitlar = []
        for it in istekler:
            gomulu = {"durum": 200}
            if it.get("body", {}).get("params", {}).get("ettn") == "x-1":
                gomulu["durum"] = 503
                gomulu["data"] = ("HATA: servis yok".encode("utf-8")
                                  if False else None)
            yanitlar.append({
                "idx": it["idx"],
                "durum": gomulu["durum"],
                "data": (base64.b64encode(_zip_uret()).decode("ascii")
                         if gomulu["durum"] == 200 else ""),
            })
        return yanitlar


class FakeSayfa:
    url = "https://auygs.luca.com.tr/Luca/gib530.do?tur=efatura_alis"

    class context:
        @staticmethod
        def cookies():
            return [{"name": "JSESSIONID", "value": "OTURUM123"},
                    {"name": "other", "value": "v"}]


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


def test_body(ot):
    belge = {
        "ettn": "d2815be8-383f-43c1-8abc",
        "belge_numarasi": "A022026260557307",
        "belge_turu": "FATURA",
        "onay_durumu": "Onaylandı",
        "bayi_no": "7",
        "url": "gib_efatura_alis.jq?ettn=x",
    }
    body = luca_cekme._zip_body_uret(ot, belge)
    params = body["params"]
    kontrol("sirket/donem üstte",
            body.get("sirket_id") == "1234" and
            body.get("donem_id") == "5678")
    kontrol("gövde anahtarları tam",
            all(k in params for k in ("islem", "etti", "ettn", "bayiNo",
                                      "onayDurumu", "belgeTuru",
                                      "belgeNumarasi", "entegrator", "url",
                                      "dosya_adi", "_u",
                                      "gibKullaniciKodu", "gibSifre")))
    kontrol("ettn/dosya adı",
            params["ettn"] == "d2815be8-383f-43c1-8abc" and
            params["dosya_adi"] == "A022026260557307.zip")
    kontrol("gib kullanıcı/sifre dolu",
            params["gibKullaniciKodu"] == "kkk" and
            params["gibSifre"] == "sss")
    kontrol("işlem türü download",
            params["islem"] == "download" and params["_u"] == "ea530:download")


def test_toplu_paralel(ot):
    plan = []
    for i in range(6):
        plan.append(({
            "ettn": f"ettn-{i}",
            "belge_numarasi": f"B{i:08d}",
            "belge_turu": "FATURA",
        }, os.path.join(YOL, f"_test_p_{i}.zip")))
    hatalar = luca_cekme._zip_hizli_toplu_indir(
        FakeCerceve(), FakeSayfa(), plan, "efatura_alis", klasor=YOL,
        esler=4, dilim=100)
    kontrol("6 belge de indirildi, hata yok",
            not hatalar, f"hatalar={hatalar}")
    inen = [p for _, p in plan if os.path.exists(p)]
    kontrol("hepsi zip olarak inmiş", len(inen) == 6)
    kontrol("tek evaluate turu + 6 istek",
            len(captured.get("istekler") or []) == 6)
    belgesal = plan[0][0]
    kontrol("belge UBL özetiyle zenginleşti",
            belgesal.get("matrah") == 1430.97 and
            belgesal.get("kdv_toplam") == 143.10 and
            belgesal.get("genel_toplam") == 1574.07 and
            belgesal.get("para") == "TRY",
            f"matrah={belgesal.get('matrah')}")
    kontrol("oran kalemleri dolduruldu",
            isinstance(belgesal.get("oran_kalemleri"), list)
            and belgesal.get("oran_kalemleri"))
    for _, p in plan:
        if os.path.exists(p):
            os.remove(p)


def test_hata_yedegi():
    plan = [({"ettn": "x-1", "belge_numarasi": "H1"},
             os.path.join(YOL, "_test_h.zip"))]
    hatalar = luca_cekme._zip_hizli_toplu_indir(
        FakeCerceve(), FakeSayfa(), plan, "efatura_alis", klasor=YOL,
        esler=4, dilim=100)
    kontrol("hizalı durum sıralı yedeğe döner",
            not os.path.exists(plan[0][1]) and
            plan[0][1] in hatalar, f"hatalar={hatalar}")
    if os.path.exists(plan[0][1]):
        os.remove(plan[0][1])


class _CercevePatladi:
    def evaluate(self, *a, **k):
        raise Exception("frame kapandı")


def test_cerceve_patladi():
    plan = [({"ettn": "e-1", "belge_numarasi": "C1"},
             os.path.join(YOL, "_test_c.zip"))]
    hatalar = luca_cekme._zip_hizli_toplu_indir(
        _CercevePatladi(), FakeSayfa(), plan, "efatura_alis", klasor=YOL,
        esler=4, dilim=100)
    kontrol("frame kapandıysa güvenli yedek",
            plan[0][1] in hatalar and not os.path.exists(plan[0][1]))
    if os.path.exists(plan[0][1]):
        os.remove(plan[0][1])


if __name__ == "__main__":
    print("== sayfa-içi paralel zip sarmalı (offline) ==")
    ot = test_oturum_bilgisi()
    test_body(ot)
    test_toplu_paralel(ot)
    test_hata_yedegi()
    test_cerceve_patladi()
    print()
    print("SONUÇ: TÜM TESTLER TAMAM" if BASARILI
          else "SONUÇ: BAŞARISIZ")
    sys.exit(0 if BASARILI else 1)