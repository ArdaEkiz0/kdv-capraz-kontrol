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


# ZIP icinden asla cikarilmamasi gereken dosya/klasor adlari (kucuk harfe
# cevrilerek karsilastirilir). Beklenen icerik Excel/XML fatura dokumu
# oldugundan bunlarin cikmasi her zaman supheli bir durumdur.
_ZIP_YASAKLI_ADLAR = {
    "config.py", "ayar.json", "ayarlar.py", "gecmis.json", ".env",
    "__pycache__", ".git",
}


def _zip_uyesi_guvenli_mi(ic_ad):
    """Uye adinin cikarilmaya uygun olup olmadigini (dosya adi bazinda) kontrol eder."""
    taban = os.path.basename(ic_ad).lower()
    if not taban:
        return False
    if taban in _ZIP_YASAKLI_ADLAR:
        return False
    if taban.startswith("."):
        return False
    if taban.endswith((".py", ".pyc", ".pyo", ".dll", ".exe", ".bat", ".sh")):
        return False
    return True


def _guvenli_cikar(zipp, klasor):
    """ZIP icerigini zip-slip'e ve supheli dosya adlarina karsi denetleyerek cikarir.

    Uye adlari '..' icermez ve mutlak yol olamaz; surunen hedef daima
    klasor icinde kalir. Ayrica uygulamanin kendi yapilandirma/kod
    dosyalariyla ayni adi tasiyan veya calistirilabilir turden uyeler de
    atlanir (ornegin zip icine gizlenmis bir config.py). Guvensiz uye
    atlanir, sayisi dondurulur.
    """
    atlanan = 0
    kok = os.path.realpath(klasor)
    for ic_ad in zipp.namelist():
        if ic_ad.endswith("/"):
            continue
        if not _zip_uyesi_guvenli_mi(ic_ad):
            atlanan += 1
            continue
        hedef = os.path.realpath(os.path.join(klasor, ic_ad))
        if not (hedef == kok or hedef.startswith(kok + os.sep)):
            atlanan += 1
            continue
        zipp.extract(ic_ad, klasor)
    return atlanan

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


def _tarayici_ac(playwright, gorunur=True):
    """Luca oturumu icin tarayici acar.

    Captcha kullanici tarafindan pencerede elle girildigi icin gorunur
    tarayici varsayilandir. Luca sunucusu otomasyon bayragini
    (--enable-automation / navigator.webdriver) tespit edip SSO'da 500
    dondurdugu icin bu bayraklar ozellikle devre disi birakilir.
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
    try:
        ilk = sayfa.query_selector("#captcha-input")
    except Exception:
        # Sayfa henuz yukleniyor/geziyor olabilir; bir kez daha bak.
        time.sleep(2)
        try:
            ilk = sayfa.query_selector("#captcha-input")
        except Exception:
            ilk = None
    if ilk is None:
        return True
    bekleme = manuel_bekleme if manuel_bekleme > 0 else 180
    try:
        sayfa.bring_to_front()
    except Exception:
        pass
    bildir(f"Captcha isteniyor: tarayıcı penceresindeki alana görüntüdeki "
           f"kodu elle girip Tamam'a basın ({bekleme} sn)...")
    for _ in range(bekleme):
        sayfa.wait_for_timeout(1000)
        try:
            captcha_kaldi = sayfa.query_selector("#captcha-input") is not None
        except Exception:
            # Kullanicinin girisiyle sayfa gezindi; yoklama bu esnada
            # olusebilir ("execution context destroyed"). Gezinti,
            # basarili giris anlamina gelir.
            captcha_kaldi = False
        if not captcha_kaldi:
            bildir("Captcha girildi; devam ediliyor.")
            return True
        _luca_swal_kapat(sayfa)
        # Oturum sıfırlanıp temiz giriş formu geldiyse tekrar gönder
        try:
            if sayfa.query_selector("#musteriNo") is not None:
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


def _gorunur_esles(sayfa, secici):
    """Secicinin gorunur eslesmesini dondurur; yoksa None.

    Luca sayfalari quirks modunda oldugu icin id secicileri gizli
    buyuk harf kopyalara da carpiabilir (HESAP_KODU_ILK gibi); ilk
    eslesme gizli dugum olabilir ve yazim bosluga gider.
    """
    try:
        for oge in sayfa.query_selector_all(secici):
            try:
                if oge.is_visible():
                    return oge
            except Exception:
                continue
    except Exception:
        pass
    return None


def _luca_metin_gir(oge, metin):
    """Luca'nın maskeli alanlarına klavye vuruşuyla yazar; değeri
    özellikten geri okuyup döndürür.

    Bu alanların özel JS araçları (takvim, hesap planı) olduğu için
    click() yerine odak JS ile verilir (tık takvim penceresi açar);
    yazım sonrası Escape/Tab ile araç kapatılıp değer işlenir. Tarih
    aracı ayraç karakterini değiştirebildiği için karşılaştırma
    ayraç-bağımsız yapılır ('/' -> '.').
    """
    try:
        oge.evaluate("el => el.focus && el.focus()")
    except Exception:
        pass
    try:
        oge.evaluate("el => el.select && el.select()")
    except Exception:
        pass
    try:
        oge.type(metin, delay=45)
        oge.press("Enter")
    except Exception:
        try:
            oge.fill(metin, force=True)
        except Exception:
            pass
    try:
        return (oge.input_value() or "").strip().replace("/", ".")
    except Exception:
        return None


def _tarih_alanlarini_doldur(sayfa, bas_tarih, bit_tarih, bildir):
    """Rapor ekranındaki tarih alanlarını bulup doldurmaya çalışır.

    Birincil: gib530 ekranındaki #tarih1/#tarih2 (e-Belge tarih aralığı).
    İkincil: Muavin ekranındaki #tarih_ilk/#tarih_son.
    Üçüncül: Genel seçicilerle tarama.
    """
    bas_metin = bas_tarih.strftime("%d.%m.%Y")
    bit_metin = bit_tarih.strftime("%d.%m.%Y")
    doldurulan = 0
    # Birincil: gib530 e-Belge ekranındaki tarih alanları
    for secici, metin in (("#tarih1", bas_metin),
                          ("#tarih2", bit_metin)):
        try:
            oge = sayfa.query_selector(secici)
            if oge is None or not oge.is_visible():
                continue
            if _luca_metin_gir(oge, metin) == metin:
                doldurulan += 1
        except Exception:
            continue
    if doldurulan < 2:
        # İkincil: Muavin ekranındaki tarih alanları
        for secici, metin in (("#tarih_ilk", bas_metin),
                              ("#tarih_son", bit_metin)):
            try:
                oge = sayfa.query_selector(secici)
                if oge is None or not oge.is_visible():
                    continue
                if _luca_metin_gir(oge, metin) == metin:
                    doldurulan += 1
            except Exception:
                continue
    if doldurulan < 2:
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
                    hedef = bas_metin if doldurulan == 0 else bit_metin
                    if _luca_metin_gir(oge, hedef) == hedef:
                        doldurulan += 1
                    if doldurulan >= 2:
                        break
                except Exception:
                    continue
            if doldurulan >= 2:
                break
    if doldurulan < 2:
        bildir("UYARI: Tarih alanları otomatik doldurulamadı; sayfanın kendi "
               "varsayılan dönemi kullanılacak.")
    else:
        bildir(f"Tarih aralığı girildi: {bas_metin} - {bit_metin}")
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


def _rapor_seceneklerini_duzelt(cerceve, bildir=None):
    """Muavin rapor formunda bakiyesiz hesaplari gizleyen filtreyi acar.

    'Bakiyesi ve Calismayan Hesaplar' select'i 'Bakiyesiz Hesaplari
    Gosterme' seciliyse, donem icinde hareketi olmayan bitis hesabi
    (orn. 192) dokumden tamamen elenir. Tumunu gosteren degere
    cevrilir; bulunamazsa sessiz gecilir.
    """
    try:
        for secenek in cerceve.query_selector_all("select option"):
            try:
                metin = (secenek.inner_text() or "").strip()
            except Exception:
                continue
            kucuk = metin.lower()
            # 'Tumunu Goster' / 'Tumu' iceren secenek: bakiyesizleri de
            # listeye alir. Turkce karakterler degisik yazilabildigi
            # icin esnek eslestirme kullanilir.
            if "t" + chr(252) + "m" in kucuk and ("goster" in kucuk
                                                  or "g" in kucuk):
                deger = secenek.get_attribute("value")
                secenek.evaluate(
                    "o => o.parentElement.value = arguments[0]", deger)
                try:
                    cerceve.select_option(
                        f"select:has(option[value='{deger}'])", value=deger)
                except Exception:
                    pass
                if bildir:
                    bildir(f"Rapor filtresi '{metin}' olarak ayarlandi.")
                return True
    except Exception:
        pass
    return False


def _hesap_alanlarini_doldur(sayfa, hesap_kodu, bildir=None):
    """Başlangıç ve Bitiş hesap kodu alanlarını aralık olarak doldurur.

    Luca aralığı dizgesel karşılaştırmayla uygular; bitişe aynı kodu
    yazmak (191 -> 191) alt hesapları (191.01.003 gibi) dışarıda
    bırakır. Bitiş kodu bir sonraki hesap olmalıdır (191 -> 192) ki
    tüm alt hesaplar aralığa dahil olsun. Hesap boyu alanlarına
    (hesap_boyu_ilk/son) kesinlikle dokunulmaz.

    Sayfada ayni kimligin gizli buyuk harf kopyalari da vardir
    (HESAP_KODU_ILK); quirks mod seciciyi gizli dugume kilitleyebilir.
    Bu yuzden yalniz GORUNUR dugume gercek tiklama + Ctrl+A + klavye
    ile yazilir ve deger ayni dugumden okunarak dogrulanir.
    """
    try:
        son_kod = str(int(hesap_kodu) + 1)
    except ValueError:
        son_kod = hesap_kodu
    klavye = sayfa.page.keyboard

    def _deger_uyuyor(okunan, beklenen):
        # Maskeli alan '192.' veya '192/...' biciminde dondurabilir;
        # ayraclar temizlenip on ek olarak karsilastirilir.
        if not okunan:
            return False
        temiz = okunan.replace("/", ".").rstrip(".")
        return temiz == beklenen or temiz.startswith(beklenen + ".")

    def _dugume_yaz(oge, metin):
        """Alana tikla, mevcut degeri tamamen sil, metni yaz ve ENTER'a bas.

        Luca maskeli alanlari yazilan degeri Enter ile isler; Tab
        yetmez. Deger ozellikten geri okunarak dogrulanir.
        """
        for deneme in range(3):
            try:
                oge.click(timeout=4000)
            except Exception:
                pass
            time.sleep(0.3)
            # Onceki hesaptan kalan degeri tumuyle temizle:
            klavye.press("Control+a")
            klavye.press("Delete")
            klavye.press("Backspace")
            time.sleep(0.2)
            klavye.type(metin, delay=80)
            time.sleep(0.2)
            # Luca bu alanda Enter bekler; onay olmadan deger islenmez.
            klavye.press("Enter")
            time.sleep(0.5)
            try:
                okunan = (oge.evaluate("el => el.value")
                          or "").strip().replace("/", ".")
                if _deger_uyuyor(okunan, metin):
                    return metin
                if deneme < 2:
                    bildir(f"UYARI: Alan '{metin}' yazımı doğrulanamadı "
                           f"(okunan: '{okunan}'), tekrar deneniyor.")
            except Exception as hata:
                if deneme < 2:
                    bildir(f"UYARI: Alan okunamadı ({str(hata)[:60]}), "
                           "tekrar deneniyor.")
        return None

    def _cift_yaz():
        ilk = _gorunur_esles(sayfa, "#hesap_kodu_ilk")
        if ilk is None:
            bildir("UYARI: Başlangıç hesap kodu alanı bulunamadı.")
            return False
        if _dugume_yaz(ilk, hesap_kodu) is None:
            return False
        son = _gorunur_esles(sayfa, "#hesap_kodu_son")
        if son is None:
            bildir("UYARI: Bitiş hesap kodu alanı bulunamadı; döküm yalnız "
                   f"{hesap_kodu} ile sınırlı kalabilir.")
            return False
        try:
            onceki = (son.evaluate("el => el.value") or "").strip()
        except Exception:
            onceki = ""
        if _dugume_yaz(son, son_kod) is None:
            bildir(f"UYARI: Bitiş hesap koduna '{son_kod}' yazılamadı "
                   f"(alan önce şunuydu: '{onceki}'); elle kontrol edin.")
            return False
        bildir(f"Hesap aralığı yazıldı: {hesap_kodu} -> {son_kod} "
               f"(bitiş alanının önceki değeri: {onceki or 'boş'})")
        return True

    # Bilinen kimlikler: muavin ekranındaki hesap kodu alanları
    try:
        if _gorunur_esles(sayfa, "#hesap_kodu_ilk") is not None:
            if _cift_yaz():
                return True
    except Exception:
        pass

    # Genel yol: bos kalan ilk iki 'Hesap' girdisini bul; hesap boyu
    # alanlarini atla, birine baslangic digerine bitis kodunu yaz.
    doldurulan = 0
    for secici in ("input[name*='Hesap' i]", "input[id*='Hesap' i]",
                   "input[name*='hesap']", "input[id*='hesap']"):
        try:
            ogeler = sayfa.query_selector_all(secici)
        except Exception:
            continue
        for oge in ogeler:
            try:
                kimlik = ((oge.get_attribute("name") or "")
                          + (oge.get_attribute("id") or "")).lower()
                if "boyu" in kimlik:
                    continue
                if oge.is_visible() and not (oge.input_value() or "").strip():
                    hedef = hesap_kodu if doldurulan == 0 else son_kod
                    _luca_metin_gir(oge, hedef)
                    # Luca düğüm değiştirdiğinde geri okuma yanıltır;
                    # yazim istisna vermediyse basarili say. Asil
                    # denetim indirilen dosyada yapilir.
                    doldurulan += 1
                    if doldurulan >= 2:
                        return True
            except Exception:
                continue
    return doldurulan > 0


def cek_muavin(uye_no, kullanici, parola, bas_tarih, bit_tarih, hedef_klasor,
               hesap_kodlari=("191", "391"), firma_adi="", ilerleme=None):
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
        # Captcha kullanicinin elle girdigi icin gorunur tarayici sart;
        # varsayilan da gorunur ama cagirida acikca belirtiyoruz.
        tarayici = _tarayici_ac(p, gorunur=True)
        oturum = _luca_oturum_ac(tarayici)
        sayfa = oturum.new_page()
        try:
            sayfa = giris_yap(sayfa, uye_no, kullanici, parola, bildir)
            sayfa.wait_for_timeout(2500)

            # Menuler iframe icinde render edildigi icin metin
            # eslestirmesiyle gezinme guvenilir degil; ERP penceresine
            # gecip rapor ekranini dogrudan adresiyle yukluyoruz.
            erp = _erp_penceresi(oturum, sayfa, bildir)
            _firma_donem_sec(erp, firma_adi, bas_tarih, bildir)
            cerceve = _muavin_frame(erp, uye_no, bildir)
            if cerceve is None:
                ekran = _hata_ekrani_kaydet(erp, "muavin_menu")
                detay = f" Ekran görüntüsü: {ekran}" if ekran else ""
                raise LucaHata(
                    "Muavin rapor ekranı (raporMizanDetayHazirla) "
                    "yüklenemedi." + detay)

            for hesap in hesap_kodlari:
                donem_etiketi = bas_tarih.strftime("%Y%m")
                hedef = os.path.join(
                    hedef_klasor,
                    f"luca_muavin_{hesap}_{donem_etiketi}.xlsx")
                try:
                    bildir(f"Hesap {hesap} muavini sorgulanıyor...")
                    # Onceki rapordan kalmis bayat form yerine ekranı
                    # her hesap icin tazele (alanlar temiz baslar).
                    yeni = _muavin_frame(erp, uye_no, bildir)
                    if yeni is not None:
                        cerceve = yeni
                    _tarih_alanlarini_doldur(cerceve, bas_tarih, bit_tarih,
                                             bildir)
                    # Bakiyesiz hesaplari gizleyen filtre acilir; yoksa
                    # donem ici hareketi olmayan bitis hesabi (192/392)
                    # dokumden elenir.
                    _rapor_seceneklerini_duzelt(cerceve, bildir)
                    _hesap_alanlarini_doldur(cerceve, hesap, bildir)
                    # Rapor Türü seçimi: varsa Excel'i işaretle
                    excel_secildi = _indir_butonu_tikla(
                        cerceve, (r"^excel$",), zaman_asimi=2)
                    if excel_secildi:
                        bildir("Rapor türü Excel olarak seçildi.")
                    raporda_indi = False
                    try:
                        with erp.expect_download(timeout=25000) as indirme:
                            _indir_butonu_tikla(
                                cerceve,
                                (r"^rapor$", r"^liste$", r"listele",
                                 r"sorgula", r"getir"),
                                zaman_asimi=6)
                        dosya = indirme.value
                        dosya.save_as(hedef)
                        dosyalar.append(hedef)
                        raporda_indi = True
                        bildir(f"İndirildi: {os.path.basename(hedef)}")
                        _muavin_dosya_denetle(hedef, hesap, bildir)
                    except Exception:
                        pass
                    if not raporda_indi:
                        # Rapor ekranda açıldı; ayrı Excel/döküm düğmesi ara
                        try:
                            with erp.expect_download(
                                    timeout=20000) as indirme:
                                if not _indir_butonu_tikla(
                                        cerceve,
                                        (r"excel", r"\bxls\b",
                                         r"aktar", r"döküm\s*al")):
                                    raise RuntimeError(
                                        "Excel/döküm düğmesi bulunamadı")
                            dosya = indirme.value
                            dosya.save_as(hedef)
                            dosyalar.append(hedef)
                            raporda_indi = True
                            bildir(f"İndirildi: {os.path.basename(hedef)}")
                            _muavin_dosya_denetle(hedef, hesap, bildir)
                        except Exception as hata:
                            bildir(f"Hesap {hesap}: döküm alınamadı "
                                   f"({str(hata)[:70]}).")
                        if not raporda_indi:
                            _hata_ekrani_kaydet(erp, f"rapor_{hesap}")
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

# 4 grup için okunaklı Türkçe etiketler (takip ekranında kullanılır).
_KATEGORI_ETIKET = {
    "earsiv_alis": "e-Arşiv Alış",
    "earsiv_satis": "e-Arşiv Satış",
    "efatura_alis": "e-Fatura Alış",
    "efatura_satis": "e-Fatura Satış",
}


def _kategori_etiketi(kategori):
    return _KATEGORI_ETIKET.get(kategori, kategori)


def _turk_kucult(metin):
    """Turkce buyuk harfleri de kuculterek karsilastirma metni uretir.

    I/ı/i farki da esitlenir; boylece 'KIRAZLAR' ile 'KİRAZLAR' ortak
    ibareye iner.
    """
    return (metin.replace("İ", "i").replace("I", "i").replace("Ş", "ş")
            .replace("Ğ", "ğ").replace("Ü", "ü").replace("Ö", "ö")
            .replace("Ç", "ç")).replace("ı", "i").lower()


_SIRKET_EK_KELIMELERI = {
    "a.s.", "as", "a.s", "ltd", "sti", "şti", "s.t.i.", "tic", "san",
    "ve", "ticaret", "sanayi", "limited", "sirketi", "şirketi",
    "kurumsal", "co", "corp", "inc",
}


def _firma_anahtar(metin):
    """Unvandan sirket eklerini atarak anlamli kelime kumesi uretir.

    'KİRAZLAR FERMANTASYON SAN. VE TİC. LTD. ŞTİ.' -> {'kirazlar',
    'fermantasyon'}; Luca'daki kısa ad 'KIRAZLARLT' olsa da kök
    'kirazlar' ile eslesir.
    """
    temiz = _turk_kucult(metin)
    temiz = re.sub(r"[^\w\s]", " ", temiz)
    return {k for k in temiz.split()
            if len(k) >= 3 and k not in _SIRKET_EK_KELIMELERI}


def _firma_eslesen(secenekler, firma_adi):
    """Sirket combo seceneklerini unvanla eslestirir (esnek).

    1. Tam alt-dize (eski davranis, en kesin)
    2. Anahtar-kelime kesisimi: hedef unvanin anlamli kelimeleri,
       Luca'nin kisaltilmis adinda gecmeli; kestirme 'KIRAZLARLT'
       gibi adlar da yakalanir.
    3. Ilk anlamli kelimeyle baslayan ad ('kirazlar*' gibi).
    """
    ibare = _turk_kucult(firma_adi)
    tam = [s for s in secenekler if ibare in _turk_kucult(s["t"])]
    if tam:
        return tam
    anahtarlar = _firma_anahtar(firma_adi) or set()
    if not anahtarlar:
        return []
    skorlu = []
    # Her anlamli kelime sirayla denenir ('kirazlar' da 'fermantasyon'
    # da); kisaltilmis adlar ('KIRAZLARLT') boyle yakalanir, benzer
    # baslangicli ilgisiz firmalar ('AKIN'/'AKKEC') eslesmez.
    for anahtar in sorted(anahtarlar, key=len, reverse=True):
        secili = {s["v"] for _, s in skorlu}
        for s in secenekler:
            if s["v"] in secili:
                continue
            ad_kucuk = re.sub(r"[^\w\s]", " ", _turk_kucult(s["t"]))
            if re.search(r"\b" + re.escape(anahtar), ad_kucuk):
                skorlu.append((1, s))
        if len(skorlu) == 1:
            return [s for _, s in skorlu]
        if len(skorlu) > 1:
            break
    if len(skorlu) == 1:
        return [s for _, s in skorlu]
    if skorlu:
        # Birden fazla aday: sirali dondur; cagiran taraf hata verir.
        return [s for _, s in skorlu]
    ilk = sorted(anahtarlar)[0] if anahtarlar else ""
    if ilk:
        baslayan = [s for s in secenekler
                    if _turk_kucult(s["t"]).startswith(ilk)]
        if len(baslayan) == 1:
            return baslayan
    return []


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
        eslesen = _firma_eslesen(secenekler, firma_adi)
        if not eslesen:
            ornekler = ", ".join(s["t"] for s in secenekler[:6])
            raise LucaHata(f"Firma bulunamadı: {firma_adi} "
                           f"(örnek firmalar: {ornekler})")
        hedef = eslesen[0]
        if len(eslesen) > 1:
            adaylar = ", ".join(s["t"] for s in eslesen[:6])
            raise LucaHata(
                f"'{firma_adi}' ile {len(eslesen)} firma eşleşti "
                f"({adaylar}). Hangi firma olduğunu netleştirmek için "
                "mükellef kaydındaki Unvan alanını Luca'daki kısa ada "
                "göre düzenleyin (örn. 'KIRAZLARLT' yazın).")
    else:
        if len(secenekler) != 1:
            raise LucaHata(
                f"firma_adi belirtilmeli (hesapta {len(secenekler)} "
                "firma var).")
        hedef = secenekler[0]
    ust.select_option("#SirketCombo", hedef["v"])
    ust.wait_for_timeout(800)
    bildir(f"Luca firması seçildi: {hedef['t']}")
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


def _gibten_getir(cerceve, bas_tarih, bit_tarih, bildir=None):
    """Luca e-belge ekranında 'GİB'ten Getir' (İnternetten Getir) adımını çalıştırır.

    Luca'nın gib530 ekranı iki adımlıdır: belgeler önce GİB'den bu butonla
    çekilir (listeye yüklenir), ardından indirilir.

    Buton bulma ÇOK GENİŞ yapılır: input/button/a + span/div/img + onclick/
    title/alt + 'getir', 'indir', 'internetten', 'gib' gibi anahtar
    kelimeler taranır. is_visible() güvenilir olmadığı için DOM'da olan
    öğelerden tıklanabilir ilk aday seçilir; bulunamazsa en kötü ihtimalle
    'gib530' ekranında ilk butona tıklanmaz, sessizce dönülür.
    """
    if bildir is None:
        bildir = lambda s: None
    try:
        sayfa = cerceve.page
        # ADIM: hangi tarihse onu yaz. Belge ekranındaki tarih aralığı
        # alanlarına istenen dönem girilir (aynı muavin çekimindeki gibi).
        try:
            _tarih_alanlarini_doldur(cerceve, bas_tarih, bit_tarih, bildir)
        except Exception as th:
            bildir(f"Tarih alanları doldurulamadı ({str(th)[:50]}); "
                   "varsayılan kullanılacak.")
        buton = None

        # Birincil: Luca'nın güncel arabirimindeki "Belgeleri Getir" butonu
        for secici in ("#faturalari-getir-btn",
                       "button[onclick*=\"gonder('indir')\"]",
                       "button[onclick*='indir']"):
            try:
                oge = cerceve.query_selector(secici)
                if oge is not None:
                    buton = oge
                    bildir("Belgeleri Getir butonu bulundu (doğrudan seçim).")
                    break
            except Exception:
                continue

        # İkincil: Geniş aday toplama (eski sürümler için geriye dönük uyumluluk)
        if buton is None:
            adaylar = []
            for secici in ("button", "input", "a", "span", "div", "img",
                           "li", "td", "b", "i"):
                try:
                    ogeler = cerceve.query_selector_all(secici)
                except Exception:
                    continue
                for oge in ogeler:
                    try:
                        metin = ((oge.get_attribute("value") or "")
                                 + " " + (oge.inner_text() or "")
                                 + " " + (oge.get_attribute("onclick") or "")
                                 + " " + (oge.get_attribute("title") or "")
                                 + " " + (oge.get_attribute("alt") or "")
                                 + " " + (oge.get_attribute("src") or ""))
                        k = (metin or "").lower()
                        if ("getir" in k or "internette" in k
                                or ("gib" in k and ("indir" in k or "cek" in k))
                                or "taşı" in k or "tası" in k
                                or ("gib" in k and "yükle" in k)
                                or "belgeleri getir" in k):
                            if "onceki" not in k and "geri" not in k:
                                adaylar.append(oge)
                    except Exception:
                        continue

            for oge in adaylar:
                tag = ""
                try:
                    tag = (oge.evaluate("el => el.tagName") or "").lower()
                except Exception:
                    pass
                m = ""
                try:
                    m = ((oge.get_attribute("value") or "")
                         + " " + (oge.inner_text() or "")
                         + " " + (oge.get_attribute("title") or "")
                         + " " + (oge.get_attribute("onclick") or "")).lower()
                except Exception:
                    pass
                if tag in ("button", "input") or "getir" in m \
                        or "internette" in m or "belgeleri" in m:
                    buton = oge
                    break
            if buton is None and adaylar:
                buton = adaylar[0]

        if buton is None:
            bildir("GİB'ten getir butonu hiç bulunamadı; listeyi "
                   "sorguyla yenilemeyi deniyorum.")
            try:
                _sorgula_listele_butonu(cerceve, bildir)
            except Exception:
                pass
            return
        bildir("GİB'ten getir tıklanıyor (belgeler çekiliyor)...")
        # gonder('indir') Luca'nın kendi JS fonksiyonudur; çerçeve
        # context'inden doğrudan çağrılır (buton.click() bazı frame
        # yapılarında event'i tetiklemeyebilir).
        try:
            cerceve.evaluate("gonder('indir')")
            bildir("gonder('indir') JS ile çağrıldı.")
        except Exception:
            try:
                buton.scroll_into_view_if_needed()
            except Exception:
                pass
            try:
                buton.click()
            except Exception:
                try:
                    buton.evaluate("e => e.click()")
                except Exception:
                    pass
            bildir("Buton tıklama ile çağrıldı (JS fallback).")
        # İlgili onay/uyarı penceresi çıkabilir (Evet/Tamam/liste).
        time.sleep(2)
        # Onay/SweetAlert penceresi varsa 'Evet'/'Tamam'a bas.
        for _ in range(3):
            try:
                onay = cerceve.query_selector(
                    "button:has-text('Evet'), button:has-text('Tamam'), "
                    "button:has-text('OK'), input[value*='Evet'], "
                    "input[value*='Tamam']")
                if onay is not None and onay.is_visible():
                    try:
                        onay.click()
                        bildir("Onay penceresi kapatıldı.")
                        time.sleep(1)
                    except Exception:
                        pass
                    break
            except Exception:
                pass
            # SweetAlert / custom popup
            try:
                cerceve.evaluate(
                    "document.querySelectorAll('.swal2-confirm, "
                    ".swal2-styled').forEach(b => b.click())")
            except Exception:
                pass
            time.sleep(0.5)
        # Belgeler listeye gelene kadar bekle (akıllı).
        # GİB sorguları 10-30 sn sürebilir; 30 denemeye kadar bekle.
        try:
            import luca_cekme as _l
            for _i in range(30):
                deneme_html = cerceve.content()
                belge_sayisi = len(_l._satirlari_ayikla(deneme_html))
                if belge_sayisi > 0:
                    bildir(f"Listede {belge_sayisi} belge göründü.")
                    break
                if _i % 5 == 4:
                    bildir(f"Hâlâ bekleniyor... ({_i+1}s)")
                time.sleep(1)
            else:
                bildir("30 sn'de belge gelmedi; mevcut liste kullanılıyor.")
        except Exception:
            time.sleep(3)
        bildir("GİB'ten getir tamamlandı; liste güncellendi.")

        # Güvence: getir sonrası 'Sorgula'/'Listele' butonuna basarak
        # listenin tazelenmesini zorla. Luca bazı ekranlarda getir ile
        # listeyi yenilemez; sorgu butonu gerekir.
        try:
            _sorgula_listele_butonu(cerceve, bildir)
        except Exception:
            pass
    except Exception as hata:
        bildir(f"GİB'ten getir başarısız: {str(hata)[:50]}")


def _sorgula_listele_butonu(cerceve, bildir=None):
    """'Sorgula' / 'Listele' / 'Getir' gibi listeyi yenileyen butona basar.

    GİB'ten getir sonrası listenin dolması için gerekli; bulunamazsa
    sessizce geçer.
    """
    if bildir is None:
        bildir = lambda s: None
    adaylar = []
    for secici in ("button", "input", "a", "span", "div"):
        try:
            ogeler = cerceve.query_selector_all(secici)
        except Exception:
            continue
        for oge in ogeler:
            try:
                metin = ((oge.get_attribute("value") or "")
                         + " " + (oge.inner_text() or "")
                         + " " + (oge.get_attribute("onclick") or "")).lower()
                if any(k in metin for k in ("sorgula", "listele", "liste",
                                            "getir", "ara", "tazele")):
                    adaylar.append(oge)
            except Exception:
                continue
    for oge in adaylar:
        try:
            oge.scroll_into_view_if_needed()
        except Exception:
            pass
        try:
            oge.click()
            if cerceve.page is not None:
                cerceve.page.wait_for_timeout(1300)
            return
        except Exception:
            try:
                oge.evaluate("e => e.click()")
                if cerceve.page is not None:
                    cerceve.page.wait_for_timeout(1300)
                return
            except Exception:
                continue
    bildir("Sorgula/Listele butonu bulunamadı; mevcut liste kullanılıyor.")


def _tani_kaydet(kategori, cerceve):
    """Çekim ekranının HTML + URL'sini %TEMP%\\luca_tani\\ altına yazar.

    Gerçek Luca yapısını çözüp çekimi kökten tasarlarken kullanılır;
    her kategori için ayrı dosya oluşturur.
    """
    import time as _t
    try:
        klasor = os.path.join(os.environ.get("TEMP", "."), "luca_tani")
        os.makedirs(klasor, exist_ok=True)
        damga = _t.strftime("%Y%m%d_%H%M%S")
        yol = os.path.join(klasor, f"{kategori}_{damga}.html")
        icerik = cerceve.content() if cerceve is not None else ""
        with open(yol, "w", encoding="utf-8", errors="replace") as f:
            f.write(icerik)
        try:
            url_yol = os.path.join(klasor, f"{kategori}_{damga}.url.txt")
            with open(url_yol, "w", encoding="utf-8") as f:
                f.write((cerceve.url or "") if cerceve is not None else "")
        except Exception:
            pass
    except Exception:
        pass


def _gib530_frame(erp, tur, uye_no, bildir=None):
    """Ana icerik cercevesini istenen gib530 ekranina goturur ve frame'i
    dondurur; yuklenmezse None doner.

    Firma secimi sonrasi cerceveler yeniden yuklendigi icin ilk
    denemede 'execution context destroyed' hatasi normaldir; gezinme
    araliklarla yeniden denenir.

    Yeni mükellefte 'E-Fatura Satış' turunun ana menüde takılmasını
    önlemek için: tur adresi yalnız frm3'e değil, bulunan her
    gib530 frame'ine uygulanır; ayrıca her denemede tüm frame'ler
    taranır ve yalnız istenen turdaki gib530 döndürülür (eski turdayken
    yanlış frame dönmesin diye URL içinde tur de denetlenir).

    Bazen tur geçişi frm3 yönlendirmesiyle olmaz (Luca'nın kimi
    ekranları farklı frame/sekme kullanır). Bu yüzden yönlendirme
    başarısız olursa, en-dış sayfada doğrudan gib530.do adresine
    gidilir ve yükleme beklenir.
    """
    adres = f"gib530.do?tur={tur}&c_musteri_id={uye_no}"
    # Yalnız frame-içi yönlendirme: ana pencereyi asla değiştirme (goto
    # ana ERP'yi bozup çekimi çökertebiliyor). frm3 yanında, kullanıcı
    # yapılandırmasına göre farklı olabilecek adları da dener.
    frame_adlari = ["frm3", "frm1", "frm2", "main", "icerik", "content",
                    "fatura"]
    for deneme in range(10):
        try:
            if deneme in (0, 2, 4, 6, 8):
                for fn in frame_adlari:
                    erp.evaluate(
                        "p => { const [fn, u] = p;"
                        " const f = top.frames[fn];"
                        " if (f) { f.location.href = u; }"
                        " else { const el = document.querySelector("
                        "   'iframe[name=\"' + fn + '\"],frame[name=\"' + fn + '\"]');"
                        "   if (el) el.src = u; } }",
                        [fn, adres])
        except Exception:
            pass
        time.sleep(1.2)
        for f in erp.frames:
            try:
                url = f.url or ""
                if "gib530" in url and tur in url and len(f.content()) > 5000:
                    return f
            except Exception:
                continue
    # Frm3 yönlendirmesiyle olmadıysa, TÜM çocuk frame'lere tur adresini
    # uygula (hangi frame gib530'u taşıyorsa o yüklensin).
    try:
        for f in erp.frames:
            try:
                if f == erp:
                    continue
                f.evaluate("u => { window.location.href = u; }",
                           adres if adres.startswith("http") else
                           "gib530.do?tur=" + tur + "&c_musteri_id=" +
                           str(uye_no))
                time.sleep(1.5)
                if "gib530" in (f.url or "") and tur in (f.url or ""):
                    if len(f.content()) > 5000:
                        return f
            except Exception:
                continue
    except Exception:
        pass
    if bildir is not None:
        try:
            nerede = erp.evaluate(
                "top.frames['frm3'] "
                "? top.frames['frm3'].location.href : 'frm3 yok'")
            bildir(f"frm3 durumu: {str(nerede)[:100]}")
        except Exception:
            pass
    return None


def _muavin_dosya_denetle(yol, hesap, bildir):
    """Indirilen muavin dosyasinda veri satiri ve dogru aralik var mi
    diye bakar.

    Ilk ~4 satir basliktir (MUAVIN DEFTER, firma, dönem, tarih); ilk
    hesap satirinin kodu istenen aralikta (hesap..hesap+1) olmalidir.
    Bitis kodu bir sonraki hesap oldugu icin 192 hesaplarinin da
    gorunmesi normaldir.
    """
    try:
        import openpyxl
        try:
            son_kod = str(int(hesap) + 1)
        except ValueError:
            son_kod = hesap
        wb = openpyxl.load_workbook(yol)
        ws = wb.active
        satir_sayisi = ws.max_row or 0
        ilk_hesap = None
        hareket_var = False
        ana_hesaplar = set()
        if satir_sayisi > 4:
            for satir in ws.iter_rows(min_row=5, values_only=True):
                ilk = str(satir[0] or "").strip() if satir else ""
                m = re.match(r"^(\d{3})(\.|$)", ilk)
                if m:
                    ana_hesaplar.add(m.group(1))
                    if not ilk_hesap:
                        ilk_hesap = ilk
                # Tarihli hareket satiri (dd.mm.yyyy / dd/mm/yyyy)
                if re.match(r"^\d{2}[./]\d{2}[./]\d{4}", ilk):
                    hareket_var = True
        wb.close()
        if satir_sayisi <= 4:
            bildir(f"UYARI: Hesap {hesap} dökümü boş görünüyor "
                   f"({satir_sayisi} satır).")
        elif son_kod not in ana_hesaplar and hesap in ana_hesaplar:
            bildir(f"UYARI: Hesap {hesap} dökümünde bitiş hesabı "
                   f"{son_kod} YOK (içindekiler: "
                   f"{', '.join(sorted(ana_hesaplar))}). Rapor filtresi "
                   "bakiyesiz hesapları eliyor olabilir; döküm aralığı "
                   "eksik.")
        elif ilk_hesap and not (hesap <= ilk_hesap[:3] <= son_kod):
            bildir(f"UYARI: Hesap {hesap} dökümü beklenen aralıkta değil "
                   f"(ilk satır: {ilk_hesap}).")
        elif ilk_hesap and not hareket_var:
            bildir(f"UYARI: Hesap {hesap} dökümünde DÖNEM İÇİ hareket yok "
                   "(yalnız 'Nakli Yekün' açılış satırları var). Belgeler "
                   "Luca'ya düşmüş ama henüz muhasebe fişine işlenmemiş "
                   "olabilir; bu yüzden faturalarla eşleşme çıkmaz.")
        elif ilk_hesap:
            bildir(f"Hesap {hesap} dökümü doğrulandı ({satir_sayisi} satır, "
                   f"ilk hesap: {ilk_hesap}).")
    except Exception:
        pass


def _muavin_frame(erp, uye_no, bildir=None):
    """Icerik cercevesini muavin defter ekranina goturur ve frame'i
    dondurur; yuklenmezse None doner.

    Luca menuleri iframe icinde render edildigi icin metin
    eslestirmesiyle gezinme guvenilir degil; ERP menu dizisindeki
    'Tum Yazicilar -> Muavin Defter' adresi (raporMizanDetayHazirla.do)
    dogrudan yuklenir. Firma secimi sonrasi cerceveler yeniden
    yuklendigi icin gezinme araliklarla yeniden denenir.
    """
    adres = f"raporMizanDetayHazirla.do?c_musteri_id={uye_no}"
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
                if ("raporMizanDetayHazirla" in f.url
                        and len(f.content()) > 5000):
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



def _zip_toplu_indir(frame, sayfa, indirme_planlari, bildir=None,
                     pencere=4):
    """ZIP indirmelerini kademeli paralel tetikler.

    `indirme_planlari`: [(satir_sirasi, hedef_yol), ...] çiftleri.
    Playwright'in download olaylarını toplayıcıyla yakalar; her 'pencere'
    adedinde bir sonraki grubu tetikler. Kritik fark: her satır için hedef
    dosya yolu ÖNCEDEN belli olduğundan, indirilen şey yanlış dosyaya
    yazılmaz (suggested_filename güvenilmez). Başarısız olan satırları
    döndürür (kalıp güvenilirliği için).
    """
    import queue
    hedef_map = {sira: yol for sira, yol in indirme_planlari}
    kuyruk = queue.Queue()
    dinleyici = lambda d: kuyruk.put(d)
    sayfa.on("download", dinleyici)
    basarisiz = []
    try:
        bekleyen = [sira for sira, _ in indirme_planlari]
        # Aktif click sayısını değil, inen dosya sayısını izle; kuyruk
        # uzun süre sessiz kalırsa (bazı click'ler indirme başlatmıyorsa)
        # o siparişleri kalanlara geri koy / başarısız işaretle.
        while bekleyen:
            # Yeni clicking: pencere kadar aktif download bekleyebiliriz.
            while bekleyen:
                sira = bekleyen.pop(0)
                hedef = hedef_map[sira]
                try:
                    frame.evaluate(
                        "n => { const e = [...document.querySelectorAll("
                        "'[onclick]')]"
                        ".filter(x => x.getAttribute('onclick')"
                        ".includes('zip_indir'))"
                        "[n]; if (!e) throw new Error('yok'); e.click(); }",
                        sira)
                except Exception:
                    basarisiz.append(sira)
                    continue
                # Belirli kısa süre içinde en az pencere kadar download
                # gelmeye devam etmeli; aksi halde tıklama bir işe
                # yaramadı, bir sonraki adıma geç.
                try:
                    d = kuyruk.get(timeout=12)
                except Exception:
                    # İndirme başlatılamadı — tekrar dene (bir kez).
                    try:
                        frame.evaluate(
                            "n => { const e = [...document.querySelectorAll("
                            "'[onclick]')]"
                            ".filter(x => x.getAttribute('onclick')"
                            ".includes('zip_indir'))"
                            "[n]; if (!e) throw new Error('yok'); e.click(); }",
                            sira)
                        d = kuyruk.get(timeout=15)
                    except Exception:
                        basarisiz.append(sira)
                        continue
                try:
                    d.save_as(hedef)
                except Exception:
                    basarisiz.append(sira)
                time.sleep(0.05)
        # Kalan kuyruktaki olası download'ları da kaydet.
        while True:
            try:
                d = kuyruk.get_nowait()
            except Exception:
                break
            # En iyi tahmini hedef: hedef_map'te kalanlardan birine eşle.
            for sira, yol in hedef_map.items():
                if not os.path.exists(yol):
                    try:
                        d.save_as(yol)
                        break
                    except Exception:
                        continue
    finally:
        try:
            sayfa.remove_listener("download", dinleyici)
        except Exception:
            pass
    return basarisiz


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


def _sayfa_butonlari(cerceve):
    """Luca belge listesindeki sayfa ilerleme düğmelerini döndürür.

    Geniş tarama: input/button/a + span/div + onclick içeren her öğe.
    Metin ya da onclick'te 'sonraki/ileri/next/»/›/>' veya 'sayfa 2'
    deseni aranır; 'önceki/geri' hariç.
    """
    adaylar = []
    try:
        ogeler = cerceve.query_selector_all(
            "input, button, a, span, div, td, li, img, b, i")
        for oge in ogeler:
            try:
                metin = ((oge.get_attribute("value") or "")
                         + " " + (oge.inner_text() or "")
                         + " " + (oge.get_attribute("onclick") or "")
                         + " " + (oge.get_attribute("title") or "")
                         + " " + (oge.get_attribute("alt") or "")).strip()
                if not metin:
                    continue
                k = metin.lower()
                # 'önceki/geri' hariç; ilerleme desenleri
                if "onceki" in k or "geri" in k:
                    continue
                ilerleme = (
                    "sonraki" in k or "ileri" in k or "next" in k
                    or "»" in k or "›" in k or ">>" in k
                    or k.strip() in (">", "→")
                    or "sayfa 2" in k or "sayfa2" in k
                    or re.search(r"goPage|nextPage|sayfaGec|ileri", k)
                    or re.search(r"pager", k)
                )
                if ilerleme:
                    adaylar.append(oge)
            except Exception:
                continue
    except Exception:
        pass
    return adaylar


def _sonraki_sayfa_var_mi(cerceve):
    """Luca belge listesinde 'Sonraki' / ileri sayfa düğmesi varsa True."""
    return len(_sayfa_butonlari(cerceve)) > 0


def _sonraki_sayfaya_git(cerceve):
    """Listedeki 'Sonraki' / 'İleri' düğmesine tıklar; yönlendirme
    sonrası yeni sayfa içeriği yüklenir. Dönüş: True/False."""
    adaylar = _sayfa_butonlari(cerceve)
    for oge in adaylar:
        try:
            oge.scroll_into_view_if_needed()
        except Exception:
            pass
        try:
            oge.click()
        except Exception:
            continue
        try:
            cerceve.page.wait_for_timeout(1300)
        except Exception:
            pass
        # Tıklama sonrası gerçekten sayfa değişti mi? İlk sayfa ile
        # aynı belgeleri tekrar görüyorsak ilerlememiş olabilir;
        # yine de döngü dedup ile yönetir.
        return True
    return False


def cek_luca_belgeleri(uye_no, kullanici, parola, bas_tarih, bit_tarih,
                       hedef_klasor, kategoriler=None, ilerleme=None,
                       gorunur=True, firma_adi=None, duz_yaz=True,
                       olay=None):
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
      {kategori}_{dosya}.zip/.xml/.html   → düz yazım (duz_yaz=True)
      luca_{kategori}_{bas}_{bit}/        → alt klasör (duz_yaz=False)
      luca_{kategori}_{bas}_{bit}.xlsx    → özet tablo

    olay: yapılandırılmış ilerleme takibi için sözlük alan callback.
    Her çağrı şöyledir (UI takip ekranı için):
      {\"kategori\": ..., \"adim\": ..., \"durum\": ..., \"sayi\": ...,
       \"toplam\": ..., \"mesaj\": ...}
    adim: 'basla'|'liste'|'indirme'|'indirildi'|'ozet'|'hata'|'bitti'
    durum: 'calisiyor'|'tamam'|'hata'|'atlandi'

    Dönen değer: {kategori: {"zip": [yollar], "ozet": xlsx_yolu,
    "belge_sayisi": n}}. Hiçbir kategori inmezse LucaHata.
    """
    bildir = _bildir_fonksiyonu(ilerleme)
    if not olay:
        olay = lambda o: None
    if not gorunur:
        raise LucaHata(
            "Captcha kullanıcı tarafından elle girildiği için Luca çekimi "
            "yalnız görünür tarayıcıyla çalışır (gorunur=True kullanın).")
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
            sayfa.wait_for_timeout(1300)
            erp = _erp_penceresi(oturum, sayfa, bildir)
            _firma_donem_sec(erp, firma_adi, bas_tarih, bildir)

            for kategori in hedefler:
                tur = LUCA_GIB_TURLER.get(kategori)
                if tur is None:
                    bildir(f"Bilinmeyen kategori atlandı: {kategori}")
                    continue
                birim = _kategori_etiketi(kategori)
                olay({"kategori": kategori, "adim": "basla",
                      "durum": "calisiyor", "sayi": 0, "toplam": 0,
                      "mesaj": f"{birim} ekranı açılıyor..."})
                bildir(f"{kategori}: ekran açılıyor...")
                try:
                    cerceve = _gib530_frame(erp, tur, uye_no, bildir)
                    if cerceve is None:
                        olay({"kategori": kategori, "adim": "hata",
                              "durum": "hata", "sayi": 0, "toplam": 0,
                              "mesaj": "gib530 ekranı yüklenemedi"})
                        raise RuntimeError("gib530 ekranı yüklenmedi")
                    # TANI: gerçek ekran HTML'ini kaydet (çekim kökten
                    # tasarlanırken kullanılacak).
                    try:
                        _tani_kaydet(kategori, cerceve)
                    except Exception:
                        pass
                    # İKİ ADIMLI AKIŞ: Luca'nın e-belge ekranında belgeler
                    # GİB'ten önce 'çekilir' (GİB'ten Getir / İnternetten
                    # Getir butonu), sonra listelenip indirilir. Bu adım
                    # atlanırsa yeni mükelleflerde belge listesi boş kalır.
                    try:
                        _gibten_getir(cerceve, bas_tarih, bit_tarih, bildir)
                    except Exception as g_hata:
                        bildir(f"{kategori}: GİB'ten getir adımı "
                               f"atlandı ({str(g_hata)[:60]})")
                        _hata_ekrani_kaydet(cerceve, f"getir_{kategori}")
                    # İlk olarak satır sayısını artırmayı dene (500/1000/tümü);
                    # Luca tek sayfada en fazla ~500 fatura listeler.
                    try:
                        _satir_sayisini_buyut(cerceve, bildir)
                        cerceve.page.wait_for_timeout(1000)
                    except Exception:
                        pass
                    # TÜM SAYFALARI TOPLA: ilk sayfa + 'Sonraki' ile gidilen
                    # her sayfa. Aynı belgeleri alt alta ekleme (tekrar koru).
                    # Güvence: sayfada tam sayfa limiti (500) belge görünüyorsa
                    # daha fazlası var demektir -> sonraki sayfa aranır.
                    SAYFA_LIMITI = 500
                    tum_satirlar = []
                    gorulen_belge = set()
                    for sayfa_sirasi in range(1, 60):  # 500*59≈30k, güvenlik sınırı
                        sayfa_satirlari = _satirlari_ayikla(cerceve.content())
                        yeni = 0
                        for sira, belge in sayfa_satirlari:
                            anahtar = (str(belge.get("belge_numarasi") or "")
                                       + "|" + str(belge.get("belge_tarihi") or "")
                                       + "|" + str(belge.get("ettn") or ""))
                            if anahtar not in gorulen_belge:
                                gorulen_belge.add(anahtar)
                                # Satır indeksi: bu sayfadaki sira korunur;
                                # ZIP tıklamaları her sayfada 0'dan başlar.
                                tum_satirlar.append((sira, belge))
                                yeni += 1
                        if not sayfa_satirlari or yeni == 0:
                            break
                        # Sayfada tam limit kadar belge var mı? O zaman
                        # mutlaka devamı vardır.
                        tam_sayfa = len(sayfa_satirlari) >= SAYFA_LIMITI
                        sonraki_var = _sonraki_sayfa_var_mi(cerceve)
                        if sayfa_sirasi >= 30 and sonraki_var:
                            bildir(f"{kategori}: {sayfa_sirasi}. sayfa "
                                   "toplandı, ilerleniyor...")
                        if not sonraki_var and not tam_sayfa:
                            break
                        if not _sonraki_sayfaya_git(cerceve):
                            # Düğme görünse de tıklama başarısız olabilir;
                            # tam sayfa ise yine de devam etmeye zorla.
                            if tam_sayfa:
                                try:
                                    cerceve.page.wait_for_timeout(1300)
                                    continue
                                except Exception:
                                    pass
                            break
                    satirlar = tum_satirlar
                    # Tarih aralığında kalan ve geçerli (red/iptal olmayan)
                    # belgelerin tam listesi (belge no, sayac ile).
                    gorulen_no = {}
                    tum_secili = []
                    atlanan_belge = 0
                    for sira, belge in satirlar:
                        if not _tarih_araliginda(belge.get("belge_tarihi"),
                                                 bas_tarih, bit_tarih):
                            continue
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
                        gorulen_no[belge_no] = \
                            gorulen_no.get(belge_no, 0) + 1
                        tum_secili.append((sira, belge, belge_no,
                                           gorulen_no[belge_no]))
                    secili = [(sira, belge)
                              for sira, belge, _, _ in tum_secili]
                    bildir(f"{kategori}: listede {len(satirlar)} belge, "
                           f"tarih aralığında {len(secili)} tanesi var.")
                    olay({"kategori": kategori, "adim": "liste",
                          "durum": "calisiyor", "sayi": len(secili),
                          "toplam": len(secili),
                          "mesaj": f"{birim}: {len(secili)} belge bulundu"})
                    if duz_yaz:
                        klasor = hedef_klasor
                    else:
                        klasor = os.path.join(
                            hedef_klasor,
                            f"luca_{kategori}_{bas_tarih:%Y%m%d}_"
                            f"{bit_tarih:%Y%m%d}")
                    on_ek = ("" if duz_yaz
                             else f"luca_{kategori}_")
                    os.makedirs(klasor, exist_ok=True)
                    sayfa2 = cerceve.page
                    zip_yollari = []
                    kayitlar = []

                    def _hedef_zip(no, c):
                        ad = no if c <= 1 else f"{no}_{c}"
                        return os.path.join(klasor, f"{on_ek}{ad}.zip")

                    def _zipten_ozet(zip_yol):
                        o = {}
                        try:
                            with zipfile.ZipFile(zip_yol) as zipp:
                                for ic_ad in zipp.namelist():
                                    icerik = zipp.read(ic_ad)
                                    if ic_ad.lower().endswith(".xml"):
                                        o = _ubl_ozet(icerik)
                                _guvenli_cikar(zipp, klasor)
                        except Exception:
                            pass
                        return o

                    # ÇOK SAYFALI İNDİRME: her sayfadayken o sayfanın
                    # sira'larıyla (DOM sırası) ZIP'ler indirilir; sayfa
                    # geçişleri arasında sira sıfırlandığı için aynı
                    # sayfada kalan belgelerin tamamı o sayfadayken.
                    indirilen_yollar = set()
                    for _sayfa in range(1, 60):
                        sayfa_satirlari = _satirlari_ayikla(
                            cerceve.content())
                        sayfa_hedef = []
                        for sira, belge in sayfa_satirlari:
                            if not _tarih_araliginda(
                                    belge.get("belge_tarihi"),
                                    bas_tarih, bit_tarih):
                                continue
                            durum_kisa = _turk_kucult(
                                str(belge.get("onay_durumu") or ""))
                            iptal_ibare = str(
                                belge.get("iptal_itiraz") or
                                belge.get("iptal_itiraz_durumu")
                                or "").strip()
                            if (iptal_ibare
                                    or ("red" in durum_kisa)
                                    or ("iptal" in durum_kisa)
                                    or (durum_kisa
                                        and "onay" not in durum_kisa)):
                                continue
                            belge_no = (belge.get("belge_numarasi")
                                        or f"belge{sira}").strip()
                            # Bu sayfadaki geçerli tekrarlar: ilk_gör =
                            # global görülme sayısı (tumsayfadaki konum).
                            g_say = gorulen_no.get(belge_no, 1)
                            hedef = _hedef_zip(belge_no, g_say)
                            # Aynı sayfada aynı belge_no ikinci kez varsa
                            # dosya adı _2 ile devam eder.
                            sayfa_hedef.append((sira, hedef, belge_no))
                        # Sadece henüz inmemis olanları indir
                        bekleyen = []
                        for sira, hedef, bno in sayfa_hedef:
                            if hedef not in indirilen_yollar \
                                    and not _dosya_saglam(hedef):
                                bekleyen.append((sira, hedef))
                        if bekleyen:
                            _zip_toplu_indir(cerceve, sayfa2,
                                             list(bekleyen), bildir)
                            indirilen_yollar.update(h for _, h in bekleyen)
                        tam_sayfa = len(sayfa_satirlari) >= SAYFA_LIMITI
                        sonraki_var = _sonraki_sayfa_var_mi(cerceve)
                        if not sonraki_var and not tam_sayfa:
                            break
                        if not _sonraki_sayfaya_git(cerceve):
                            if tam_sayfa:
                                try:
                                    cerceve.page.wait_for_timeout(1300)
                                    continue
                                except Exception:
                                    pass
                            break

                    # Kayıt oluştur: indirilen/hedef ZIP'lerden özet oku.
                    for numara, (sira, belge, belge_no, gor_c) \
                            in enumerate(tum_secili, 1):
                        zip_yol = _hedef_zip(belge_no, gor_c)
                        ozet = {}
                        if not _dosya_saglam(zip_yol):
                            try:
                                _zip_tikla_indir(cerceve, sayfa2, sira,
                                                 zip_yol)
                            except Exception as hata:
                                bildir(f"{kategori}: {belge_no} inmedi "
                                       f"({str(hata)[:50]}), atlanıyor.")
                                continue
                        ozet = _zipten_ozet(zip_yol)
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
                        # Her belge indikçe takip ekranı güncellensin.
                        olay({"kategori": kategori, "adim": "indirildi",
                              "durum": "calisiyor",
                              "sayi": len(kayitlar),
                              "toplam": len(secili),
                              "mesaj": f"{birim}: {len(kayitlar)}/"
                                       f"{len(secili)} indirildi"})
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
                    bildir(f"{kategori}: TAMAMLANDI — {len(kayitlar)} belge.")
                    olay({"kategori": kategori, "adim": "bitti",
                          "durum": "tamam", "sayi": len(kayitlar),
                          "toplam": len(secili),
                          "mesaj": f"{birim}: {len(kayitlar)} belge tamam"})
                except Exception as hata:
                    # Tek kategori inmedi: digerlerini engelleme.
                    bildir(f"{kategori}: HATA — {str(hata)[:80]}")
                    olay({"kategori": kategori, "adim": "hata",
                          "durum": "hata", "sayi": 0, "toplam": 0,
                          "mesaj": f"{birim}: {str(hata)[:80]}"})
                    _hata_ekrani_kaydet(sayfa, f"belge_{kategori}")
        finally:
            tarayici.close()
    if not sonuc:
        raise LucaHata(
            "Luca'dan hiçbir e-Belge kategorisi indirilemedi. Ekran "
            "görüntüleri %TEMP% altına kaydedildi.")
    return sonuc
