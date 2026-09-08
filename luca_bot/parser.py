import os
import zipfile
import shutil

class InvoiceParser:
    """İndirilen ZIP dosyasını hedefe çıkarır ve geçerli fatura yollarını döndürür."""
    
    def __init__(self, hedef_klasor: str, bildir=None):
        self.hedef_klasor = hedef_klasor
        self.bildir = bildir or (lambda s: None)
        os.makedirs(self.hedef_klasor, exist_ok=True)
        
    def zip_cikar(self, zip_yolu: str, kategori_adi: str) -> list:
        """ZIP dosyasını açar ve içindeki faturaları hedef klasöre kopyalar."""
        cikan_dosyalar = []
        islenen = 0
        
        if not zip_yolu or not os.path.exists(zip_yolu):
            self.bildir(f"HATA: Çıkarılacak ZIP dosyası bulunamadı ({zip_yolu})")
            return cikan_dosyalar
            
        try:
            with zipfile.ZipFile(zip_yolu, 'r') as zipp:
                icindekiler = zipp.namelist()
                for ic_ad in icindekiler:
                    # Klasör yapılarını atla
                    if ic_ad.endswith("/"): continue
                    
                    # Sadece geçerli fatura formatlarını al
                    if ic_ad.lower().endswith((".xml", ".html", ".htm", ".pdf", ".zip")):
                        hedef_dosya = os.path.join(self.hedef_klasor, f"{kategori_adi}_{os.path.basename(ic_ad)}")
                        
                        # İçeriği diske yaz
                        icerik = zipp.read(ic_ad)
                        with open(hedef_dosya, "wb") as f:
                            f.write(icerik)
                            
                        cikan_dosyalar.append(hedef_dosya)
                        islenen += 1
                        
            self.bildir(f"{kategori_adi}: {islenen} belge dosyası ZIP'ten çıkarıldı.")
        except Exception as e:
            self.bildir(f"ZIP çıkarma hatası ({kategori_adi}): {e}")
            
        return cikan_dosyalar
