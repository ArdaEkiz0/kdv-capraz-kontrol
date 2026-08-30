import re
import urllib.parse
from playwright.sync_api import Page, Frame
from .exceptions import LucaLoginHata, LucaTimeoutHata

class LucaAuthenticator:
    """Luca login işlemlerini ve ilk firma/dönem seçimini yönetir."""
    
    def __init__(self, page: Page, bildir=None):
        self.page = page
        self.bildir = bildir or (lambda s: None)
    
    def giris_yap(self, uye_no: str, kullanici: str, parola: str, firma_adi: str = None) -> Frame:
        """Luca'ya giriş yapar, CAPTCHA bekler, MM paketine girer ve istenen firmayı seçer."""
        self.bildir("Luca'ya giriş yapılıyor...")
        
        try:
            self.page.goto("https://luca.com.tr", timeout=45000)
            
            # Form doldurma
            self.page.fill("#musteriNo", uye_no)
            self.page.fill("#kullaniciAdi", kullanici)
            self.page.fill("#parola", parola)
            self.page.click("#GirisUyePopup")
        except Exception as e:
            raise LucaLoginHata(f"Luca ana sayfası yüklenemedi veya form doldurulamadı: {e}")
            
        # Captcha kontrolü
        try:
            captcha_uyari = self.page.locator("text=Resimdeki Kodu Giriniz")
            if captcha_uyari.is_visible(timeout=5000):
                self.bildir("Captcha isteniyor: tarayıcı penceresindeki alana görüntüdeki kodu elle girip Tamam'a basın (180 sn)...")
                # 3 dakika (180sn) icinde .MMBtn (Mali Müşavir Paketi) veya frm1_frame gelmesini bekle
                self.page.wait_for_function("""
                    () => document.querySelector('.MMBtn') !== null || 
                          document.querySelector('frame[name="frm1_frame"]') !== null ||
                          document.querySelector('.isletmeBtn') !== null
                """, timeout=180000)
                self.bildir("Captcha girildi; devam ediliyor.")
        except Exception:
            raise LucaLoginHata("Captcha zaman aşımına uğradı veya giriş başarısız.")
            
        # Başarılı girişten sonra MM paketi penceresini bulalım
        if self.page.locator('.MMBtn').is_visible():
            self.bildir("Mali Müşavir Paketi penceresi açılıyor...")
            self.page.evaluate("gonder('formTarget')")
            
        # Şimdi ana sisteme girdik. frm1_frame (üst çerçeve) ve frm3 (ana çalışma alanı) yüklenmeli
        self.page.wait_for_timeout(2000)
        self.page.wait_for_selector("frame[name='frm1_frame']", timeout=30000)
        frm1 = self.page.frame(name="frm1_frame")
        
        if not frm1:
            raise LucaLoginHata("Luca üst menü çerçevesi (frm1_frame) bulunamadı.")
            
        self.bildir("Luca'ya giriş başarılı.")
        
        # Firma Seçimi
        if firma_adi:
            self.bildir(f"Luca firması seçiliyor: {firma_adi}")
            try:
                frm1.wait_for_selector("#SirketCombo", timeout=10000)
                secenekler = frm1.query_selector_all("#SirketCombo option")
                eslesmeler = [
                    opt for opt in secenekler
                    if firma_adi.lower() in (opt.inner_text() or "").lower()
                ]
                
                if eslesmeler:
                    secili_deger = eslesmeler[0].get_attribute("value")
                    secili_metin = (eslesmeler[0].inner_text() or "").strip()
                    frm1.select_option("#SirketCombo", value=secili_deger)
                    self.bildir(f"Firma seçildi: {secili_metin}")
                else:
                    self.bildir(f"UYARI: '{firma_adi}' adlı firma bulunamadı. Aktif olan devam ediyor.")
            except Exception as e:
                self.bildir(f"Firma seçimi yapılamadı: {e}")
                
        # Dönem Seçimi (Sürekli Güncel Yıl veya Aralık İçin Gerekebilir - Eski kodda yoktu ama ekliyoruz)
        try:
            frm1.wait_for_selector("#DonemCombo", timeout=5000)
            secili_donem = frm1.evaluate("document.querySelector('#DonemCombo').options[document.querySelector('#DonemCombo').selectedIndex].text")
            self.bildir(f"Aktif Dönem: {secili_donem}")
        except:
            pass
            
        # Bütün operasyonların yürütüleceği frm3 isimli IFrame'in dönülmesi
        self.page.wait_for_selector("frame[name='frm3']", timeout=15000)
        cerceve = self.page.frame(name="frm3")
        if not cerceve:
            raise LucaLoginHata("Ana çalışma çerçevesi (frm3) bulunamadı.")
            
        return cerceve
