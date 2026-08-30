import re
from playwright.sync_api import Frame
from .exceptions import LucaTimeoutHata

class LucaNavigator:
    """Luca içindeki e-Belge sayfalarına gider, tarih aralıklarını ayarlar ve listeyi çeker."""
    
    def __init__(self, cerceve: Frame, bildir=None):
        self.cerceve = cerceve
        self.page = cerceve.page
        self.bildir = bildir or (lambda s: None)
        
    def _tarih_gir(self, no: int, tarih):
        """1. veya 2. tarih kutusuna (ör. 01.01.2024) tarih yazar."""
        gun = f"{tarih.day:02d}"
        ay = f"{tarih.month:02d}"
        yil = str(tarih.year)
        
        # input name=tarih_1 veya tarih_2
        secici = f"input[name='tarih_{no}']"
        try:
            kutu = self.cerceve.locator(secici)
            kutu.wait_for(state="visible", timeout=5000)
            
            # Luca'nın maskeli tarih girişlerini ezmek için JavaScript kullanalım
            self.cerceve.evaluate(f"""
                var el = document.querySelector("{secici}");
                if(el) {{
                    el.value = "{gun}.{ay}.{yil}";
                    // Olası değişiklik eventlerini tetikle
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                }}
            """)
        except Exception as e:
            self.bildir(f"Tarih alanı ({no}) ayarlanamadı: {e}")

    def sayfaya_git_ve_getir(self, kategori_tur: str, bas_tarih, bit_tarih):
        """
        Belirtilen kategori ekranını açar (Örn: gib_ebelge_alis), 
        tarihleri girer, GİB'ten Getir / Listele tuşuna basar.
        """
        self.bildir(f"{kategori_tur}: ekran açılıyor...")
        
        # Eski sistemde frm3'ü baştan yüklemek için JS kullanılıyordu (Daha stabil)
        try:
            self.page.evaluate(f"""
                var f3 = document.querySelector('frame[name="frm3"]');
                if(f3) {{
                    f3.src = 'gib530.do?tur={kategori_tur}';
                }}
            """)
            self.cerceve.wait_for_load_state("networkidle", timeout=15000)
            # Sayfa içinde form'un yüklenmesini bekle
            self.cerceve.wait_for_selector("form[name='ebelgeTarihFiltreForm']", timeout=10000)
        except Exception as e:
            raise LucaTimeoutHata(f"'{kategori_tur}' sayfası yüklenemedi: {e}")
            
        # Tarihleri ayarla
        self._tarih_gir(1, bas_tarih)
        self._tarih_gir(2, bit_tarih)
        
        # 'GİB'ten Getir' VEYA 'Listele' Butonuna Bas
        self._getir_butonuna_bas()
        
    def _getir_butonuna_bas(self):
        """Listeyi getirecek olan asıl butonu bulur ve tıklar."""
        butonlar = self.cerceve.query_selector_all(
            "input[type='button'][value*='Getir' i], "
            "input[type='submit'][value*='Getir' i], "
            "button:has-text('Getir'), "
            "input[type='button'][value*='Listele' i], "
            "input[type='submit'][value*='Listele' i], "
            "button:has-text('Listele')"
        )
        
        hedef_buton = None
        for b in butonlar:
            if b.is_visible():
                hedef_buton = b
                break
                
        if hedef_buton:
            self.bildir("Listele / GİB'ten Getir butonu tıklandı.")
            try:
                hedef_buton.click()
                self.cerceve.wait_for_load_state("networkidle", timeout=20000)
            except Exception as e:
                self.bildir(f"Getir butonuna basarken hata: {e}")
        else:
            self.bildir("GİB'ten getir butonu görünmüyor; mevcut liste kullanılır.")
            
    def satir_sayisini_genislet(self):
        """Sayfadaki sonuç limitini (100 -> 500 veya Tümü) olarak genişletir."""
        genisletildi = False
        
        # YÖNTEM 1: Select Box üzerinden deneme
        selectler = self.cerceve.query_selector_all("select")
        for sel in selectler:
            try:
                if not sel.is_visible(): continue
                opsiyonlar = sel.query_selector_all("option")
                for opt in opsiyonlar:
                    val = (opt.get_attribute("value") or opt.inner_text() or "").strip()
                    # Tüm, 500, 1000, 2000 seçeneklerini ara
                    if re.match(r"^(t[üu]m[üu]|500|1000|2000)$", val, re.I):
                        sel.select_option(value=val)
                        self.cerceve.page.wait_for_timeout(2000)
                        genisletildi = True
                        break
            except:
                pass
            if genisletildi: break
            
        # YÖNTEM 2: Eski sistem Buton/Link üzerinden deneme (Örn: '500')
        if not genisletildi:
            butonlar = self.cerceve.query_selector_all(
                "input[type='button'], input[type='submit'], button, a"
            )
            for b in butonlar:
                try:
                    if b.is_visible():
                        metin = (b.inner_text() or b.get_attribute("value") or "").strip()
                        if re.match(r"^(t[üu]m[üu]|500|1000|2000)$", metin, re.I):
                            b.click()
                            self.cerceve.page.wait_for_timeout(2000)
                            genisletildi = True
                            break
                except:
                    pass
        
        if genisletildi:
            self.bildir("Sayfalama genişletildi (Tek sayfa görünümü aktif).")
            # Yükleme için kısa bir süre tanıyalım
            self.cerceve.page.wait_for_timeout(3000)
