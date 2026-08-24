"""GİB Dijital Vergi Dairesi'nden e-Arşiv faturalarının otomatik indirilmesi.

Dijital Vergi Dairesi'ne (dijital.gib.gov.tr) TC/VKN + şifre + captcha ile
girip 'e-Arşiv Faturalarım' (adınıza düzenlenen / alış) listesini tarih
aralıklarına bölerek Excel olarak indirir. Kısıt: sorgu başına en fazla 7
günlük aralık, geriye en fazla 2 ay.

e-Fatura belgeleri burada LİSTENMEZ: GİB e-Fatura portalının şifreli girişi
kaldırıldı, yalnızca e-İmza/mobil imza ile açılır; entegratör kullanmayan
mükellefin B2B e-faturalarına şifreyle ulaşılamaz.
"""
import base64
import io
import os
import shutil
import socket
import time
from datetime import date, timedelta

import excel_oku
import gib_api

GIRIS_ADRESI = "https://dijital.gib.gov.tr/portal/login"
ARSIV_ADRESI = "https://dijital.gib.gov.tr/portal/e-arsiv-faturalarim"
KARAKTER_KUMESI = (" tessedit_char_whitelist="
                   "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789")
MAKS_GIRIS_DENEMESI = 12


class GibHata(Exception):
    """Kullanıcıya gösterilebilir GİB çekim hatası."""


def internet_var_mi():
    try:
        socket.create_connection(("dijital.gib.gov.tr", 443), timeout=6).close()
        return True
    except OSError:
        return False


def _ocr_hazir():
    try:
        import pytesseract  # noqa: F401
        import PIL.Image  # noqa: F401
    except ImportError:
        return False, ("OCR bileşenleri eksik. Kurulum:\n"
                       "pip install pytesseract pillow\n"
                       "ve Tesseract OCR kurulumu "
                       "(C:\\Program Files\\Tesseract-OCR)")
    komut = shutil.which("tesseract")
    if not komut:
        for aday in (r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                     r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"):
            if os.path.exists(aday):
                komut = aday
                break
    if komut:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = komut
        return True, ""
    return False, "Tesseract OCR bulunamadı. https://github.com/UB-Mannheim/tesseract/wiki"


def _tarih_araligini_bol(bas, bit, parca_gun=7):
    """[bas, bit] aralığını en fazla `parca_gun` günlük kapalı parçalara böler."""
    parcalar = []
    baslangic = bas
    while baslangic <= bit:
        son = min(baslangic + timedelta(days=parca_gun - 1), bit)
        parcalar.append((baslangic, son))
        baslangic = son + timedelta(days=1)
    return parcalar


def _captcha_oku(sayfa):
    from PIL import Image, ImageOps
    import pytesseract
    src = sayfa.eval_on_selector("img[src^='data:image']", "e => e.src")
    img = Image.open(io.BytesIO(base64.b64decode(src.split(",", 1)[1])))
    buyuk = img.resize((img.width * 4, img.height * 4),
                       Image.LANCZOS).convert("L")
    hist = buyuk.histogram()
    toplam = sum(hist)
    ortalama = sum(i * c for i, c in enumerate(hist)) / max(toplam, 1)
    temel = ImageOps.invert(buyuk) if ortalama < 100 else buyuk
    varyantlar = [temel]
    for esik in (110, 130, 150, 170):
        varyantlar.append(temel.point(lambda x, e=esik: 0 if x < e else 255))
    adaylar = []
    for im in varyantlar:
        for psm in ("7", "8"):
            try:
                metin = pytesseract.image_to_string(
                    im, config="--psm " + psm + KARAKTER_KUMESI).strip()
            except Exception:
                continue
            metin = "".join(c for c in metin if c.isalnum())[:6]
            if len(metin) >= 4 and metin not in adaylar:
                adaylar.append(metin)
    return adaylar[:6]


def _giris_yapildi_mi(sayfa):
    try:
        adres = sayfa.url.lower()
        if "/portal" in adres and "login" not in adres:
            return True
        if sayfa.query_selector("#userid") is None:
            metin = sayfa.inner_text("body")
            return ("Doğrulama Kodu" not in metin and "Giriş Yap" not in metin
                    and len(metin) > 400)
    except Exception:
        pass
    return False


def _giris_yap(sayfa, tc, sifre, ilerleme=None):
    def bildir(metin):
        if ilerleme:
            ilerleme(metin)

    sayfa.set_default_navigation_timeout(90000)
    sayfa.goto(GIRIS_ADRESI, wait_until="domcontentloaded")
    sayfa.wait_for_timeout(1200)
    tamam = _giris_yapildi_mi(sayfa)
    deneme = 0
    while not tamam and deneme < MAKS_GIRIS_DENEMESI:
        try:
            if sayfa.query_selector("#userid") is None:
                sayfa.goto(GIRIS_ADRESI, wait_until="domcontentloaded")
                sayfa.wait_for_timeout(800)
            sayfa.fill("#userid", tc)
            sayfa.fill("#sifre", sifre)
            adaylar = _captcha_oku(sayfa)
            if not adaylar:
                sayfa.reload(wait_until="domcontentloaded")
                time.sleep(1)
                deneme += 1
                continue
            kod = adaylar[deneme % len(adaylar)]
            bildir(f"GİB doğrulama kodu denemesi {deneme + 1}: {kod}")
            sayfa.fill("#dk", kod)
            sayfa.click("button[type=submit]")
            for _ in range(8):
                time.sleep(1.5)
                if _giris_yapildi_mi(sayfa):
                    tamam = True
                    break
            if not tamam:
                sayfa.goto(GIRIS_ADRESI, wait_until="domcontentloaded")
                if deneme and deneme % 4 == 3:
                    bildir("Doğrulama kodu zorlanıyor, kısa bekleniyor...")
                    time.sleep(8)
        except Exception as hata:
            bildir(f"GİB giriş uyarısı: {str(hata)[:80]}")
        deneme += 1
    if not tamam:
        raise GibHata("GİB'e giriş yapılamadı. TC, şifre veya doğrulama kodu "
                      "sürekli reddedildi. Şifrenizi DVD'den kontrol edin.")


def _tarayici_ac(playwright):
    kanallar = ["msedge", "chrome"]
    son_hata = None
    for kanal in kanallar:
        try:
            return playwright.chromium.launch(channel=kanal, headless=True)
        except Exception as hata:
            son_hata = hata
    try:
        return playwright.chromium.launch(headless=True)
    except Exception as hata:
        raise GibHata(
            "Tarayıcı başlatılamadı. Edge veya Chrome kurulu olmalı ya da "
            "'playwright install chromium' çalıştırılmalı. Detay: "
            f"{son_hata or hata}")


def _excel_aktar_tikla(sayfa):
    """Excel'e Aktar ogesi bir <p> olup uzerine yukleme ortusu binebilir;
    normal -> force -> JS tiklama zinciri."""
    try:
        sayfa.click("text=Excel'e Aktar", timeout=8000)
        return
    except Exception:
        pass
    try:
        sayfa.click("text=Excel'e Aktar", timeout=4000, force=True)
        return
    except Exception:
        pass
    sayfa.evaluate(
        "() => { const es=[...document.querySelectorAll("
        "'button,a,p,span,div')];"
        " for (const e of es) { if ((e.textContent||'').trim()==="
        "\"Excel'e Aktar\") { e.click(); return true; } }"
        " return false; }")


def _parca_guncel_mi(dosya_yolu, bas_tarih, bit_tarih):
    """Excel'deki en az bir belge tarihi istenen aralıkta mı?

    Döner: True (güncel), False (bayat - aralık dışı), None (tarih okunamadı).
    """
    try:
        satirlar = excel_oku.fatura_gib_arsiv_liste_parse(dosya_yolu)
    except Exception:
        return None
    if not satirlar:
        return True
    okunabilen = 0
    for s in satirlar:
        t = s.get("tarih")
        if not t:
            continue
        try:
            d = date.fromisoformat(str(t)[:10])
        except ValueError:
            continue
        okunabilen += 1
        if bas_tarih <= d <= bit_tarih:
            return True
    return False if okunabilen else None


def cek_e_arsiv_alis(gib_tc, gib_sifre, bas_tarih, bit_tarih, hedef_klasor,
                     ilerleme=None, ivd_kod=None, ivd_sifre=None):
    """Adınıza düzenlenen e-Arşiv faturalarını Excel olarak indirer.

    bas_tarih/bit_tarih: datetime.date. Dönen değer: indirilen dosya yolları.
    ivd_kod/ivd_sifre verilirse çekim öncesi e-Arşiv REST API'si ile hızlı
    doğrulama yapılır; dönemde belge yoksa tarayıcı hiç açılmadan [] döner.
    """
    hazir, mesaj = _ocr_hazir()
    if not hazir:
        raise GibHata(mesaj)

    def bildir(metin):
        if ilerleme:
            ilerleme(metin)

    parcalar = _tarih_araligini_bol(bas_tarih, bit_tarih)
    # Portal gelecek gun iceren araliklari sessizce reddediyor:
    # parcalarini bugune kadar kisip tamamen gelecek olanlari atla.
    bugun = date.today()
    parcalar = [(b, min(s, bugun)) for b, s in parcalar if b <= bugun]
    os.makedirs(hedef_klasor, exist_ok=True)
    dosyalar = []

    beklenen = None
    if ivd_kod and ivd_sifre:
        bildir("IVD kullanıcı kodu hızlı doğrulanıyor...")
        try:
            istemci = gib_api.GibApi(ivd_kod, ivd_sifre)
            istemci.giris()
            beklenen = [len(istemci.adima_duzenlenen_belgeler(p_bas, p_son))
                        for p_bas, p_son in parcalar]
        except gib_api.GibApiHata as hata:
            raise GibHata(
                "e-Arşiv hızlı doğrulama başarısız: %s\n"
                "(IVD kullanıcı kodu/şifresini kontrol edin veya alanları "
                "boş bırakın.)" % hata)
        toplam = sum(beklenen)
        if toplam == 0:
            bildir("Seçilen dönemde adınıza düzenlenmiş e-Arşiv belgesi yok "
                   "(API sorgusu).")
            return []
        bildir(f"Doğrulandı: dönemde {toplam} belge bekleniyor.")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise GibHata("Playwright kurulu değil. Kurulum: pip install playwright")

    bildir("GİB bağlantısı açılıyor...")
    with sync_playwright() as p:
        tarayici = _tarayici_ac(p)
        oturum = tarayici.new_context(viewport={"width": 1600, "height": 1000},
                                      accept_downloads=True)
        sayfa = oturum.new_page()
        try:
            _giris_yap(sayfa, gib_tc, gib_sifre, bildir)
            bildir("GİB'e giriş başarılı.")
            time.sleep(2)

            gorulen = {}
            for sira, (p_bas, p_son) in enumerate(parcalar, start=1):
                bildir(f"Aralık {sira}/{len(parcalar)}: "
                       f"{p_bas.strftime('%d.%m.%Y')} - {p_son.strftime('%d.%m.%Y')}")
                hedef = os.path.join(
                    hedef_klasor,
                    f"earsiv_alis_{p_bas.strftime('%Y%m%d')}"
                    f"_{p_son.strftime('%Y%m%d')}.xlsx")
                try:
                    deneme = 0
                    while True:
                        # Her aralikta taze yukleme: onceki sorgunun
                        # kalintilari (bayat Excel dugmesi dahil) temizlenir.
                        sayfa.goto(ARSIV_ADRESI, wait_until="domcontentloaded")
                        sayfa.wait_for_timeout(2500)
                        sayfa.fill("#basTarih", p_bas.strftime("%d.%m.%Y"))
                        sayfa.fill("#bitTarih", p_son.strftime("%d.%m.%Y"))
                        sayfa.click("text=Filtrele")
                        time.sleep(6 + deneme * 5)
                        govde = sayfa.inner_text("body")
                        if "Lütfen önce sorgulama" in govde:
                            if deneme < 2:
                                deneme += 1
                                bildir(f"  Aralık {sira}: sayfa hazır "
                                       f"değil, yeniden deneniyor "
                                       f"({deneme}/2)...")
                                continue
                            bildir(f"  Aralık {sira}: filtre uygulanamadı, "
                                   "atlandı.")
                            break
                        sonuc_yok = False
                        try:
                            excel_dugme = sayfa.locator("text=Excel'e Aktar")
                            dugme_var = (excel_dugme.count() > 0
                                         and excel_dugme.first.is_visible())
                        except Exception:
                            dugme_var = False
                        if dugme_var:
                            try:
                                with sayfa.expect_download(
                                        timeout=30000) as indirme:
                                    _excel_aktar_tikla(sayfa)
                                dosya = indirme.value
                                dosya.save_as(hedef)
                                dosyalar.append(hedef)
                                bildir(f"  İndirildi: "
                                       f"{os.path.basename(hedef)}")
                            except Exception as hata:
                                bildir(f"  Dışa aktarma başarısız "
                                       f"({str(hata)[:60]}).")
                                sonuc_yok = True
                        else:
                            sonuc_yok = True

                        istenen = (beklenen[sira - 1]
                                   if beklenen is not None else None)
                        if not sonuc_yok:
                            guncel = _parca_guncel_mi(hedef, p_bas, p_son)
                            if beklenen is None:
                                if guncel is False and deneme < 2:
                                    deneme += 1
                                    bildir(f"  Dosya istenen aralığı "
                                           f"içermiyor; yeniden "
                                           f"({deneme}/2)...")
                                    continue
                                break
                            okunan = None
                            if guncel is not None:
                                try:
                                    okunan = len(
                                        excel_oku.fatura_gib_arsiv_liste_parse(
                                            hedef))
                                except Exception:
                                    okunan = None
                            if okunan == istenen and guncel is not False:
                                break
                            if deneme >= 2:
                                bildir(f"  UYARI: API {istenen} belge "
                                       f"bildirdi, Excel'de {okunan} satır; "
                                       "denemeler tükendi.")
                                break
                            deneme += 1
                            bildir(f"  Uyuşmazlık (satır {okunan} ≠ "
                                   f"{istenen}, güncellik {guncel}); filtre "
                                   f"yeniden uygulanıyor ({deneme}/2)...")
                            continue
                        # Bos/indirilemedi
                        if istenen in (0, None):
                            bildir(f"  Aralık {sira}: sonuç yok.")
                            break
                        if deneme >= 2:
                            bildir(f"  UYARI: API {istenen} belge bildirdi "
                                   "ama liste boş göründü; denemeler "
                                   "tükendi.")
                            break
                        deneme += 1
                        bildir(f"  Sonuç bekleniyordu ({istenen}) ama boş "
                               f"görünüyor; yeniden deneniyor ({deneme}/2)..."
                               )

                    # Gunluk yedek: haftalik aralik inatla basarisizsa
                    # ayni pencereyi gun gun dene.
                    istenen = (beklenen[sira - 1]
                               if beklenen is not None else None)
                    ana_basari = (istenen == 0)
                    if not ana_basari and os.path.exists(hedef):
                        try:
                            n = len(excel_oku.fatura_gib_arsiv_liste_parse(
                                hedef) or [])
                            ana_basari = (istenen is None or n == istenen)
                        except Exception:
                            ana_basari = False
                    if not ana_basari:
                        if os.path.exists(hedef):
                            os.remove(hedef)
                        if hedef in dosyalar:
                            dosyalar.remove(hedef)
                        if p_son > p_bas:
                            bildir(f"  Aralık {sira}: günlük parçalama "
                                   "deneniyor...")
                            toplanan = 0
                            gun = p_bas
                            while gun <= p_son:
                                gh = os.path.join(
                                    hedef_klasor,
                                    f"earsiv_alis_{gun:%Y%m%d}"
                                    f"_{gun:%Y%m%d}.xlsx")
                                try:
                                    sayfa.goto(ARSIV_ADRESI,
                                               wait_until="domcontentloaded")
                                    sayfa.wait_for_timeout(2500)
                                    sayfa.fill("#basTarih",
                                               gun.strftime("%d.%m.%Y"))
                                    sayfa.fill("#bitTarih",
                                               gun.strftime("%d.%m.%Y"))
                                    sayfa.click("text=Filtrele")
                                    time.sleep(6)
                                    d = sayfa.locator("text=Excel'e Aktar")
                                    if d.count() > 0 and \
                                            d.first.is_visible():
                                        with sayfa.expect_download(
                                                timeout=30000) as indirme:
                                            _excel_aktar_tikla(sayfa)
                                        indirme.value.save_as(gh)
                                        dosyalar.append(gh)
                                        try:
                                            toplanan += len(
                                                excel_oku.
                                                fatura_gib_arsiv_liste_parse(
                                                    gh) or [])
                                        except Exception:
                                            pass
                                        bildir(f"    {gun:%d.%m}: indirildi")
                                except Exception as hata:
                                    bildir(f"    {gun:%d.%m}: "
                                           f"{str(hata)[:60]}")
                                gun += timedelta(days=1)
                            if istenen is not None and toplanan != istenen:
                                bildir(f"  UYARI: günlük toplam {toplanan} "
                                       f"≠ {istenen}")

                    try:
                        for s in (excel_oku.fatura_gib_arsiv_liste_parse(hedef)
                                  or []):
                            anahtar = ((s.get("belge_no") or "",
                                        str(s.get("tarih") or "")))
                            if anahtar in gorulen and \
                                    gorulen[anahtar] != os.path.basename(hedef):
                                bildir(f"  UYARI: {anahtar[0]} belgesi birden "
                                       "fazla aralıkta göründü (bayat "
                                       "filtre olabilir).")
                            gorulen[anahtar] = os.path.basename(hedef)
                    except Exception:
                        pass
                except GibHata:
                    raise
                except Exception as hata:
                    bildir(f"  Aralık {sira} hatası: {str(hata)[:90]}")
        finally:
            tarayici.close()
    if not dosyalar and parcalar:
        raise GibHata("Hiçbir tarih aralığından dosya indirilemedi. "
                      "Seçilen dönemde adınıza düzenlenmiş e-Arşiv faturası "
                      "olmayabilir.")
    return dosyalar
