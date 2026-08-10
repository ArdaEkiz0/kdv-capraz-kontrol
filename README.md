# 📊 KDV Çapraz Kontrol Programı

![Program Ekran Görüntüsü](screenshot.png)

Bu program e-Fatura, PDF ve Excel faturalarınızı KDV kontrol cetveli ile karşılaştırır.

Farkları, eksikleri ve hataları otomatik bulur. Excel ve PDF rapor üretir.

## 👨‍💻 Geliştirici

**Arda M. Ekiz**

---

## 🚀 Nasıl Kurulur? (Adım Adım)

### Adım 1: Python'u İndirin ve Kurun (Python yoksa)

Program çalışması için bilgisayarınızda Python olması gerekir. Python yüklü mü, bakalım:

1. Klavyeden **Windows + R** tuşlarına basın
2. Açılan kutuya **cmd** yazın ve **Enter**'a basın
3. Siyah ekrana şunu yazın: `py -3.12 --version`

- ✅ **"Python 3.12.x"** yazıyorsa → Python kurulu, Adım 2'ye geçin
- ❌ **"Python bulunamadı"** yazıyorsa → **[Python 3.12'yi buradan indirin](https://www.python.org/downloads/release/python-31210/)** ve kurun
  - Kurulumda **"Add python.exe to PATH"** kutusunu **işaretlemeyi unutmayın!**
  - Kurulum bitince **cmd penceresini kapatıp yeniden açın** ve 3. adımdaki komutu tekrar deneyin

### Adım 2: Programı İndirin

1. [GitHub Release sayfasına](https://github.com/ArdaEkiz0/kdv-capraz-kontrol/releases) gidin
2. En üstteki en yeni sürümün **`kdv-kontrol-vX.X.X.zip`** dosyasını indirin
3. Zip'e sağ tıklayın → **"Tümünü Ayıkla"** deyin
4. Çıkan klasörü bilgisayarınızda kolay bulacağınız bir yere taşıyın (ör. `C:\KDV Kontrol`)

### Adım 3: Programı Çalıştırın

- Proje klasöründeki **`calistir.bat`** dosyasına **çift tıklayın**
- Program ilk açılışta eksik kütüphaneleri **otomatik kurar** (1-2 dakika sürebilir), sonra açılır
- Daha sonraki açılışlarda direkt açılır

> ⚠️ **Not:** İlk açılışta Windows Defender uyarı verebilir. "Daha fazla bilgi" → "Yine de çalıştır" deyin.

> ⚠️ **Not:** `calistir.bat` açılırken kısa bir siyah pencere açılıp kapanması normaldir, uygulama ayrı pencere olarak açılır.

---

## 🔄 Eski Sürümden (v2.0) Güncelleme

v2.0.0 kullanıcılarının güncelleme butonu yoktur (o özellik v2.1.0 ile geldi). Bir kez elle güncellemeniz gerekir:

1. [GitHub Release sayfasından](https://github.com/ArdaEkiz0/kdv-capraz-kontrol/releases) en yeni sürümün **zip dosyasını indirin**
2. Zip'in içindeki dosyaları **eski proje klasörünüzün içine kopyalayın** (dosya var uyarısına "Evet / Değiştir" deyin)
3. `calistir.bat`'a tıklayın → artık en yeni sürüm çalışıyor

Bundan sonraki sürümlerde bu işlemi yapmanıza gerek yok: program her açılışta yeni sürümü otomatik kontrol eder, çıkan **"🔄 Güncelleme"** butonuyla kendini günceller.

---

## 📖 Nasıl Kullanılır? (5 Adım)

### 1️⃣ Faturalarınızı Seçin

- **"Fatura Klasörü Seç"** butonuna tıklayın
- Fatura dosyalarınızın olduğu klasörü seçin
- (XML, PDF veya Excel olabilir)

### 2️⃣ KDV Cetvelinizi Seçin

- **"KDV Cetveli Klasörü"** butonuna tıklayın
- KDV kontrol cetvelinizin klasörünü seçin
- (Birden fazla dosya varsa hepsini seçer)

### 3️⃣ Kontrolü Başlatın

- **"Kontrolü Başlat"** butonuna tıklayın
- Biraz bekleyin, sonuçlar tabloya gelecek

### 4️⃣ Sonuçları İnceleyin

Tabloda göreceksiniz:

- ✅ **Yeşil** = Eşleşen (sorun yok)
- 🟡 **Sarı** = Dikkat (VKN farkı, mükerrer)
- 🔴 **Kırmızı** = Sorunlu (tutar farkı, eksik)

### 5️⃣ Rapor Alın

- **"Excel Raporunu Kaydet"** → Excel raporu
- **"PDF Raporunu Kaydet"** → PDF raporu
- **"📧 Mail Gönder"** → Muhasebecinize mail atın

---

## ❓ Sık Sorulan Sorular

### Program açılmıyor, hata veriyor?

**C:** `calistir.bat` artık hatayı ekranda gösterir. Ekrandaki komutu (pip install) çalıştırıp tekrar deneyin. Hata devam ederse ekrandaki bilgiyi geliştiriciyle paylaşın.

### "python bulunamadı" hatası alıyorum?

**C:** Python'u kurarken **"Add to PATH"** kutusunu işaretlemeyi unutmuşsunuz. Python'u kaldırıp tekrar kurun veya [buradan](https://www.python.org/downloads/release/python-31210/) indirirken kutuya dikkat edin.

### Python yüklerken hangi sürümü seçeyim?

**C:** **Python 3.12** önerilir. Kurulum penceresinde en alttaki **"Add python.exe to PATH"** kutusunu **mutlaka işaretleyin**.

### Mail gönder butonu çalışmıyor?

**C:** Gmail kullanıyorsanız [Uygulama Şifresi](https://myaccount.google.com/apppasswords) oluşturmanız gerekir.

### Türkçe karakterler bozuk görünüyor?

**C:** Bilgisayarınızın bölgesel ayarlarından "Türkiye" seçili olduğundan emin olun.

### Excel/PDF rapor oluşmuyor?

**C:** Programı kapatıp yeniden açın, klasör yazma izniniz olduğundan emin olun.

---

## 💡 İpuçları

- **Ayarlar hatırlanır**: Son kullandığınız klasörler otomatik kaydedilir
- 🔍 **Gelişmiş Filtre**: Tarih, VKN, tutar aralığı ile detaylı arama yapabilirsiniz
- 📊 **Dashboard**: KPI kartları ve grafiklerle özet görün
- 📅 **Aylık Trend**: Eski kontrollerinizle karşılaştırma yapabilirsiniz
- 🔄 **Otomatik Güncelleme**: Program açılışta GitHub'daki yeni sürümü kontrol eder. Yeni sürüm çıkınca **"Güncelleme" butonu** sürüm numarasını gösterir. Tıklayın, sürüm notlarını görün, **"İndir & Kur"** deyin — program kendini günceller ve yeniden başlar.

---

## 🔄 Güncellemeler

- Program her açılışta GitHub'daki son sürümü otomatik kontrol eder
- Yeni sürüm varsa üstteki **"🔄 Güncelleme (vX.X.X)"** butonu görünür
- Butona tıklayın → sürüm notlarını okuyun → **"İndir & Kur"** → uygulama otomatik yeniden başlar
- Sürüm kontrolü internet gerektirir; internet yoksa kontrol sessizce geçilir

---

## 📞 İletişim

Sorun mu yaşıyorsunuz? Bana ulaşın:

- 🐙 **GitHub**: [ArdaEkiz0](https://github.com/ArdaEkiz0)
- 🔗 **LinkedIn**: [arda-mehmet-ekiz](https://www.linkedin.com/in/arda-mehmet-ekiz-107640333/)
- 📷 **Instagram**: [@ardaaekiz](https://www.instagram.com/ardaaekiz/)
- 📧 **E-posta**: ardaekiz72@gmail.com

---

## ⚖️ Lisans

Bu program MIT Lisansı ile korunmaktadır. Telif Hakkı © 2026 Arda M. Ekiz.

Detaylar için [LICENSE](LICENSE) dosyasına bakın.
