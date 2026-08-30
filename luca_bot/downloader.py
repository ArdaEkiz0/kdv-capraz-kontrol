import os
import uuid
import queue
from playwright.sync_api import Frame

class LucaDownloader:
    """Listelenmiş e-belgelerin tamamını seçer ve ZIP olarak güvenle indirir."""
    
    def __init__(self, cerceve: Frame, bildir=None):
        self.cerceve = cerceve
        self.page = cerceve.page
        self.bildir = bildir or (lambda s: None)
        
    def _uyarilari_gec(self):
        """Çıkabilecek olan Javascript Dialog (Alert/Confirm) mesajlarını otomatik onaylar."""
        def oto_onay(dialog):
            try:
                self.bildir(f"Luca mesaji: {dialog.message}")
                dialog.accept()
            except:
                pass
        self.page.on('dialog', oto_onay)
        return oto_onay
        
    def _tumu_sec(self) -> bool:
        """Tablodaki tüm belgeleri seçer."""
        self.bildir("Tüm belgeler seçiliyor...")
        secildi = False
        
        # Strateji 1: Header Checkbox
        try:
            baslik_cb = self.cerceve.query_selector(
                "table input[type='checkbox'], th input[type='checkbox'], "
                "thead input[type='checkbox'], .grid-header input[type='checkbox']"
            )
            if baslik_cb and baslik_cb.is_visible():
                baslik_cb.click()
                self.page.wait_for_timeout(1000)
                secildi = True
        except:
            pass
            
        # Strateji 2: Satır Satır Checkbox
        if not secildi:
            try:
                tum_cb = self.cerceve.query_selector_all(
                    "td input[type='checkbox'], tbody input[type='checkbox'], table input[type='checkbox']"
                )
                tiklanan = 0
                for cb in tum_cb:
                    try:
                        if cb.is_visible() and not cb.is_checked():
                            cb.click()
                            tiklanan += 1
                            self.page.wait_for_timeout(50) # Cok hizli yapalim
                    except:
                        continue
                if tiklanan > 0:
                    secildi = True
            except:
                pass
                
        return secildi

    def indir(self) -> str:
        """
        Görünür belgeleri seçer ve 4 aşamalı agresif algoritmayla ZIP indirmeyi dener.
        Dönerse inen ZIP dosyasının tam yolunu, dönmezse None döner.
        """
        # Ekranda hiç veri var mı kontrol edelim
        try:
            satirlar = self.cerceve.query_selector_all("tbody tr, table tr.grid-row")
            if not satirlar or len(satirlar) <= 1:
                self.bildir("İndirilecek (listelenmiş) belge bulunamadı.")
                return None
        except:
            pass # Guvenli gecis
            
        if not self._tumu_sec():
            self.bildir("UYARI: Tabloda seçilecek bir belge (checkbox) bulunamadı.")
            return None
            
        dialog_handler = self._uyarilari_gec()
        
        self.bildir("'Seçilenleri İndir' butonu aranıyor...")
        butonlar = self.cerceve.query_selector_all(
            "input[type='button'][value*='Seçilenleri' i], input[type='submit'][value*='Seçilenleri' i], "
            "button:has-text('Seçilenleri'), a:has-text('Seçilenleri İndir'), a:has-text('Seçilenleri'), "
            "input[value*='Seçilenleri'], .button:has-text('Seçilenleri')"
        )
        
        indir_buton = None
        for b in butonlar:
            if b.is_visible():
                indir_buton = b
                break
                
        if not indir_buton and len(butonlar) > 0:
            indir_buton = butonlar[-1]

        if indir_buton is None:
            self.bildir("UYARI: İndirme butonu bulunamadı.")
            self.page.remove_listener('dialog', dialog_handler)
            return None
            
        kuyruk = queue.Queue()
        dinleyici = lambda d: kuyruk.put(d)
        popup_dinleyici = lambda popup: popup.on("download", lambda d: kuyruk.put(d))
        
        self.page.on("download", dinleyici)
        self.page.on("popup", popup_dinleyici)
        self.page.wait_for_timeout(200)
        
        onclick_kodu = None
        try:
            onclick_kodu = indir_buton.get_attribute("onclick")
            if not onclick_kodu and len(butonlar) > 1:
                onclick_kodu = butonlar[0].get_attribute("onclick")
        except:
            pass

        basari = False
        indirme = None
        
        # AGRESİF İNDİRME DÖNGÜSÜ
        stratejiler = [
            ("Standart Click", lambda: indir_buton.click(force=True), 20),
            ("MouseEvent", lambda: indir_buton.evaluate("node => { node.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window})); }"), 20),
        ]
        
        if onclick_kodu:
            stratejiler.append(("Onclick Yeni Sekme", lambda: self.cerceve.evaluate(f"window.__onay_kod = `{onclick_kodu}`; eval(window.__onay_kod);"), 20))
            stratejiler.append(("Onclick Self Form", lambda: self.cerceve.evaluate("Array.from(document.querySelectorAll('form')).forEach(f => f.removeAttribute('target')); window.__onay_kod = `""" + onclick_kodu + """`; eval(window.__onay_kod);"), 30))

        for ad, func, sure in stratejiler:
            if basari: break
            self.bildir(f"Strateji: {ad} deneniyor...")
            try:
                func()
                indirme = kuyruk.get(timeout=sure)
                basari = True
            except queue.Empty:
                pass
            except Exception as e:
                self.bildir(f"Strateji Hatası ({ad}): {str(e)[:50]}")

        # Dinleyicileri temizle
        try:
            self.page.remove_listener("download", dinleyici)
            self.page.remove_listener("popup", popup_dinleyici)
            self.page.remove_listener("dialog", dialog_handler)
        except:
            pass

        if not basari or indirme is None:
            self.bildir("HATA: İndirme işlemi stratejilerin hiçbirisiyle başlatılamadı.")
            return None

        hedef_zip = os.path.join(os.environ.get("TEMP", "C:/Windows/Temp"), f"luca_toplu_{uuid.uuid4().hex[:8]}.zip")
        try:
            indirme.save_as(hedef_zip)
            self.bildir("ZIP başarıyla indirildi.")
            return hedef_zip
        except Exception as e:
            self.bildir(f"İnen dosya kaydedilemedi: {e}")
            return None
