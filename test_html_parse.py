"""HTML parse fonksiyonlari icin unit testler."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import luca_cekme as l

HATA = 0


def test(ad, kosul, detay=""):
    global HATA
    durum = "PASS" if kosul else "FAIL"
    if not kosul:
        HATA += 1
    print(f"  [{durum}] {ad} {detay}")


print("== _tutar_cevir ==")
test("virgul/nokta", l._tutar_cevir("1.234,56") == 1234.56,
     f"-> {l._tutar_cevir('1.234,56')}")
test("sadece nokta", l._tutar_cevir("1234567.89") == 1234567.89)
test("sifir", l._tutar_cevir("0") == 0.0)
test("bos string", l._tutar_cevir("") is None)
test("text", l._tutar_cevir("abc") is None)
test("None", l._tutar_cevir(None) is None)
test("negatif", l._tutar_cevir("-1.234,56") == -1234.56,
     f"-> {l._tutar_cevir('-1.234,56')}")
test("ondalik tek virgul", l._tutar_cevir("200,00") == 200.0,
     f"-> {l._tutar_cevir('200,00')}")

print("\n== _tablo_basliklarini_bul ==")
html_with_headers = """
<table>
<tr><th>Belge No</th><th>Tarih</th><th>VKN</th><th>Matrah</th><th>KDV</th><th>Genel Toplam</th></tr>
<tr><td>X</td></tr>
</table>
"""
kolon = l._tablo_basliklarini_bul(html_with_headers)
test("matrah kolonu bulundu", "matrah" in kolon,
     f"-> {kolon}")
test("kdv kolonu bulundu", "kdv" in kolon)
test("genel_toplam kolonu bulundu", "genel_toplam" in kolon)

html_no_headers = "<table><tr><td>X</td><td>Y</td></tr></table>"
kolon2 = l._tablo_basliklarini_bul(html_no_headers)
test("baslik yoksa bos dict", len(kolon2) == 0, f"-> {kolon2}")

print("\n== _satirlari_ayikla (HTML tablo) ==")
html_normal = """
<html><body>
<table>
<tr>
  <th>Belge No</th><th>Tarih</th><th>VKN</th>
  <th>Matrah</th><th>KDV</th><th>Genel Toplam</th>
</tr>
<tr fatura='{"belge_numarasi":"T001","belge_tarihi":"01/07/2026","alici_vkn_tckn":"123","alici_unvan_ad_soyad":"TEST","onay_durumu":"onay"}'>
  <td>T001</td><td>01/07/2026</td><td>123</td>
  <td>1.000,00</td><td>200,00</td><td>1.200,00</td>
</tr>
</table>
</body></html>
"""
satirlar = l._satirlari_ayikla(html_normal)
test("1 satir bulundu", len(satirlar) == 1, f"-> {len(satirlar)}")
if satirlar:
    v = satirlar[0][1]
    test("matrah_html=1000.0", v.get("matrah_html") == 1000.0,
         f"-> {v.get('matrah_html')}")
    test("kdv_html=200.0", v.get("kdv_html") == 200.0,
         f"-> {v.get('kdv_html')}")
    test("toplam_html=1200.0", v.get("toplam_html") == 1200.0,
         f"-> {v.get('toplam_html')}")
    test("belge_numarasi", v.get("belge_numarasi") == "T001")
    test("belge_tarihi", v.get("belge_tarihi") == "01/07/2026")

print("\n== _satirlari_ayikla (coklu satir) ==")
html_coklu = """
<table>
<tr><th>No</th><th>Matrah</th><th>KDV</th><th>Toplam</th></tr>
<tr fatura='{"belge_numarasi":"A1","belge_tarihi":"01/07/2026","alici_vkn_tckn":"1","alici_unvan_ad_soyad":"A","onay_durumu":"onay"}'>
  <td>A1</td><td>500,00</td><td>100,00</td><td>600,00</td>
</tr>
<tr fatura='{"belge_numarasi":"A2","belge_tarihi":"02/07/2026","alici_vkn_tckn":"2","alici_unvan_ad_soyad":"B","onay_durumu":"onay"}'>
  <td>A2</td><td>1.500,00</td><td>300,00</td><td>1.800,00</td>
</tr>
<tr fatura='{"belge_numarasi":"A3","belge_tarihi":"03/07/2026","alici_vkn_tckn":"3","alici_unvan_ad_soyad":"C","onay_durumu":"onay"}'>
  <td>A3</td><td>2.000,00</td><td>400,00</td><td>2.400,00</td>
</tr>
</table>
"""
satirlar2 = l._satirlari_ayikla(html_coklu)
test("3 satir bulundu", len(satirlar2) == 3, f"-> {len(satirlar2)}")
for i, (sira, v) in enumerate(satirlar2):
    matrah = v.get("matrah_html")
    test(f"satir {i+1} matrah", matrah is not None,
         f"-> {matrah}")

print("\n== _satirlari_ayikla (bos HTML) ==")
test("bos html", len(l._satirlari_ayikla("<html></html>")) == 0)
test("fatura yok", len(l._satirlari_ayikla("<table><tr><td>X</td></tr></table>")) == 0)

print("\n== _satirlari_ayikla (baslik yok, fallback) ==")
html_no_h = """
<tr fatura='{"belge_numarasi":"X1","belge_tarihi":"01/07/2026","alici_vkn_tckn":"99","alici_unvan_ad_soyad":"Y","onay_durumu":"onay"}'>
  <td>X1</td><td>1.000,00</td><td>200,00</td><td>1.200,00</td>
</tr>
"""
satirlar3 = l._satirlari_ayikla(html_no_h)
test("satir bulundu", len(satirlar3) == 1)
if satirlar3:
    v3 = satirlar3[0][1]
    test("baslik yoksa matrah_html=None", v3.get("matrah_html") is None)

print("\n" + "=" * 40)
if HATA == 0:
    print("TUM TESTLER BASARILI!")
else:
    print(f"{HATA} TEST BASARISIZ!")
    sys.exit(1)
