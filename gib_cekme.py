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
    from PIL import Image
    import pytesseract
    src = sayfa.eval_on_selector("img[src^='data:image']", "e => e.src")
    img = Image.open(io.BytesIO(base64.b64decode(src.split(",", 1)[1])))
    buyuk = img.resize((img.width * 4, img.height * 4), Image.LANCZOS).convert("L")
    esik = buyuk.point(lambda x: 0 if x < 140 else 255)
    adaylar = []
    for im, cfg in ((img, "--psm 7" + KARAKTER_KUMESI),
                    (esik, "--psm 7" + KARAKTER_KUMESI),
                    (buyuk, "--psm 13" + KARAKTER_KUMESI)):
        metin = pytesseract.image_to_string(im, config=cfg).strip()
        metin = "".join(c for c in metin if c.isalnum())[:6]
        if len(metin) >= 4:
            adaylar.append(metin)
    return adaylar


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
            sayfa.goto(ARSIV_ADRESI, wait_until="domcontentloaded")
            sayfa.wait_for_timeout(3000)

            for sira, (p_bas, p_son) in enumerate(parcalar, start=1):
                bildir(f"Aralık {sira}/{len(parcalar)}: "
                       f"{p_bas.strftime('%d.%m.%Y')} - {p_son.strftime('%d.%m.%Y')}")
                try:
                    sayfa.fill("#basTarih", p_bas.strftime("%d.%m.%Y"))
                    sayfa.fill("#bitTarih", p_son.strftime("%d.%m.%Y"))
                    sayfa.click("text=Filtrele")
                    time.sleep(6)
                    govde = sayfa.inner_text("body")
                    if "Lütfen önce sorgulama" in govde:
                        bildir(f"  Aralık {sira}: filtre uygulanamadı, atlandı.")
                        continue
                    with sayfa.expect_download(timeout=30000) as indirme:
                        sayfa.click("text=Excel'e Aktar")
                    dosya = indirme.value
                    hedef = os.path.join(
                        hedef_klasor,
                        f"earsiv_alis_{p_bas.strftime('%Y%m%d')}"
                        f"_{p_son.strftime('%Y%m%d')}.xlsx")
                    dosya.save_as(hedef)
                    dosyalar.append(hedef)
                    bildir(f"  İndirildi: {os.path.basename(hedef)}")
                    if beklenen is not None:
                        beklenen_sayi = beklenen[sira - 1]
                        try:
                            satirlar = excel_oku.fatura_gib_arsiv_liste_parse(hedef)
                            okunan = len(satirlar)
                        except Exception:
                            okunan = None
                        if okunan is not None and okunan != beklenen_sayi:
                            bildir(f"  UYARI: API {beklenen_sayi} belge "
                                   f"bildirdi, Excel'de {okunan} satır okundu.")
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
