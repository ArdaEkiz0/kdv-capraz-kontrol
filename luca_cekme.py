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
import html as html_cevir
import io
import json
import os
import re
import time
import zipfile
from datetime import date, datetime

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


def _luca_captcha_as(sayfa, bildir, uye_no, kullanici, parola,
                     manuel_bekleme=180):
    """Luca captcha'sini kullanicinin elle girmesini bekler.

    Tarayici gorunur olmalidir; kullanici #captcha-input alanina kodu
    yazip Tamam'a basar. Yanlis girişte çıkan HATA penceresi otomatik
    kapatılır, kullanıcı aynı ekranda yeniden deneyebilir. Oturum
    sıfırlanıp giriş formu geri gelirse kimlikler yeniden gönderilir.
    Sure dolarsa False doner.
    """
    if sayfa.query_selector("#captcha-input") is None:
        return True
    bekleme = manuel_bekleme if manuel_bekleme > 0 else 180
    bildir(f"Captcha isteniyor: tarayıcı penceresindeki alana görüntüdeki "
           f"kodu elle girip Tamam'a basın ({bekleme} sn)...")
    for _ in range(bekleme):
        sayfa.wait_for_timeout(1000)
        if sayfa.query_selector("#captcha-input") is None:
            bildir("Captcha girildi; devam ediliyor.")
            return True
        _luca_swal_kapat(sayfa)
        # Oturum sıfırlanıp temiz giriş formu geldiyse tekrar gönder
        if sayfa.query_selector("#musteriNo") is not None:
            try:
                sayfa.fill("#musteriNo", str(uye_no))
                sayfa.fill("#kullaniciAdi", str(kullanici))
                sayfa.fill("#parola", str(parola))
                sayfa.click("input[type=button][value='GİRİŞ']", timeout=4000)
                sayfa.wait_for_timeout(1500)
            except Exception:
                pass
    bildir("Captcha süresi doldu.")
    return False


def giris_yap(sayfa, uye_no, kullanici, parola, bildir, manuel_bekleme=180):
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
                "Captcha süresi içinde girilmedi. Tekrar deneyin ve "
                "tarayıcı penceresindeki captcha'yı zamanında girin." + detay)
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

# Luca ERP'de gib530.do ekranlarinin 'tur' parametre karsiliklari.
LUCA_GIB_TURLER = {
    "efatura_alis": "gib_efatura_alis",
    "efatura_satis": "gib_efatura_satis",
    "earsiv_alis": "gib_ebelge_alis",
    "earsiv_satis": "gib_ebelge_satis",
}


def _turk_kucult(metin):
    """Turkce buyuk harfleri de kuculterek karsilastirma metni uretir.

    I/ı/i farki da esitlenir; boylece 'KIRAZLAR' ile 'KİRAZLAR' ortak
    ibareye iner.
    """
    return (metin.replace("İ", "i").replace("I", "i").replace("Ş", "ş")
            .replace("Ğ", "ğ").replace("Ü", "ü").replace("Ö", "ö")
            .replace("Ç", "ç")).replace("ı", "i").lower()


def _erp_penceresi(oturum, sayfa, bildir):
    """Portalda gonder('formTarget') tetikler; acilan ERP sekmesini dondurur.

    Yeni sekme auygs.luca.com.tr SSO'sundan gecer; otomasyon bayraklari
    kapali degilse sunucu 500 dondurdugu icin _tarayici_ac zorunludur.
    """
    popuplar = []
    oturum.on("page", lambda y: popuplar.append(y))
    sayfa.evaluate("gonder('formTarget')")
    bildir("Mali Müşavir Paketi penceresi açılıyor...")
    for _ in range(30):
        time.sleep(2)
        if not popuplar:
            continue
        hedef = popuplar[0]
        try:
            if len(hedef.content()) > 3000 or len(hedef.frames) > 1:
                hedef.wait_for_timeout(4000)
                return hedef
        except Exception:
            continue
    raise LucaHata(
        "Luca ERP penceresi açılamadı. Sunucu SSO isteğini reddetti "
        "(oturum çakışması olabilir; birkaç dakika sonra deneyin).")


def _firma_donem_sec(erp, firma_adi, bas_tarih, bildir):
    """ERP ust cercevesinde sirket + donem secip Tamam'a basar."""
    ust = None
    for f in erp.frames:
        try:
            if f.query_selector("#SirketCombo"):
                ust = f
                break
        except Exception:
            continue
    if ust is None:
        raise LucaHata("Firma seçim alanı (SirketCombo) bulunamadı.")
    secenekler = ust.eval_on_selector_all(
        "#SirketCombo option",
        "os => os.map(o => ({v:o.value,t:o.textContent.trim()}))"
        ".filter(x => x.v && x.v !== '0')")
    if not secenekler:
        raise LucaHata("Firma listesi boş geldi.")
    if firma_adi:
        ibare = _turk_kucult(firma_adi)
        eslesen = [s for s in secenekler
                   if ibare in _turk_kucult(s["t"])]
        if not eslesen:
            ornekler = ", ".join(s["t"] for s in secenekler[:6])
            raise LucaHata(f"Firma bulunamadı: {firma_adi} "
                           f"(örnek firmalar: {ornekler})")
        hedef = eslesen[0]
        if len(eslesen) > 1:
            bildir(f"Dikkat: '{firma_adi}' ile {len(eslesen)} firma "
                   f"eşleşti, ilk seçiliyor ({hedef['t']}).")
    else:
        if len(secenekler) != 1:
            raise LucaHata(
                f"firma_adi belirtilmeli (hesapta {len(secenekler)} "
                "firma var).")
        hedef = secenekler[0]
    ust.select_option("#SirketCombo", hedef["v"])
    ust.wait_for_timeout(800)
    donemler = ust.eval_on_selector_all(
        "#DonemCombo option",
        "os => os.map(o => ({v:o.value,t:o.textContent.trim()}))"
        ".filter(x => x.v && x.v !== '0')")
    yil = str(bas_tarih.year)
    donem = next((d for d in donemler if yil in d["t"]), None)
    if donem is None and donemler:
        donem = donemler[0]
    if donem is None:
        raise LucaHata("Bu firmaya ait dönem bulunamadı.")
    ust.select_option("#DonemCombo", donem["v"])
    ust.wait_for_timeout(500)
    ust.click("button:has-text('Tamam')")
    bildir(f"Firma/dönem seçildi: {hedef['t']} / {donem['t']}")
    time.sleep(8)
    return hedef["t"], donem["t"]


def _gib530_frame(erp, tur, uye_no, bildir=None):
    """Ana icerik cercevesini istenen gib530 ekranina goturur ve frame'i
    dondurur; yuklenmezse None doner.

    Firma secimi sonrasi cerceveler yeniden yuklendigi icin ilk
    denemede 'execution context destroyed' hatasi normaldir; gezinme
    araliklarla yeniden denenir.
    """
    adres = f"gib530.do?tur={tur}&c_musteri_id={uye_no}"
    for deneme in range(10):
        try:
            if deneme in (0, 3, 6):
                erp.evaluate(
                    "u => { top.frames['frm3'].location.href = u; }",
                    adres)
        except Exception:
            pass
        time.sleep(2)
        for f in erp.frames:
            try:
                if "gib530" in f.url and len(f.content()) > 5000:
                    return f
            except Exception:
                continue
    if bildir is not None:
        try:
            nerede = erp.evaluate(
                "top.frames['frm3'] "
                "? top.frames['frm3'].location.href : 'frm3 yok'")
            bildir(f"frm3 durumu: {str(nerede)[:100]}")
        except Exception:
            pass
    return None


_FATURA_JSON = re.compile(r'fatura="([^"]+)"')


def _satirlari_ayikla(html_metin):
    """gib530 listesindeki her satirin 'fatura' JSON ozelligini cozer.

    Donen liste [(satir_sirasi, sozluk), ...]; satir_sirasi DOM sirasidir
    ve ZIP indirme tuslarinin sirasiyla birebir ortusur.
    """
    satirlar = []
    for sira, ham in enumerate(_FATURA_JSON.findall(html_metin)):
        try:
            veri = json.loads(html_cevir.unescape(ham))
        except Exception:
            continue
        satirlar.append((sira, veri))
    return satirlar


def _tarih_araliginda(metin, bas_tarih, bit_tarih):
    try:
        gun = datetime.strptime(metin, "%d/%m/%Y").date()
    except (TypeError, ValueError):
        return False
    return bas_tarih <= gun <= bit_tarih


def _zip_tikla_indir(frame, sayfa, satir_sirasi, hedef_yol):
    """Satirdaki ZIP ikonuna tiklar; indigi dosyayi kaydeder."""
    with sayfa.expect_download(timeout=30000) as bekle:
        frame.evaluate(
            "n => { const e = [...document.querySelectorAll('[onclick]')]"
            ".filter(x => x.getAttribute('onclick').includes('zip_indir'))"
            "[n]; if (!e) throw new Error('ZIP düğmesi yok'); e.click(); }",
            satir_sirasi)
    indirme = bekle.value
    indirme.save_as(hedef_yol)
    return indirme.suggested_filename


def _ubl_ozet(xml_bytes):
    """UBL fatura XML'inden tutarlari cikarir.

    Kurallar:
    - Para birimi TRY olan degerler oncelidir; hic TRY yoksa belge
      para birimi kullanilir ve 'para' alanindan anlasilir.
    - Bazi gondericiler TaxTotal bloklarini tekrarlar; dogrudan TaxAmount
      ile kendi TaxSubtotal toplami tutarli olmayan bloklar sayilmaz,
      boylece KDV iki katına cikmaz.
    - oran_kalemleri: her KDV orani icin {"oran", "matrah", "kdv"}
      sozlugu; cok oranli faturalar capraz kontrolde oran basina
      degerlendirilir. (Uygulamanin diger yerlerindeki oranlar=[18, 8]
      duz oran listesinden farkli alandir.)
    """
    try:
        import xml.etree.ElementTree as ET
        kok = ET.fromstring(xml_bytes)
    except Exception:
        return {}

    def yerel(etiket):
        return etiket.split("}")[-1]

    def sayi(metin):
        try:
            return float((metin or "0").replace(",", "."))
        except ValueError:
            return None

    bloklar = []
    for eb in kok.iter():
        if yerel(eb.tag) != "TaxTotal":
            continue
        dogrudan = None
        para_b = ""
        alt = []
        for el in eb:
            ad = yerel(el.tag)
            if ad == "TaxAmount":
                dogrudan = sayi(el.text)
                para_b = el.get("currencyID") or para_b
            elif ad == "TaxSubtotal":
                yuzde = None
                taban_t = None
                alt_kdv = None
                for a in el:
                    aa = yerel(a.tag)
                    if aa == "Percent":
                        yuzde = sayi(a.text)
                    elif aa == "TaxableAmount":
                        taban_t = sayi(a.text)
                    elif aa == "TaxAmount":
                        alt_kdv = sayi(a.text)
                if yuzde is not None and alt_kdv is not None:
                    alt.append({"oran": round(yuzde, 2),
                                "matrah": round(taban_t, 2)
                                if taban_t is not None else None,
                                "kdv": round(alt_kdv, 2)})
        tutarli = bool(alt) and dogrudan is not None and \
            abs(sum(a["kdv"] for a in alt) - dogrudan) <= 0.02
        bloklar.append({"para": para_b, "dogrudan": dogrudan,
                        "alt": alt, "tutarli": tutarli})

    secili = [b for b in bloklar if b["tutarli"]]
    if not secili:
        secili = [b for b in bloklar if b["alt"]] or bloklar

    genels = []
    matrahs = []
    for el in kok.iter():
        ad = yerel(el.tag)
        if ad == "PayableAmount":
            genels.append((sayi(el.text),
                           el.get("currencyID") or ""))
        elif ad == "TaxExclusiveAmount":
            matrahs.append((sayi(el.text),
                            el.get("currencyID") or ""))

    def tercih(ciftler):
        temiz = [(d, p) for d, p in ciftler if d is not None]
        if not temiz:
            return None, ""
        for d, p in temiz:
            if p in ("TRY", "TL"):
                return d, "TRY"
        return temiz[0]

    genel_toplam, genel_para = tercih(genels)
    matrah, matrah_para = tercih(matrahs)

    # Blok secimi: gondericiler hem satir kirilimini hem belge toplamini
    # ayri TaxTotal bloklari olarak yazabiliyor. Tabanlari toplami KDV-
    # haric matraya esit olan blok(lar) gercek vergi bilesenleridir;
    # matraya eslesen tek blok varsa digerleri (kismi/kopya) atlanir.
    if len(secili) > 1 and matrah is not None:
        tam_bloklar = [b for b in secili
                       if abs(sum((a.get("matrah") or 0.0)
                                  for a in b["alt"]) - matrah) <= 0.05]
        if len(tam_bloklar) == 1:
            secili = tam_bloklar

    # Alt kalemleri temizle: belge duzeyinde tekrarlanan ozet satirini
    # (tabani diger satirlarin toplami) ve sent kopyalarini kaldirir.
    tum_alt = []
    for b in secili:
        tum_alt.extend(b["alt"])
    temiz = []
    for i, a in enumerate(tum_alt):
        taban_a = a.get("matrah")
        if taban_a is None:
            continue
        digerler = [x for j, x in enumerate(tum_alt) if j != i]
        if digerler and abs(
                sum((x.get("matrah") or 0.0) for x in digerler)
                - taban_a) <= 0.05:
            continue
        temiz.append(a)

    oranlar = []
    for a in sorted(temiz,
                    key=lambda x: (-x["oran"], -x["kdv"])):
        benzer = [b for b in oranlar
                  if b["oran"] == a["oran"]
                  and abs(b["kdv"] - a["kdv"]) <= 0.05]
        if not benzer:
            oranlar.append(a)

    # KDV toplami: tutarli bloklarin dogrudan degerleri; yakin degerler
    # tek sayilir (tekrarlanan TaxTotal bloklari yaygin).
    kdvs = []
    for b in secili:
        d = b["dogrudan"]
        if d is None:
            continue
        if not any(abs(d - y) <= 0.05 for y in kdvs):
            kdvs.append(round(d, 2))

    para = "TRY" if (genel_para == "TRY" or matrah_para == "TRY"
                     or any(b["para"] in ("TRY", "TL")
                            for b in secili)) else (
        genel_para or (secili[0]["para"] if secili else ""))

    ozet = {}
    if matrahs:
        ozet["matrah"] = round(matrah, 2)
    if kdvs:
        ozet["kdv_toplam"] = round(sum(kdvs), 2)
    if genel_toplam is not None:
        ozet["genel_toplam"] = round(genel_toplam, 2)
    if para:
        ozet["para"] = para
    if oranlar:
        ozet["oran_kalemleri"] = oranlar
    return ozet


def _ozet_tablo_yaz(yol, kayitlar):
    """Belge ozetini .xlsx olarak yazar; openpyxl yoksa .csv dener."""
    sutunlar = [("belge_numarasi", "Belge No"),
                ("belge_tarihi", "Tarih"),
                ("belge_turu", "Tür"),
                ("karsi_vkn", "VKN/TCKN"),
                ("unvan", "Unvan"),
                ("onay_durumu", "Durum"),
                ("matrah", "Matrah"),
                ("kdv_toplam", "KDV"),
                ("genel_toplam", "Genel Toplam"),
                ("oranlar_metni", "KDV Oranlar"),
                ("para", "Para"),
                ("ettn", "ETTN"),
                ("dosya", "ZIP")]
    try:
        from openpyxl import Workbook
        kitap = Workbook()
        yaprak = kitap.active
        yaprak.title = "belgeler"
        yaprak.append([baslik for _, baslik in sutunlar])
        for kayit in kayitlar:
            yaprak.append([kayit.get(anahtar, "")
                           for anahtar, _ in sutunlar])
        kitap.save(yol)
        return yol
    except Exception:
        csv_yol = os.path.splitext(yol)[0] + ".csv"
        with open(csv_yol, "w", encoding="utf-8-sig", newline="") as dosya:
            dosya.write(",".join(b for _, b in sutunlar) + "\n")
            for kayit in kayitlar:
                hucreler = [str(kayit.get(a, "")).replace('"', "'")
                            for a, _ in sutunlar]
                dosya.write(",".join('"' + h + '"' for h in hucreler) + "\n")
        return csv_yol


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
                       gorunur=True, firma_adi=None):
    """Luca ERP Akıllı Entegrasyon ekranlarından e-Belgeleri indirir.

    Gerçek akış: giriş → portalda gonder('formTarget') ile MM Paketi
    penceresi → SirketCombo/DonemCombo ile firma+dönem seçimi → her
    kategori için gib530.do?tur=... ekranı → listedeki 'fatura' JSON'ları
    okunur, tarih aralığına göre süzülür → her belgenin ZIP'i satırdaki
    ZIP simgesiyle indirilip açılır (UBL XML + HTML).

    firma_adi: firma unvanının içinde geçen ibare; Türkçe büyük/küçük
    harf duyarsız eşleşir. Tek firmalık hesapta boş bırakılabilir.

    gorunur=True önerilir; captcha kullanıcı tarafından tarayıcı
    penceresinde elle girilir, bu yüzden görünür tarayıcı gerekir.

    Kategori başına çıktılar hedef_klasor altına yazılır:
      luca_{kategori}_{bas}_{bit}/          → belge ZIP + XML + HTML
      luca_{kategori}_{bas}_{bit}.xlsx      → özet tablo

    Dönen değer: {kategori: {"zip": [yollar], "ozet": xlsx_yolu,
    "belge_sayisi": n}}. Hiçbir kategori inmezse LucaHata.
    """
    bildir = _bildir_fonksiyonu(ilerleme)
    os.makedirs(hedef_klasor, exist_ok=True)
    hedefler = kategoriler or [k for k in LUCA_GIB_TURLER]
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise LucaHata(
            "Playwright kurulu değil. Kurulum: pip install playwright")

    sonuc = {}
    with sync_playwright() as p:
        tarayici = _tarayici_ac(p, gorunur=gorunur)
        oturum = _luca_oturum_ac(tarayici)
        sayfa = oturum.new_page()
        try:
            sayfa = giris_yap(sayfa, uye_no, kullanici, parola, bildir)
            sayfa.wait_for_timeout(2500)
            erp = _erp_penceresi(oturum, sayfa, bildir)
            _firma_donem_sec(erp, firma_adi, bas_tarih, bildir)

            for kategori in hedefler:
                tur = LUCA_GIB_TURLER.get(kategori)
                if tur is None:
                    bildir(f"Bilinmeyen kategori atlandı: {kategori}")
                    continue
                bildir(f"{kategori}: ekran açılıyor...")
                try:
                    cerceve = _gib530_frame(erp, tur, uye_no, bildir)
                    if cerceve is None:
                        raise RuntimeError("gib530 ekranı yüklenmedi")
                    satirlar = _satirlari_ayikla(cerceve.content())
                    secili = [(sira, belge) for sira, belge in satirlar
                              if _tarih_araliginda(
                                  belge.get("belge_tarihi"),
                                  bas_tarih, bit_tarih)]
                    bildir(f"{kategori}: listede {len(satirlar)} belge, "
                           f"tarih aralığında {len(secili)} tanesi var.")
                    klasor = os.path.join(
                        hedef_klasor,
                        f"luca_{kategori}_{bas_tarih:%Y%m%d}_"
                        f"{bit_tarih:%Y%m%d}")
                    os.makedirs(klasor, exist_ok=True)
                    sayfa2 = cerceve.page
                    zip_yollari = []
                    kayitlar = []
                    gorulen = {}
                    atlanan_belge = 0
                    for numara, (sira, belge) in enumerate(secili, 1):
                        durum_kisa = _turk_kucult(
                            str(belge.get("onay_durumu") or ""))
                        iptal_ibare = str(belge.get("iptal_itiraz") or
                                          belge.get("iptal_itiraz_durumu")
                                          or "").strip()
                        if (iptal_ibare
                                or ("red" in durum_kisa)
                                or ("iptal" in durum_kisa)
                                or (durum_kisa and "onay" not in durum_kisa)):
                            atlanan_belge += 1
                            continue
                        belge_no = (belge.get("belge_numarasi")
                                    or f"belge{sira}").strip()
                        gorulen[belge_no] = gorulen.get(belge_no, 0) + 1
                        if gorulen[belge_no] > 1:
                            dosya_no = (f"{belge_no}_"
                                        f"{gorulen[belge_no]}")
                        else:
                            dosya_no = belge_no
                        zip_yol = os.path.join(klasor,
                                               f"{dosya_no}.zip")
                        ozet = {}
                        if _dosya_saglam(zip_yol):
                            try:
                                with zipfile.ZipFile(zip_yol) as zipp:
                                    for ic_ad in zipp.namelist():
                                        icerik = zipp.read(ic_ad)
                                        if ic_ad.lower().endswith(".xml"):
                                            ozet = _ubl_ozet(icerik)
                                        if not os.path.exists(
                                                os.path.join(klasor,
                                                             ic_ad)):
                                            zipp.extract(ic_ad, klasor)
                            except Exception:
                                pass
                        else:
                            try:
                                _zip_tikla_indir(cerceve, sayfa2, sira,
                                                 zip_yol)
                            except Exception as hata:
                                bildir(f"{kategori}: {belge_no} inmedi "
                                       f"({str(hata)[:50]}), atlanıyor.")
                                continue
                            try:
                                with zipfile.ZipFile(zip_yol) as zipp:
                                    for ic_ad in zipp.namelist():
                                        icerik = zipp.read(ic_ad)
                                        if ic_ad.lower().endswith(".xml"):
                                            ozet = _ubl_ozet(icerik)
                                        zipp.extract(ic_ad, klasor)
                            except Exception:
                                pass
                        kayitlar.append({
                            "belge_numarasi": belge_no,
                            "belge_tarihi": belge.get("belge_tarihi", ""),
                            "belge_turu": belge.get("belge_turu", ""),
                            "karsi_vkn": str(belge.get("alici_vkn_tckn",
                                                       "")),
                            "unvan": belge.get("alici_unvan_ad_soyad", ""),
                            "onay_durumu": belge.get("onay_durumu", ""),
                            "ettn": belge.get("ettn", ""),
                            "dosya": os.path.basename(zip_yol),
                            **ozet})
                        kayit = kayitlar[-1]
                        if ozet.get("oran_kalemleri"):
                            kayit["oranlar_metni"] = "; ".join(
                                f"{a['oran']:g}%:"
                                f"{(a.get('matrah') or 0):.2f}/"
                                f"{a['kdv']:.2f}"
                                for a in ozet["oran_kalemleri"])
                        zip_yollari.append(zip_yol)
                        bildir(f"{kategori}: {numara}/{len(secili)} "
                               f"belge ({belge_no}).")
                    if atlanan_belge:
                        bildir(f"{kategori}: {atlanan_belge} red/iptal "
                               "belge dışarıda bırakıldı.")
                    if not kayitlar:
                        raise RuntimeError("tarih aralığında belge inmedi")
                    ozet_yol = _ozet_tablo_yaz(
                        os.path.join(
                            hedef_klasor,
                            f"luca_{kategori}_{bas_tarih:%Y%m%d}_"
                            f"{bit_tarih:%Y%m%d}.xlsx"), kayitlar)
                    sonuc[kategori] = {
                        "zip": zip_yollari,
                        "ozet": ozet_yol,
                        "belge_sayisi": len(kayitlar)}
                except Exception as hata:
                    bildir(f"{kategori} çekilemedi: {str(hata)[:80]}")
                    _hata_ekrani_kaydet(sayfa, f"belge_{kategori}")
        finally:
            tarayici.close()
    if not sonuc:
        raise LucaHata(
            "Luca'dan hiçbir e-Belge kategorisi indirilemedi. Ekran "
            "görüntüleri %TEMP% altına kaydedildi.")
    return sonuc
