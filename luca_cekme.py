"""Luca (Türmob) web uygulamasından 191/391 muavin dökümü ve e-Belge
(e-Fatura / e-Arşiv, alış + satış) dosyalarının çekimi.

https://agiris.luca.com.tr/SSO/giris.erp ortak giriş sayfasına Üye Numarası +
Kullanıcı Adı + Parola ile girilir (sanal klavye zorunlu değildir). Ardından
uygulama içinden Muavin Defteri raporu bulunup seçilen dönem ve hesap kodları
(191 indirilecek KDV, 391 hesaplanan KDV) için Excel dökümü indirilir.

Not: Luca uygulamasının oturum sonrası ekranları müşteri yapılandırmasına göre
değişebilir; gezinme metin eşleştirmesiyle yapılır ve başarısızlıkta hata ayıkla-
ma için ekran görüntüsü %%TEMP%% altına kaydedilir.
"""
import base64
import io
import os
import re
import time
from datetime import date

KARAKTER_KUMESI = (" -c tessedit_char_whitelist="
                   "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
                   "0123456789")

_DDDDOCR = None
_DDDDOCR_BETA = None


def _ddddocr_motoru():
    """Captcha-özel ONNX OCR motorunu tembel yükler."""
    global _DDDDOCR
    if _DDDDOCR is None:
        try:
            import ddddocr
            _DDDDOCR = ddddocr.DdddOcr(show_ad=False)
        except Exception:
            _DDDDOCR = False
    return _DDDDOCR or None


def _ddddocr_beta_motoru():
    """ddddocr beta modelini tembel yükler (Latin captcha'da güçlü)."""
    global _DDDDOCR_BETA
    if _DDDDOCR_BETA is None:
        try:
            import ddddocr
            _DDDDOCR_BETA = ddddocr.DdddOcr(beta=True, show_ad=False)
        except Exception:
            _DDDDOCR_BETA = False
    return _DDDDOCR_BETA or None


def _luca_captcha_temizle(ham, yukseklik_kat=0.30):
    """Captcha görüntüsünü ön işler: çizgi gürültüsünü siler.

    Şekil filtreleri: en-boy oranı, dolgu oranı, yatay bant; küçük
    glifler yukseklik_kat ile elenir (0.0 = hepsi kalsın).
    Dönen değer: temizlenmiş PIL Image ('L' modu) ya da None.
    """
    try:
        import cv2
        import numpy as np
        dizi = np.frombuffer(ham, dtype=np.uint8)
        img = cv2.imdecode(dizi, cv2.IMREAD_COLOR)
        if img is None:
            return None
        ucx = cv2.resize(img, None, fx=3, fy=3,
                         interpolation=cv2.INTER_CUBIC)
        gri = cv2.cvtColor(ucx, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gri, 120, 255, cv2.THRESH_BINARY_INV)
        cekirdek = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        temiz = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cekirdek)
        adet, etiket, istat, _ = cv2.connectedComponentsWithStats(temiz)
        adaylar = []
        for i in range(1, adet):
            x, y, w, h, alan = istat[i]
            if alan < 150 or h < 28 or h > 220:
                continue
            oran = w / max(1, h)
            if not (0.15 <= oran <= 1.6):
                continue
            dolgu = alan / max(1, w * h)
            if dolgu < 0.22:
                continue
            adaylar.append((x, y, w, h, i))
        if not adaylar:
            return None
        med_h = float(np.median([a[3] for a in adaylar]))
        med_y = float(np.median([a[1] + a[3] / 2.0 for a in adaylar]))
        sonuc = np.full_like(gri, 255)
        for (x, y, w, h, i) in adaylar:
            if abs(y + h / 2.0 - med_y) > med_h * 1.6:
                continue
            if h < med_h * yukseklik_kat:
                continue
            bolge = etiket[y:y + h, x:x + w] == i
            sonuc[y:y + h, x:x + w][bolge] = 0
        kenarli = cv2.copyMakeBorder(sonuc, 24, 24, 24, 24,
                                     cv2.BORDER_CONSTANT, value=255)
        from PIL import Image
        return Image.fromarray(kenarli)
    except Exception:
        return None


def _luca_captcha_adaylari(ham):
    """Captcha görsel baytlarından sıralı OCR adayları üretir.

    Sıra: temizlenmiş görüntü (ddddocr + beta + tesseract) -> ham
    görüntü (ddddocr + beta + çoklu eşik tesseract).
    """
    from PIL import Image, ImageOps
    import pytesseract
    adaylar = []

    def ekle(metin):
        metin = "".join(c for c in str(metin)
                        if c.isalnum() and c.isascii())[:8]
        if len(metin) < 3:
            return
        if metin not in adaylar and metin.lower() not in \
                [a.lower() for a in adaylar]:
            adaylar.append(metin)

    motor = _ddddocr_motoru()
    beta = _ddddocr_beta_motoru()
    for kat in (0.30, 0.0, 0.75):
        temiz = _luca_captcha_temizle(ham, yukseklik_kat=kat)
        if temiz is None:
            continue
        tampon = io.BytesIO()
        temiz.save(tampon, format="PNG")
        temiz_ham = tampon.getvalue()
        if motor:
            try:
                ekle(motor.classification(temiz_ham))
            except Exception:
                pass
        if beta:
            try:
                ekle(beta.classification(temiz_ham))
            except Exception:
                pass
        for psm in ("7", "13"):
            try:
                ekle(pytesseract.image_to_string(
                    temiz, config="--psm " + psm + KARAKTER_KUMESI))
            except Exception:
                continue

    if motor:
        try:
            ekle(motor.classification(ham))
        except Exception:
            pass
    if beta:
        try:
            ekle(beta.classification(ham))
        except Exception:
            pass

    img = Image.open(io.BytesIO(ham))
    buyuk = img.resize((img.width * 4, img.height * 4),
                       Image.LANCZOS).convert("L")
    hist = buyuk.histogram()
    toplam = sum(hist)
    ortalama = sum(i * c for i, c in enumerate(hist)) / max(toplam, 1)
    temel = ImageOps.invert(buyuk) if ortalama < 100 else buyuk
    for esik in (110, 130, 150, 170):
        ikili = temel.point(lambda x, e=esik: 0 if x < e else 255)
        for psm in ("7", "8"):
            try:
                ekle(pytesseract.image_to_string(
                    ikili, config="--psm " + psm + KARAKTER_KUMESI))
            except Exception:
                continue
    return adaylar[:10]


def _luca_captcha_oku(sayfa):
    """Sayfadaki captcha görselini indirip aday metin listesi üretir."""
    src = sayfa.eval_on_selector("#captcha", "e => e.src")
    if not src:
        return []
    if src.startswith("data:image"):
        ham = base64.b64decode(src.split(",", 1)[1])
    else:
        try:
            ham = sayfa.context.request.get(src).body()
        except Exception:
            return []
    return _luca_captcha_adaylari(ham)

LUCA_GIRIS_ADRESI = "https://agiris.luca.com.tr/LUCASSO/giris.erp"
LUCA_GIRIS_ADRESLERI = (
    "https://agiris.luca.com.tr/LUCASSO/giris.erp",
    "https://agiris.luca.com.tr/SSO/giris.erp",
)


class LucaHata(Exception):
    """Kullanıcıya gösterilebilir Luca çekim hatası."""


def _bildir_fonksiyonu(ilerleme):
    return ilerleme if ilerleme else (lambda metin: None)


_BRAVE_YOLU = (r"C:\Program Files\BraveSoftware\Brave-Browser"
               r"\Application\brave.exe")


def _tarayici_ac(playwright, gorunur=False):
    """Luca oturumu icin tarayici acar.

    Luca sunucusu otomasyon bayragini (--enable-automation /
    navigator.webdriver) tespit edip SSO'da 500 dondurdugu icin bu
    bayraklar ozellikle devre disi birakilir.
    """
    ortak = {
        "headless": not gorunur,
        "ignore_default_args": ["--enable-automation"],
        "args": ["--disable-blink-features=AutomationControlled",
                 "--start-maximized"],
    }
    tarayici = None
    if os.path.exists(_BRAVE_YOLU):
        try:
            tarayici = playwright.chromium.launch(
                executable_path=_BRAVE_YOLU, **ortak)
        except Exception:
            tarayici = None
    if tarayici is None:
        for kanal in ("brave", "msedge", "chrome"):
            try:
                tarayici = playwright.chromium.launch(channel=kanal,
                                                      **ortak)
                break
            except Exception:
                continue
    if tarayici is None:
        try:
            tarayici = playwright.chromium.launch(**ortak)
        except Exception as hata:
            raise LucaHata(
                "Tarayıcı başlatılamadı. Edge veya Chrome kurulu olmalı "
                "ya da 'playwright install chromium' çalıştırılmalı.")
    try:
        tarayici._luca_gorunur = gorunur
    except Exception:
        pass
    return tarayici


def _luca_oturum_ac(tarayici, accept_downloads=True):
    """Luca icin tarayici oturumu (context) acar.

    Headless modda UA'daki 'HeadlessChrome' ibaresi sunucuda SSO 500'e
    yol actigi icin temizlenir. Sabit viewport da SSO'yu bozdugu icin
    no_viewport kullanilir.
    """
    user_agent = None
    if not getattr(tarayici, "_luca_gorunur", False):
        try:
            olcum = tarayici.new_context()
            sayfa = olcum.new_page()
            sayfa.goto("about:blank", wait_until="domcontentloaded")
            user_agent = sayfa.evaluate("navigator.userAgent")
            olcum.close()
        except Exception:
            user_agent = None
        if user_agent and "Headless" in user_agent:
            user_agent = user_agent.replace("HeadlessChrome", "Chrome")
        else:
            user_agent = None
    kwargs = {"no_viewport": True}
    if accept_downloads:
        kwargs["accept_downloads"] = True
    if user_agent:
        kwargs["user_agent"] = user_agent
    return tarayici.new_context(**kwargs)


def _hata_ekrani_kaydet(sayfa, etiket):
    try:
        klasor = os.path.join(os.environ.get("TEMP", "."), "opencode")
        os.makedirs(klasor, exist_ok=True)
        yol = os.path.join(klasor, f"luca_{etiket}.png")
        sayfa.screenshot(path=yol, full_page=True)
        with open(os.path.join(klasor, f"luca_{etiket}_url.txt"), "w",
                  encoding="utf-8") as akis:
            akis.write(f"{sayfa.url}\n\n{sayfa.inner_text('body')[:2000]}")
        return yol
    except Exception:
        return ""


def _govde_metni(sayfa):
    try:
        return sayfa.inner_text("body")
    except Exception:
        return ""


def _giris_yapildi_mi(sayfa):
    adres = sayfa.url.lower()
    if "giris.erp" not in adres:
        return True
    return False


def _hata_iletisini_ayikla(metin):
    """Sayfadaki 'HATA ...' bloğundaki mesajı döndürür; yoksa '' döner."""
    satirlar = [s.strip() for s in metin.splitlines()]
    for sira, satir in enumerate(satirlar):
        if satir.upper() == "HATA" and sira + 1 < len(satirlar):
            return satirlar[sira + 1][:120]
    return ""


def _luca_captcha_src(sayfa):
    """Sayfadaki captcha görselinin kaynağını döndürür (değişim takibi)."""
    try:
        return sayfa.eval_on_selector("#captcha", "e => e.src") or ""
    except Exception:
        return ""


def _luca_swal_kapat(sayfa):
    """SweetAlert2 uyarı penceresi açıkssa onay düğmesiyle kapatır."""
    try:
        swal = sayfa.query_selector(".swal2-container")
        if swal is None or not swal.is_visible():
            return
        for secici in (".swal2-confirm", ".swal2-cancel", ".swal2-deny"):
            dugme = sayfa.query_selector(secici)
            if dugme:
                dugme.click(timeout=2000)
                sayfa.wait_for_timeout(600)
                return
        sayfa.keyboard.press("Escape")
        sayfa.wait_for_timeout(500)
    except Exception:
        pass


def _luca_captcha_as(sayfa, bildir, uye_no, kullanici, parola, deneme=12,
                     manuel_bekleme=0):
    """Luca captcha ekranını OCR adaylarıyla aşmaya çalışır.

    Başarıda True; tüm adaylar reddedilirse False döner. Her yanlış
    denemeden sonra HATA penceresi kapatılır; görsel yenilenmişse o
    ekranın adayları tüketilmeden yeni okuma yapılır. Sayfa yenileme
    sonrası giriş formu geri gelirse kimlikleri yeniden gönderir.
    manuel_bekleme > 0 ise OCR tükenince kullanıcıya pencerede captcha'yı
    elle girme şansı tanınır (gorunur tarayıcı gerekir).
    """
    onceki_kaynak = ""
    for tur in range(deneme):
        # Yenileme sonrası temiz giriş formu geldiyse tekrar gönder
        if sayfa.query_selector("#musteriNo") is not None:
            try:
                sayfa.fill("#musteriNo", str(uye_no))
                sayfa.fill("#kullaniciAdi", str(kullanici))
                sayfa.fill("#parola", str(parola))
                sayfa.click("input[type=button][value='GİRİŞ']", timeout=4000)
                sayfa.wait_for_timeout(2000)
            except Exception:
                pass
        kaynak = _luca_captcha_src(sayfa)
        if kaynak and kaynak == onceki_kaynak:
            # Aynı captcha: OCR deterministik, giriş akışını baştan al
            try:
                sayfa.goto(LUCA_GIRIS_ADRESLERI[0],
                           wait_until="domcontentloaded")
                sayfa.wait_for_timeout(1500)
                if sayfa.query_selector("#musteriNo") is not None:
                    sayfa.fill("#musteriNo", str(uye_no))
                    sayfa.fill("#kullaniciAdi", str(kullanici))
                    sayfa.fill("#parola", str(parola))
                    sayfa.click("input[type=button][value='GİRİŞ']",
                                timeout=4000)
                    sayfa.wait_for_timeout(2000)
            except Exception:
                pass
            kaynak = _luca_captcha_src(sayfa)
        onceki_kaynak = kaynak
        adaylar = _luca_captcha_oku(sayfa)[:8]
        for kod in adaylar:
            try:
                sayfa.fill("#captcha-input", kod)
                sayfa.click("input[type=button][value='Tamam']",
                            timeout=3000)
                sayfa.wait_for_timeout(1800)
            except Exception:
                break
            if sayfa.query_selector("#captcha-input") is None:
                bildir(f"Captcha '{kod}' ile geçildi.")
                return True
            _luca_swal_kapat(sayfa)
            if _luca_captcha_src(sayfa) != kaynak:
                break
        try:
            sayfa.reload(wait_until="domcontentloaded")
            sayfa.wait_for_timeout(1500)
        except Exception:
            pass
    if manuel_bekleme > 0:
        bildir(f"OCR captcha'yı çözemedi. Penceredeki captcha'yı "
               f"elle girin ({manuel_bekleme} sn)...")
        for _ in range(manuel_bekleme):
            sayfa.wait_for_timeout(1000)
            if sayfa.query_selector("#captcha-input") is None:
                bildir("Captcha elle girildi; devam ediliyor.")
                return True
    return False


def giris_yap(sayfa, uye_no, kullanici, parola, bildir, manuel_bekleme=0):
    """Luca ortak giriş sayfasından oturum açar; sayfayı döndürür."""
    for i, adres in enumerate(LUCA_GIRIS_ADRESLERI):
        try:
            sayfa.goto(adres, wait_until="domcontentloaded")
            sayfa.wait_for_timeout(1500)
            if sayfa.query_selector("#musteriNo") is not None or \
                    _giris_yapildi_mi(sayfa):
                break
        except Exception:
            if i == len(LUCA_GIRIS_ADRESLERI) - 1:
                raise
            continue
    if sayfa.query_selector("#musteriNo") is None:
        if not _giris_yapildi_mi(sayfa):
            raise LucaHata(
                "Luca giriş sayfası açılamadı (beklenen alan bulunamadı). "
                f"Adres: {sayfa.url[:100]}")
        bildir("Mevcut Luca oturumu kullanılıyor.")
        return sayfa
    sayfa.fill("#musteriNo", str(uye_no))
    sayfa.fill("#kullaniciAdi", str(kullanici))
    sayfa.fill("#parola", str(parola))
    tiklandi = False
    for secici in ("input[type=button][value='GİRİŞ']",
                   "input[type=submit][value='GİRİŞ']", "text=GİRİŞ"):
        try:
            sayfa.click(secici, timeout=4000)
            tiklandi = True
            break
        except Exception:
            continue
    if not tiklandi:
        raise LucaHata("Luca giriş düğmesi bulunamadı.")
    sayfa.wait_for_timeout(1500)
    if sayfa.query_selector("#captcha-input") is not None:
        bildir("Captcha doğrulaması isteniyor...")
        if not _luca_captcha_as(sayfa, bildir, uye_no, kullanici, parola,
                                manuel_bekleme=manuel_bekleme):
            ekran = _hata_ekrani_kaydet(sayfa, "captcha")
            detay = f" Ekran görüntüsü: {ekran}" if ekran else ""
            raise LucaHata(
                "Luca captcha'sı çözülemedi (OCR adayları reddedildi). "
                "Tekrar deneyin." + detay)
    for _ in range(12):
        time.sleep(2)
        metin = _govde_metni(sayfa)
        hata_mesaji = _hata_iletisini_ayikla(metin)
        if hata_mesaji:
            try:
                sayfa.click("text=TAMAM", timeout=2000)
            except Exception:
                pass
            raise LucaHata("Luca girişi reddedildi: " + hata_mesaji)
        if "hatalı" in metin.lower() and "parola" in metin.lower():
            raise LucaHata(
                "Luca girişi reddedildi: Üye numarası, kullanıcı adı veya "
                "parola hatalı.")
        if _giris_yapildi_mi(sayfa):
            bildir("Luca'ya giriş başarılı.")
            return sayfa
    ekran = _hata_ekrani_kaydet(sayfa, "giris")
    detay = f" Ekran görüntüsü: {ekran}" if ekran else ""
    raise LucaHata(
        "Luca girişi doğrulanamadı (sayfa giriş ekranında kaldı). İki aşamalı "
        f"doğrulama isteniyor olabilir.{detay}")


def _aktif_sayfa(oturum, mevcut):
    """Yeni sekme/pop-up açıldıysa ona geçer; aksi halde mevcudu döndürür."""
    try:
        sayfalar = [s for s in oturum.pages if not s.is_closed()]
        if sayfalar and sayfalar[-1] is not mevcut:
            return sayfalar[-1]
    except Exception:
        pass
    return mevcut


def _menu_elemani_tikla(sayfa, desen, aciklama, bildir, zaman_asimi=6):
    """Metni desene uyan ilk görünür öğeye tıklar; başarıda True döner."""
    derleme = re.compile(desen, re.IGNORECASE)
    bitis = time.time() + zaman_asimi
    while time.time() < bitis:
        try:
            ogeler = sayfa.query_selector_all(
                "a, span, td, th, div[onclick], label, li, b")
            for oge in ogeler:
                try:
                    if not oge.is_visible():
                        continue
                    metin = (oge.inner_text() or "").strip()
                    if metin and derleme.search(metin) and len(metin) < 80:
                        bildir(f"{aciklama}: '{metin[:50]}' tıklanıyor...")
                        oge.click()
                        sayfa.wait_for_timeout(2000)
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        time.sleep(1)
    return False


def _tarih_alanlarini_doldur(sayfa, bas_tarih, bit_tarih, bildir):
    """Rapor ekranındaki tarih alanlarını bulup doldurmaya çalışır."""
    bas_metin = bas_tarih.strftime("%d.%m.%Y")
    bit_metin = bit_tarih.strftime("%d.%m.%Y")
    doldurulan = 0
    for secici in ("input[name*='Tarih' i]", "input[id*='Tarih' i]",
                   "input[name*='tarih']", "input[id*='tarih']"):
        try:
            ogeler = sayfa.query_selector_all(secici)
        except Exception:
            continue
        for oge in ogeler:
            try:
                if not oge.is_visible():
                    continue
                deger = (oge.input_value() or "").strip()
                if deger and re.match(r"^\d{2}\.\d{2}\.\d{4}$", deger):
                    continue
                if doldurulan == 0:
                    oge.fill(bas_metin, force=True)
                    doldurulan += 1
                elif doldurulan == 1:
                    oge.fill(bit_metin, force=True)
                    doldurulan += 1
                    break
            except Exception:
                continue
        if doldurulan >= 2:
            break
    if doldurulan < 2:
        bildir("UYARI: Tarih alanları otomatik doldurulamadı; sayfanın kendi "
               "varsayılan dönemi kullanılacak.")
    return doldurulan


def _indir_butonu_tikla(sayfa, desenler, zaman_asimi=8):
    """Desenlere uyan ilk görünür düğmeye tıklar; True/False döner."""
    derlemeler = [re.compile(d, re.IGNORECASE) for d in desenler]
    bitis = time.time() + zaman_asimi
    while time.time() < bitis:
        try:
            ogeler = sayfa.query_selector_all(
                "input[type=button], input[type=submit], button, a")
            for oge in ogeler:
                try:
                    if not oge.is_visible():
                        continue
                    metin = ((oge.get_attribute("value") or "")
                             + " " + (oge.inner_text() or "")).strip()
                    if any(d.search(metin) for d in derlemeler):
                        oge.click()
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        time.sleep(1)
    return False


def _hesap_alanlarini_doldur(sayfa, hesap_kodu):
    """Başlangıç ve Bitiş hesap kodu alanlarını aynı kodla doldurur.

    Luca muavin raporunda aralık iki alandır; her ikisine de aynı kodu
    yazmak (örn. 191 -> 191) yalnız o hesabın dökümünü verir.
    """
    doldurulan = 0
    for secici in ("input[name*='Hesap' i]", "input[id*='Hesap' i]",
                   "input[name*='hesap']", "input[id*='hesap']"):
        try:
            ogeler = sayfa.query_selector_all(secici)
        except Exception:
            continue
        for oge in ogeler:
            try:
                if oge.is_visible() and not (oge.input_value() or "").strip():
                    oge.fill(hesap_kodu, force=True)
                    doldurulan += 1
                    if doldurulan >= 2:
                        return True
            except Exception:
                continue
    return doldurulan > 0


def cek_muavin(uye_no, kullanici, parola, bas_tarih, bit_tarih, hedef_klasor,
               hesap_kodlari=("191", "391"), ilerleme=None):
    """Luca'dan muavin dökümünü Excel olarak indirir.

    Dönen değer: indirilen dosya yolları listesi.
    """
    bildir = _bildir_fonksiyonu(ilerleme)
    os.makedirs(hedef_klasor, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise LucaHata("Playwright kurulu değil. Kurulum: pip install playwright")

    dosyalar = []
    with sync_playwright() as p:
        tarayici = _tarayici_ac(p)
        oturum = _luca_oturum_ac(tarayici)
        sayfa = oturum.new_page()
        try:
            sayfa = giris_yap(sayfa, uye_no, kullanici, parola, bildir)
            sayfa.wait_for_timeout(2500)

            # Modul/menu gezinmesi: Genel Muhasebe -> Raporlar -> Muavin
            if _menu_elemani_tikla(sayfa, r"genel\s*muhasebe", "Modül",
                                   bildir, zaman_asimi=4):
                sayfa = _aktif_sayfa(oturum, sayfa)
                sayfa.wait_for_timeout(1500)
            if _menu_elemani_tikla(sayfa, r"^raporlar?\b", "Menü", bildir,
                                   zaman_asimi=3):
                sayfa = _aktif_sayfa(oturum, sayfa)
                sayfa.wait_for_timeout(1000)
            if not _menu_elemani_tikla(sayfa, r"muavin\s*defter|muavin",
                                       "Rapor", bildir, zaman_asimi=8):
                ekran = _hata_ekrani_kaydet(sayfa, "menu")
                detay = f" Ekran görüntüsü: {ekran}" if ekran else ""
                raise LucaHata(
                    "Luca menüsünde 'Muavin' bağlantısı bulunamadı. Uygulama "
                    "menüsü farklı olabilir." + detay)
            sayfa = _aktif_sayfa(oturum, sayfa)
            sayfa.wait_for_timeout(1500)

            for hesap in hesap_kodlari:
                donem_etiketi = bas_tarih.strftime("%Y%m")
                hedef = os.path.join(
                    hedef_klasor,
                    f"luca_muavin_{hesap}_{donem_etiketi}.xlsx")
                try:
                    bildir(f"Hesap {hesap} muavini sorgulanıyor...")
                    _tarih_alanlarini_doldur(sayfa, bas_tarih, bit_tarih,
                                             bildir)
                    _hesap_alanlarini_doldur(sayfa, hesap)
                    # Rapor Türü seçimi: varsa Excel'i işaretle
                    excel_secildi = _indir_butonu_tikla(
                        sayfa, (r"^excel$",), zaman_asimi=2)
                    if excel_secildi:
                        bildir("Rapor türü Excel olarak seçildi.")
                    raporda_indi = False
                    try:
                        with sayfa.expect_download(timeout=25000) as indirme:
                            _indir_butonu_tikla(
                                sayfa, (r"^rapor$", r"^liste$", r"listele",
                                        r"sorgula", r"getir"),
                                zaman_asimi=6)
                        dosya = indirme.value
                        dosya.save_as(hedef)
                        dosyalar.append(hedef)
                        raporda_indi = True
                        bildir(f"İndirildi: {os.path.basename(hedef)}")
                    except Exception:
                        pass
                    if not raporda_indi:
                        # Rapor ekranda açıldı; ayrı Excel/döküm düğmesi ara
                        try:
                            with sayfa.expect_download(
                                    timeout=20000) as indirme:
                                if not _indir_butonu_tikla(
                                        sayfa, (r"excel", r"\bxls\b",
                                                r"aktar", r"döküm\s*al")):
                                    raise RuntimeError(
                                        "Excel/döküm düğmesi bulunamadı")
                            dosya = indirme.value
                            dosya.save_as(hedef)
                            dosyalar.append(hedef)
                            raporda_indi = True
                            bildir(f"İndirildi: {os.path.basename(hedef)}")
                        except Exception as hata:
                            bildir(f"Hesap {hesap}: döküm alınamadı "
                                   f"({str(hata)[:70]}).")
                        if not raporda_indi:
                            _hata_ekrani_kaydet(sayfa, f"rapor_{hesap}")
                except LucaHata:
                    raise
                except Exception as hata:
                    bildir(f"Hesap {hesap} hatası: {str(hata)[:90]}")
        finally:
            tarayici.close()
    if not dosyalar:
        raise LucaHata(
            "Luca'dan muavin dökümü indirilemedi. Hesap ekranları müşteriye "
            "özgü olabilir; muavin dosyalarını elle seçerek devam edebilirsiniz.")
    return dosyalar


def _firma_adaylari(sayfa):
    """SMM uye girisi sonrasi ekrandaki firma secim adaylarini toplar.

    Tablo satirlari ve select opsiyonlarindan VKN/TCKN desenli kayitlari
    ayiklar; yapi musteriye gore degisebildigi icin best-effort calisir.
    """
    adaylar = []
    gorulen = set()
    for tr in sayfa.query_selector_all("table tr, [role='row']"):
        try:
            metin = " ".join((tr.inner_text() or "").split())
        except Exception:
            continue
        m = re.search(r"\b(\d{10,11})\b", metin)
        if m and len(metin) >= 8 and metin not in gorulen:
            gorulen.add(metin)
            adaylar.append({"vkn": m.group(1), "metin": metin[:140],
                            "tur": "satir"})
    for opt in sayfa.query_selector_all("select option"):
        try:
            metin = " ".join((opt.inner_text() or "").split())
        except Exception:
            continue
        m = re.search(r"\b(\d{10,11})\b", metin)
        if m and metin not in gorulen:
            gorulen.add(metin)
            adaylar.append({"vkn": m.group(1), "metin": metin[:140],
                            "tur": "opsiyon",
                            "deger": opt.get_attribute("value")})
    return adaylar


def firma_sec(sayfa, vkn, bildir=None):
    """VKN'a uyan firmayi secim ekraninda secer; bulunamazsa LucaHata."""
    bildir = bildir or (lambda s: None)
    adaylar = _firma_adaylari(sayfa)
    hedef = None
    for a in adaylar:
        if a["vkn"] == str(vkn).strip():
            hedef = a
            break
    if hedef is None:
        _hata_ekrani_kaydet(sayfa, "firma_bulunamadi")
        raise LucaHata(f"VKN {vkn} için firma seçiminde bulunamadı "
                       f"({len(adaylar)} aday görüldü).")
    try:
        if hedef["tur"] == "opsiyon":
            sayfa.select_option("select",
                                value=hedef.get("deger") or hedef["metin"])
        else:
            sayfa.click(f"text={hedef['metin'][:60]}", timeout=8000)
    except Exception:
        try:
            sayfa.click(f"text={hedef['vkn']}", timeout=8000)
        except Exception as hata:
            raise LucaHata(f"Firma seçilemedi: {str(hata)[:80]}")
    bildir(f"Firma seçildi: {hedef['metin'][:60]}")
    return hedef


def kesif_raporu(oturum, sayfa, klasor):
    """Aktif ekranin yapisini haritalar: linkler, dugmeler, iframe'ler,
    menu ogeleri + tam ekran goruntusu + HTML dokumu.

    Donen deger: bulunan oge ozetleri sozlugu.
    """
    os.makedirs(klasor, exist_ok=True)
    sayfa = _aktif_sayfa(oturum, sayfa)

    def _liste(secici, nitelik="textContent", sinir=200):
        cikti = []
        for e in sayfa.query_selector_all(secici)[:sinir]:
            try:
                t = " ".join((e.inner_text() or "").split())[:90]
                h = e.get_attribute("href") or ""
                if t or h:
                    cikti.append({"metin": t, "href": h[:160]})
            except Exception:
                pass
        return cikti

    rapor = {
        "url": sayfa.url,
        "baslik": sayfa.title(),
        "linkler": _liste("a"),
        "dugmeler": _liste("button, input[type='button'], "
                           "input[type='submit']"),
        "iframeler": [],
        "menuler": _liste("[class*='menu'] li, nav a, [role='menuitem']"),
    }
    for f in sayfa.query_selector_all("iframe"):
        try:
            rapor["iframeler"].append({
                "src": (f.get_attribute("src") or "")[:160],
                "ad": f.get_attribute("name") or ""})
        except Exception:
            pass
    try:
        rapor["html_uzunluk"] = len(sayfa.content())
        with open(os.path.join(klasor, "sayfa.html"), "w",
                  encoding="utf-8", errors="replace") as d:
            d.write(sayfa.content())
    except Exception:
        pass
    import json
    with open(os.path.join(klasor, "rapor.json"), "w", encoding="utf-8",
              errors="replace") as d:
        json.dump(rapor, d, ensure_ascii=False, indent=1)
    _hata_ekrani_kaydet(sayfa, "kesif")
    return rapor

# ---------------- e-Belge cekimi (e-Fatura / e-Arsiv, alis+satis) ----------------

LUCA_BELGE_KATEGORILERI = (
    ("efatura_alis", r"e\s*[-\s]?fatura",
     (r"gelen", r"al[ıi]nan", r"inbox", r"al[ıi][şs]")),
    ("efatura_satis", r"e\s*[-\s]?fatura",
     (r"giden", r"g[öo]nderilen", r"outbox", r"d[üu]zenlenen",
      r"sat[ıi][şs]")),
    ("earsiv_alis", r"e\s*[-\s]?ar[şs]iv",
     (r"gelen", r"al[ıi]nan", r"al[ıi][şs]")),
    ("earsiv_satis", r"e\s*[-\s]?ar[şs]iv",
     (r"giden", r"g[öo]nderilen", r"d[üu]zenlenen", r"sat[ıi][şs]")),
)


def _belge_sorgula_ve_indir(sayfa, hedef, bildir):
    """Ekranda tarihleri doldurmus varsayarak sorgula + Excel indir.

    Once sorgulama dongusuyle dogrudan indirmeyi, olmazsa ayri Excel/dokum
    dugmesini dener. Basarida True doner.
    """
    raporda_indi = False
    try:
        with sayfa.expect_download(timeout=25000) as indirme:
            _indir_butonu_tikla(
                sayfa, (r"^rapor$", r"^liste$", r"listele", r"sorgula",
                        r"getir"), zaman_asimi=6)
        indirme.value.save_as(hedef)
        raporda_indi = True
    except Exception:
        pass
    if not raporda_indi:
        try:
            with sayfa.expect_download(timeout=20000) as indirme:
                if not _indir_butonu_tikla(
                        sayfa, (r"excel", r"\bxls\b", r"aktar",
                                r"d[öo]k[üu]m\s*al")):
                    raise RuntimeError("Excel/döküm düğmesi bulunamadı")
            indirme.value.save_as(hedef)
            raporda_indi = True
        except Exception as hata:
            bildir(f"Döküm alınamadı ({str(hata)[:70]}).")
    return raporda_indi


def _aralik_parcalara_bol(bas_tarih, bit_tarih, adim_gun):
    """Tarih aralığını en fazla adim_gun günlük parçalara böler."""
    parcalar = []
    b = bas_tarih
    while b <= bit_tarih:
        s = min(b.fromordinal(b.toordinal() + adim_gun - 1), bit_tarih)
        parcalar.append((b, s))
        b = b.fromordinal(b.toordinal() + adim_gun)
    return parcalar


def _dosya_saglam(yol):
    """İndirilen dosya makul boyutta mı (boş/yanlış sayfa indirmesi)."""
    try:
        return os.path.getsize(yol) >= 400
    except OSError:
        return False


def _satir_sayisini_buyut(sayfa, bildir):
    """Sayfalama satır seçicisinde yüksek değer/‘tümü’ seçer (best effort)."""
    try:
        return _indir_butonu_tikla(
            sayfa, (r"^\s*(t[üu]m[üu]|500|1000|2000)\s*$",
                    r"sat[ıi]r\s*say[ıi]s"), zaman_asimi=2)
    except Exception:
        return False


def cek_luca_belgeleri(uye_no, kullanici, parola, bas_tarih, bit_tarih,
                       hedef_klasor, kategoriler=None, ilerleme=None,
                       gorunur=False, manuel_captcha=False):
    """Luca'dan dort belge kategorisini indirir:
    efatura_alis, efatura_satis, earsiv_alis, earsiv_satis.

    Tek girisle tum kategoriler denenir. Belge sayisi yuksekse (1000-2000+)
    once tum aralik tek indirmede denenir; olmazsa aralik otomatik 10 gunluk,
    takilan parcalar 1 gunluk bolunerek surdurulur. Her parca ayri dosyadir:
    luca_{kategori}_{bas}_{bit}.xlsx

    gorunur=True tarayiciyi ekranda acar; manuel_captcha=True ile OCR
    basarisizsa kullaniciya captcha'yi elle girme süresi taninir.

    Donen deger: {kategori: [dosya_yollari]}. Basarisiz kategori ekran
    goruntusuyle atlanir. Hicbiri inmezse LucaHata.
    """
    bildir = _bildir_fonksiyonu(ilerleme)
    os.makedirs(hedef_klasor, exist_ok=True)
    hedefler = kategoriler or [k for k, _, _ in LUCA_BELGE_KATEGORILERI]
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise LucaHata("Playwright kurulu değil. Kurulum: pip install playwright")

    sonuc = {}
    with sync_playwright() as p:
        tarayici = _tarayici_ac(p, gorunur=gorunur)
        oturum = _luca_oturum_ac(tarayici)
        sayfa = oturum.new_page()
        try:
            sayfa = giris_yap(sayfa, uye_no, kullanici, parola, bildir,
                              manuel_bekleme=180 if manuel_captcha else 0)
            sayfa.wait_for_timeout(2500)

            def parca_cek(kategori, bas, bit):
                hedef = os.path.join(
                    hedef_klasor,
                    f"luca_{kategori}_"
                    f"{bas.strftime('%Y%m%d')}_{bit.strftime('%Y%m%d')}.xlsx")
                if _dosya_saglam(hedef):
                    return hedef
                if not _tarih_alanlarini_doldur(sayfa, bas, bit, bildir):
                    raise RuntimeError("tarih alanları doldurulamadı")
                if _belge_sorgula_ve_indir(sayfa, hedef, bildir):
                    if _dosya_saglam(hedef):
                        return hedef
                    try:
                        os.remove(hedef)
                    except OSError:
                        pass
                    raise RuntimeError("indirilen dosya boş görünüyor")
                raise RuntimeError("indirme başarısız")

            for kategori in hedefler:
                tanim = next((t for t in LUCA_BELGE_KATEGORILERI
                              if t[0] == kategori), None)
                if tanim is None:
                    bildir(f"Bilinmeyen kategori atlandı: {kategori}")
                    continue
                modul_deseni, alt_desenler = tanim[1], tanim[2]
                bildir(f"{kategori}: ekran aranıyor...")
                dosyalar = []
                try:
                    if not _menu_elemani_tikla(sayfa, modul_deseni,
                                               "Modül", bildir, zaman_asimi=5):
                        raise RuntimeError("modül menüsü bulunamadı")
                    sayfa = _aktif_sayfa(oturum, sayfa)
                    sayfa.wait_for_timeout(1500)
                    if not any(_menu_elemani_tikla(sayfa, d, "Alt menü",
                                                   bildir, zaman_asimi=3)
                               for d in alt_desenler):
                        raise RuntimeError("alt menü bulunamadı")
                    sayfa = _aktif_sayfa(oturum, sayfa)
                    sayfa.wait_for_timeout(1200)
                    _satir_sayisini_buyut(sayfa, bildir)

                    # 1) Tum aralik tek seferde
                    try:
                        yol = parca_cek(kategori, bas_tarih, bit_tarih)
                        dosyalar.append(yol)
                        bildir(f"{kategori}: tüm dönem tek dosyada indi.")
                    except Exception:
                        # 2) 10 gunluk parcalar; olmayan gun 1 gune bolunur
                        dosyalar = []
                        on_gunluk = _aralik_parcalara_bol(bas_tarih,
                                                          bit_tarih, 10)
                        for pi, (pb, ps) in enumerate(on_gunluk, 1):
                            try:
                                yol = parca_cek(kategori, pb, ps)
                                dosyalar.append(yol)
                                bildir(f"{kategori}: parça {pi}/"
                                       f"{len(on_gunluk)} indi "
                                       f"({pb:%d.%m}-{ps:%d.%m}).")
                            except Exception:
                                if pb == ps:
                                    bildir(f"{kategori}: {pb:%d.%m} "
                                           "günü inmedi.")
                                    continue
                                for (gb, gs) in \
                                        _aralik_parcalara_bol(pb, ps, 1):
                                    try:
                                        dosyalar.append(parca_cek(
                                            kategori, gb, gs))
                                    except Exception:
                                        bildir(f"{kategori}: {gb:%d.%m} "
                                               "günü inmedi.")
                        if dosyalar:
                            bildir(f"{kategori}: parçalı çekim tamam, "
                                   f"{len(dosyalar)} dosya.")
                    if dosyalar:
                        sonuc[kategori] = dosyalar
                    else:
                        _hata_ekrani_kaydet(sayfa, f"belge_{kategori}")
                except Exception as hata:
                    if dosyalar:
                        sonuc[kategori] = dosyalar
                    else:
                        bildir(f"{kategori} çekilemedi: {str(hata)[:80]}")
                        _hata_ekrani_kaydet(sayfa, f"belge_{kategori}")
        finally:
            tarayici.close()
    if not sonuc:
        raise LucaHata(
            "Luca'dan hiçbir e-Belge kategorisi indirilemedi. Ekranlar "
            "müşteri yapılandırmasına göre değişebilir; keşif raporu "
            "gerekli.")
    return sonuc
