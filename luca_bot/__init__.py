from playwright.sync_api import sync_playwright
from .exceptions import LucaHata
from .authenticator import LucaAuthenticator
from .navigator import LucaNavigator
from .downloader import LucaDownloader
from .parser import InvoiceParser

def cek_luca_belgeleri(uye_no, kullanici, parola, bas_tarih, bit_tarih,
                       hedef_klasor, kategoriler=None, ilerleme=None,
                       gorunur=True, firma_adi=None, duz_yaz=True,
                       olay=None, onay_callback=None):
    """
    KDV Çapraz Kontrol arayüzü ile uyumlu, modern Luca Bot yöneticisi.
    Eski luca_cekme.py yerine bu modül çalışacaktır.
    """
    bildir = ilerleme or (lambda s: None)
    sonuc = {}
    
    if kategoriler is None:
        kategoriler = ["earsiv_alis", "earsiv_satis", "efatura_alis", "efatura_satis"]

    with sync_playwright() as p:
        # Browser'ı başlat
        browser = p.chromium.launch(headless=not gorunur)
        context = browser.new_context(viewport={"width": 1200, "height": 800}, accept_downloads=True)
        page = context.new_page()
        
        try:
            # 1. Giriş Aşoması
            auth = LucaAuthenticator(page, bildir)
            if onay_callback and not onay_callback():
                return sonuc
                
            cerceve = auth.giris_yap(uye_no, kullanici, parola, firma_adi)
            
            # 2. Kategorileri Gez ve İndir
            nav = LucaNavigator(cerceve, bildir)
            dwn = LucaDownloader(cerceve, bildir)
            parser = InvoiceParser(hedef_klasor, bildir)
            
            for kat in kategoriler:
                sonuc[kat] = {"zip": []}
                # Kategori URL karşılığı
                tur = f"gib_{kat}"
                if kat == "earsiv_alis": tur = "gib_ebelge_alis"
                if kat == "earsiv_satis": tur = "gib_ebelge_satis"
                
                try:
                    nav.sayfaya_git_ve_getir(tur, bas_tarih, bit_tarih)
                    nav.satir_sayisini_genislet()
                    
                    # İndirme motorunu çalıştır
                    zip_yolu = dwn.indir()
                    
                    if zip_yolu:
                        # Parse edip yolları al
                        cikan_yollar = parser.zip_cikar(zip_yolu, kat)
                        sonuc[kat]["zip"].extend(cikan_yollar)
                        
                except Exception as e:
                    bildir(f"HATA: {kat} kategorisi işlenirken bir sorun oluştu: {e}")
                    continue
                    
        except Exception as genel_hata:
            bildir(f"Luca Bot Hatası: {genel_hata}")
            raise LucaHata(str(genel_hata))
        finally:
            context.close()
            browser.close()
            
    return sonuc
