"""Regresyon testi: _sorgula_listele_butonu.

Geçmiş kilit: 500+ fatura satırlı DOM'da _sorgula_listele_butonu her
element için ayrı inner_text() protokol turu yapıp dakikalarca takılıyor
ve 'Belge Ara' (gonder('arama-window')) / 'İptal/İtiraz Sorgula'
(gonder('indir')) gibi popup açan butonları yanlışlıkla tıklıyordu.

Bu test, gerçek luca_cekme._sorgula_listele_butonu'nu headless
Chromium'da çalıştırıp:
  1. popup/zip açan butonların TIKLANMADIĞINI,
  2. doğru 'Sorgula'/'Listele' butonunun tıklandığını,
  3. 500 satırlı DOM'da hızlı bitirdiğini (5 saniye içinde)
doğrular. Tıklanan buton window.* bayraği ile izlenir.

Playwright yoksa test atlanır (MASAÜSTÜ uygulamasında zorunlu değil).
"""
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

YOL = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, YOL)

import luca_cekme  # noqa: E402

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

BASARILI = True


def kontrol(ad, kosul, detay=""):
    global BASARILI
    durum = "TAMAM" if kosul else "HATA"
    if not kosul:
        BASARILI = False
    print(f"  [{durum}] {ad} {detay}")


def _tarayici_ac(p):
    for kanal in ("msedge", "chrome", "brave"):
        try:
            return p.chromium.launch(channel=kanal, headless=True)
        except Exception:
            continue
    return p.chromium.launch(headless=True)


def test_sorguol_butonu():
    """500 satırlı DOM: popup açanlar elenir, doğru buton tıklanır."""
    tablo = "".join(f"<tr><td>{i}</td><td>F {i}</td></tr>" for i in range(500))
    html = f"""<html><body>
    <button onclick="gonder('arama-window')">Belge Ara</button>
    <button onclick="gonder('indir')">İptal/İtiraz Sorgula</button>
    <button onclick="gonder('indir-window')">GİB'den Getir</button>
    <button onclick="yenile()">Yenile</button>
    <button onclick="listele()">Listele</button>
    <script>
      function gonder(x){{ window.gonderCagri = x; }}
      function yenile(){{ window.yenileOk = 1; }}
      function listele(){{ window.listeleOk = 1; }}
    </script>
    <table><tbody>{tablo}</tbody></table>
    </body></html>"""
    with sync_playwright() as p:
        b = _tarayici_ac(p)
        try:
            ctx = b.new_context(no_viewport=True)
            sayfa = ctx.new_page()
            sayfa.set_content(html)
            cerceve = sayfa.main_frame
            bas = time.time()
            luca_cekme._sorgula_listele_butonu(cerceve)
            gecen = time.time() - bas
            sayfa.wait_for_timeout(200)
            listele = sayfa.evaluate("window.listeleOk || 0")
            yenile = sayfa.evaluate("window.yenileOk || 0")
            gonder = sayfa.evaluate("window.gonderCagri || ''")
            kontrol("doğru 'Listele' tıklandı", bool(listele),
                    f"(listele={listele})")
            kontrol("popup açan buton tıklanmadı", gonder == "",
                    f"(gonder={gonder!r})")
            kontrol("5 sn içinde bitti", gecen < 5,
                    f"({gecen:.2f}s)")
            ctx.close()
        finally:
            b.close()


def test_sorgusu_yoksa_sessiz():
    """Sorgula butonu yoksa fonksiyon hata vermez, kilitlenmez."""
    with sync_playwright() as p:
        b = _tarayici_ac(p)
        try:
            ctx = b.new_context(no_viewport=True)
            sayfa = ctx.new_page()
            sayfa.set_content("<html><body><p>boş</p></body></html>")
            cerceve = sayfa.main_frame
            bas = time.time()
            try:
                luca_cekme._sorgula_listele_butonu(cerceve)
                hata_yok = True
            except Exception:
                hata_yok = False
            gecen = time.time() - bas
            kontrol("buton yoksa sessiz geçer", hata_yok)
            kontrol("3 sn içinde bitti", gecen < 3, f"({gecen:.2f}s)")
            ctx.close()
        finally:
            b.close()


if __name__ == "__main__":
    if sync_playwright is None:
        print("Playwright kurulu değil; _sorgula_listele_butonu regresyon "
              "testi atlandı. (pip install playwright)")
        sys.exit(0)
    print("== _sorgula_listele_butonu regresyon ==")
    test_sorguol_butonu()
    test_sorgusu_yoksa_sessiz()
    print()
    if BASARILI:
        print("SONUÇ: TÜM TESTLER TAMAM")
    else:
        print("SONUÇ: TESTLER BAŞARISIZ")
        sys.exit(1)