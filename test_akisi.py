import glob
import os
import sys

YOL = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, YOL)

from cetvel import cetvel_parse
from efatura import efatura_parse
from matcher import capraz_kontrol
from utils import tl_format

TEST_KLASORU = os.path.join(YOL, "test_veri")

BASARILI = True


def kontrol(ad, kosul, detay=""):
    global BASARILI
    durum = "TAMAM" if kosul else "HATA"
    if not kosul:
        BASARILI = False
    print(f"  [{durum}] {ad} {detay}")


if __name__ == "__main__":
    fatura_dosyalari = sorted(glob.glob(os.path.join(TEST_KLASORU, "fatura_*.pdf")))
    cetvel_dosyalari = glob.glob(os.path.join(TEST_KLASORU, "kontrol_cetveli.pdf"))

    print("== TOPLU FATURA (çok sayfalı) ==")
    toplu_faturalar = efatura_parse(os.path.join(TEST_KLASORU, "Toplu Fatura Yazdırma.pdf"))
    for f in toplu_faturalar:
        print(f"  sayfa={f['sayfa']} belge={f['belge_no']} matrah={tl_format(f['matrah'])} kdv={tl_format(f['kdv'])} toplam={tl_format(f['toplam'])}")
    kontrol("toplu 2 fatura", len(toplu_faturalar) == 2, f"-> {len(toplu_faturalar)}")
    kontrol("toplu sayfa 1", toplu_faturalar[0]["belge_no"] == "GFE202400000011")
    kontrol("toplu sayfa 2", toplu_faturalar[1]["belge_no"] == "GFE202400000012")
    kontrol("toplu kdv 1", toplu_faturalar[0]["kdv"] == 200)
    kontrol("toplu tutar tutarli", not any(n for n in toplu_faturalar[0]["notlar"] if "≠" in n))

    print("\n== TARANMIŞ CETVEL (OCR) ==")
    from cetvel import cetvel_parse
    tarama_sonuc = cetvel_parse(os.path.join(TEST_KLASORU, "taranmis_cetvel.pdf"))
    print("  notlar:", tarama_sonuc["notlar"])
    for c in tarama_sonuc["kayitlar"][:8]:
        print(f"  vkn={c['vkn']} belge={c['belge_no']} tarih={c['tarih']} matrah={tl_format(c['matrah'])} kdv={tl_format(c['kdv'])}")
    kontrol("tarama kayit sayisi", len(tarama_sonuc["kayitlar"]) >= 5, f"-> {len(tarama_sonuc['kayitlar'])}")
    ilk = tarama_sonuc["kayitlar"][0]
    kontrol("tarama ilk vkn", ilk["vkn"] == "12345678901", f"-> {ilk['vkn']}")
    kontrol("tarama ilk kdv", ilk["kdv"] == 200, f"-> {ilk['kdv']}")

    print("\n== EXCEL FATURA LİSTESİ ==")
    from dosya import cetvel_dosya_parse, fatura_dosya_parse
    excel_faturalar = fatura_dosya_parse(os.path.join(TEST_KLASORU, "fatura_listesi.xlsx"))
    for f in excel_faturalar:
        print(f"  satir={f['satir']} belge={f['belge_no']} vkn={f['satici_vkn']} matrah={tl_format(f['matrah'])} kdv={tl_format(f['kdv'])} toplam={tl_format(f['toplam'])}")
    kontrol("excel fatura 4 kayit", len(excel_faturalar) == 4, f"-> {len(excel_faturalar)}")
    kontrol("excel fatura 1", excel_faturalar[0]["belge_no"] == "GFE202400000001" and excel_faturalar[0]["matrah"] == 1000)
    kontrol("excel fatura kdv", excel_faturalar[2]["kdv"] == 50)

    print("\n== EXCEL CETVEL LİSTESİ ==")
    excel_cetvel = cetvel_dosya_parse(os.path.join(TEST_KLASORU, "kontrol_cetveli.xlsx"))
    print("  notlar:", excel_cetvel["notlar"])
    for c in excel_cetvel["kayitlar"]:
        print(f"  vkn={c['vkn']} belge={c['belge_no']} tarih={c['tarih']} matrah={tl_format(c['matrah'])} kdv={tl_format(c['kdv'])}")
    kontrol("excel cetvel 4 kayit", len(excel_cetvel["kayitlar"]) == 4, f"-> {len(excel_cetvel['kayitlar'])}")
    kontrol("excel cetvel kdv", excel_cetvel["kayitlar"][2]["kdv"] == 45)
    kontrol("excel cetvel toplam satiri atlandi", not any(c["belge_no"] == "GENELTOPLAM" for c in excel_cetvel["kayitlar"]))

    print("\n== XML FATURA (UBL e-fatura) ==")
    from dosya import fatura_dosya_parse as fatura_dosya_parse_fn
    from xml_oku import fatura_xml_parse
    xml_faturalar = []
    for d in sorted(glob.glob(os.path.join(TEST_KLASORU, "fatura_*.xml"))):
        xml_faturalar.extend(fatura_xml_parse(d))
    for f in xml_faturalar:
        print(f"  {os.path.basename(f['dosya'])}: belge={f['belge_no']} tarih={f['tarih']} "
              f"satici={f['satici_vkn']} matrah={tl_format(f['matrah'])} kdv={tl_format(f['kdv'])} toplam={tl_format(f['toplam'])} oran={f['oranlar']}")
    kontrol("xml 5 fatura", len(xml_faturalar) == 5, f"-> {len(xml_faturalar)}")
    kontrol("xml 1 belge", xml_faturalar[0]["belge_no"] == "GFE202400000001")
    kontrol("xml 1 vkn", xml_faturalar[0]["satici_vkn"] == "12345678901")
    kontrol("xml 1 matrah", xml_faturalar[0]["matrah"] == 1000)
    kontrol("xml 1 kdv", xml_faturalar[0]["kdv"] == 200)
    kontrol("xml 1 toplam", xml_faturalar[0]["toplam"] == 1200)
    kontrol("xml 3 kdv", xml_faturalar[2]["kdv"] == 50)
    kontrol("xml 3 oran", 10 in xml_faturalar[2]["oranlar"])
    kontrol("xml 5 vkn", xml_faturalar[4]["satici_vkn"] == "00099988877")
    gz = fatura_xml_parse(os.path.join(TEST_KLASORU, "sikistirilmis_fatura.xml"))
    kontrol("xml gzip acildi", len(gz) == 1 and gz[0]["belge_no"] == "GFE202400000099" and gz[0]["kdv"] == 90, f"-> {gz[0]['belge_no'] if gz else None}")
    xml_dosya_parse = fatura_dosya_parse_fn(os.path.join(TEST_KLASORU, "fatura_1.xml"))
    kontrol("xml dosya yonlendirme", len(xml_dosya_parse) == 1 and xml_dosya_parse[0]["belge_no"] == "GFE202400000001")

    print("\n== FATURA PARSE ==")
    faturalar = []
    for d in fatura_dosyalari:
        faturalar.extend(efatura_parse(d))
    for f in faturalar:
        print(f"  {os.path.basename(f['dosya'])}: belge={f['belge_no']} tarih={f['tarih']} "
              f"satici={f['satici_vkn']} matrah={tl_format(f['matrah'])} kdv={tl_format(f['kdv'])} toplam={tl_format(f['toplam'])}")

    kontrol("1 no okundu", faturalar[0]["belge_no"] == "GFE202400000001")
    kontrol("1 tarih", faturalar[0]["tarih"] == "2024-02-05")
    kontrol("1 satıcı VKN", faturalar[0]["satici_vkn"] == "12345678901")
    kontrol("1 matrah", faturalar[0]["matrah"] == 1000)
    kontrol("1 kdv", faturalar[0]["kdv"] == 200)
    kontrol("1 toplam", faturalar[0]["toplam"] == 1200)
    kontrol("3 kdv %10", faturalar[2]["kdv"] == 50)
    kontrol("5 vkn", faturalar[4]["satici_vkn"] == "00099988877")

    print("\n== CETVEL PARSE ==")
    cetvel_sonuc = cetvel_parse(cetvel_dosyalari[0])
    for c in cetvel_sonuc["kayitlar"]:
        print(f"  vkn={c['vkn']} belge={c['belge_no']} tarih={c['tarih']} "
              f"matrah={tl_format(c['matrah'])} kdv={tl_format(c['kdv'])} unvan={c['unvan']}")
    kontrol("cetvel 6 kayit", len(cetvel_sonuc["kayitlar"]) == 6, f"-> {len(cetvel_sonuc['kayitlar'])}")
    kontrol("cetvel 1 belge no", cetvel_sonuc["kayitlar"][0]["belge_no"] == "GFE202400000001")
    kontrol("cetvel 1 kdv", cetvel_sonuc["kayitlar"][0]["kdv"] == 200)
    kontrol("cetvel 3 kdv 45", cetvel_sonuc["kayitlar"][2]["kdv"] == 45)
    kontrol("cetvel 4 belge", cetvel_sonuc["kayitlar"][3]["belge_no"] == "GFE202400000009")
    kontrol("cetvel 6 vkn", cetvel_sonuc["kayitlar"][5]["vkn"] == "11122233344")

    print("\n== ÇAPRAZ KONTROL ==")
    sonuclar, ozet = capraz_kontrol(faturalar, cetvel_sonuc["kayitlar"])
    for s in sonuclar:
        print(f"  [{s['durum']}] {s['belge_no'] or ''} vkn={s['vkn'] or ''} "
              f"matrah={tl_format(s['matrah'])} kdv={tl_format(s['kdv'])} {s['detay']}")
    print("  OZET:", ozet)

    kontrol("eslesen 2", ozet["eslesen"] == 2, f"-> {ozet['eslesen']}")
    kontrol("tutar farki 1", ozet["tutar_farki"] == 1, f"-> {ozet['tutar_farki']}")
    kontrol("vkn farki 1", ozet["vkn_farki"] == 1, f"-> {ozet['vkn_farki']}")
    kontrol("cetvelde yok 1", ozet["cetvelde_yok"] == 1, f"-> {ozet['cetvelde_yok']}")
    kontrol("faturada yok 1", ozet["faturada_yok"] == 1, f"-> {ozet['faturada_yok']}")
    kontrol("mukerrer 1", ozet["mukerrer"] == 1, f"-> {ozet['mukerrer']}")

    print("\n== KARIŞIK ÇAPRAZ KONTROL (PDF + Excel) ==")
    karisik_faturalar = list(faturalar) + excel_faturalar
    karisik_cetvel = cetvel_sonuc["kayitlar"] + excel_cetvel["kayitlar"]
    k_sonuc, k_ozet = capraz_kontrol(karisik_faturalar, karisik_cetvel)
    for s in k_sonuc:
        print(f"  [{s['durum']}] {s['belge_no'] or ''} vkn={s['vkn'] or ''} {s['detay']}")
    print("  OZET:", k_ozet)
    kontrol("karisik eslesen 4", k_ozet["eslesen"] == 4, f"-> {k_ozet['eslesen']}")
    kontrol("karisik tutar farki 2", k_ozet["tutar_farki"] == 2, f"-> {k_ozet['tutar_farki']}")

    print("\n== EXCEL RAPORU ==")
    from report import rapor_olustur
    hedef = os.path.join(YOL, "test_rapor.xlsx")
    rapor_olustur(sonuclar, ozet, faturalar, cetvel_sonuc["kayitlar"], hedef)
    kontrol("excel olusturuldu", os.path.exists(hedef) and os.path.getsize(hedef) > 0)

    print("\nSONUÇ:", "TÜM TESTLER TAMAM" if BASARILI else "HATALAR VAR")
    sys.exit(0 if BASARILI else 1)
