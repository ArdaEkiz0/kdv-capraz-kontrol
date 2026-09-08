<div align="center">

# 📊 KDV Çapraz Kontrol Programı

**e-Fatura, MAHSUP Fişi ve Excel faturalarınızı KDV kontrol cetveli ile otomatik karşılaştırın.**

Farkları, eksikleri ve hataları saniyeler içinde bulun.

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-00FF00?style=for-the-badge)](LICENSE)
[![Version](https://img.shields.io/badge/Version-v2.2.2-FF6B00?style=for-the-badge)](https://github.com/ArdaEkiz0/kdv-capraz-kontrol/releases)
[![Windows](https://img.shields.io/badge/Platform-Windows-0078D4?style=for-the-badge&logo=windows&logoColor=white)](https://microsoft.com)

---

</div>

## ✨ Özellikler

| Özellik | Açıklama |
|---------|----------|
| 📄 **Çoklu Format** | e-Fatura XML, PDF, MAHSUP fişi, Excel ve taranmış belgeleri destekler |
| 🔍 **Akıllı Eşleştirme** | VKN, belge no ve tutar ile otomatik çapraz kontrol |
| 📊 **Dashboard** | KPI kartları ve grafiklerle görsel özet |
| 📧 **Mail Gönderimi** | Outlook veya SMTP ile tek tıkla muhasebecinize gönderin |
| 🔄 **Otomatik Güncelleme** | GitHub'dan yeni sürümü otomatik kontrol eder |
| 📱 **Gelişmiş Filtreleme** | Tarih, VKN, tutar aralığı ile detaylı arama |
| 💾 **Veritabanı** | Kontrol geçmişinizi saklayın ve karşılaştırın |
| 📋 **Rapor Üretimi** | Excel ve PDF formatında detaylı raporlar |

---

## 🚀 Hızlı Kurulum

### 1️⃣ Python'u Kurun

Klavyeden **Windows + R** → `cmd` yazın → Enter:

```cmd
py -3.12 --version
```

- ✅ **"Python 3.12.x"** yazıyorsa → 2. adıma geçin
- ❌ **"Python bulunamadı"** yazıyorsa → [Python'u buradan indirin](https://www.python.org/downloads/release/python-31210/)

> ⚠️ Kurulumda **"Add python.exe to PATH"** kutusunu işaretlemeyi unutmayın!

### 2️⃣ Gerekli Kütüphaneleri Kurun

```cmd
py -3.12 -m pip install pymupdf openpyxl pytesseract pillow xlrd matplotlib fpdf2
```

### 3️⃣ Programı Çalıştırın

```cmd
cd kdv-capraz-kontrol
py -3.12 -m pip install -r requirements.txt
calistir.bat
```

---

## 📖 Kullanım Kılavuzu

### 1️⃣ Faturalarınızı Seçin

**"Fatura Dosyaları Seç"** veya **"Fatura Klasörü Seç"** ile faturalarınızı yükleyin.

Desteklenen formatlar:
- 📄 **XML** → e-Fatura (UBL formatı)
- 📄 **PDF** → E-Fatura, E-Arşiv, MAHSUP fişi
- 📊 **Excel** → Fatura listesi (.xlsx, .xlsm, .xls)

### 2️⃣ KDV Cetvelinizi Seçin

**"Klasör Cetvel"** ile kontrol cetvelinizi seçin.

💡 **İpucu:** Satış muavininizi de (ör. `muavin_gokkusagi.xlsx`) seçerseniz, MAHSUP fişindeki hesap kayıtları otomatik olarak muavinle karşılaştırılır.

### 3️⃣ Kontrolü Başlatın

**"Kontrolü Başlat"** butonuna tıklayın.

Sonuçlar otomatik olarak renk kodlarıyla gösterilecek:

| Renk | Anlam |
|------|-------|
| 🟢 **Yeşil** | Eşleşen (sorun yok) |
| 🟡 **Sarı** | Dikkat (VKN farkı, mükerrer) |
| 🔴 **Kırmızı** | Sorunlu (tutar farkı, eksik belge) |

### 4️⃣ Rapor Alın

- **"Excel Raporunu Kaydet"** → Detaylı Excel raporu
- **"PDF Raporunu Kaydet"** → PDF raporu
- **"📧 Mail Gönder"** → Muhasebecinize tek tıkla gönderin

---

## 📸 Ekran Görüntüsü

<div align="center">

![Ekran Görüntüsü](screenshot.png)

</div>

---

## 🔧 Gelişmiş Özellikler

### 🎯 Akıllı Filtreleme

**"🔎 Gelişmiş Filtre"** butonu ile:
- Tarih aralığı filtreleme
- VKN bazlı arama
- Tutar aralığı filtreleme
- Durum bazlı filtreleme (Eşleşen, Sorunlu, vb.)

### 📊 Dashboard

**"📊 Dashboard"** butonu ile:
- KPI kartları (Toplam fatura, eşleşen, sorunlu)
- KDV dağılım grafiği
- Aylık trend analizi
- Veritabanı geçmişi

### 💾 Veritabanı Geçmişi

Kontrol sonuçlarınız otomatik olarak veritabanına kaydedilir. Önceki kontrollerinizle karşılaştırma yapabilirsiniz.

---

## ❓ Sık Sorulan Sorular

<details>
<summary><b>Program açılmıyor, hata veriyor?</b></summary>

`py -3.12 -m pip install pymupdf openpyxl pytesseract pillow xlrd matplotlib fpdf2` komutunu tekrar çalıştırın.
</details>

<details>
<summary><b>"Python bulunamadı" hatası alıyorum?</b></summary>

Python'u kurarken **"Add to PATH"** kutusunu işaretlemeyi unutmuşsunuz. Python'u kaldırıp tekrar kurun.
</details>

<details>
<summary><b>Mail gönder butonu çalışmıyor?</b></summary>

Gmail kullanıyorsanız [Uygulama Şifresi](https://myaccount.google.com/apppasswords) oluşturmanız gerekir.
</details>

<details>
<summary><b>Türkçe karakterler bozuk görünüyor?</b></summary>

Bilgisayarınızın bölgesel ayarlarından **"Türkiye"** seçili olduğundan emin olun.
</details>

<details>
<summary><b>500+ fatura yükledim, yavaşladı?</b></summary>

**Dönem filtresi** kullanın ("Tümü" yerine belirli bir ay seçin). 500+ fatura için optimizedir.
</details>

---

## 💡 İpuçları

- **Ayarlar hatırlanır** → Son kullandığınız klasörler otomatik kaydedilir
- **Gelişmiş Filtre** → Tarih, VKN, tutar aralığı ile detaylı arama
- **Dashboard** → KPI kartları ve grafiklerle özet görün
- **Aylık Trend** → Eski kontrollerinizle karşılaştırma yapabilirsiniz
- **Otomatik Güncelleme** → Program açılışta GitHub'daki yeni sürümü kontrol eder

---

## 🔄 Güncelleme

Program her açılışta GitHub'daki son sürümü otomatik kontrol eder.

1. Yeni sürüm varsa **"🔄 Güncelleme (vX.X.X)"** butonu görünür
2. Butona tıklayın → sürüm notlarını okuyun
3. **"İndir & Kur"** deyin
4. Program otomatik güncellenir ve yeniden başlar

---

## 📁 Proje Yapısı

```
kdv-capraz-kontrol/
├── main.py                    # Ana uygulama (GUI)
├── dosya.py                   # Dosya yönlendirme
├── efatura.py                 # E-Fatura PDF parse
├── cetvel.py                  # KDV kontrol cetveli parse
├── xml_oku.py                 # UBL XML parse
├── excel_oku.py               # Excel okuma
├── fis_listesi.py             # MAHSUP fişi parse
├── matcher.py                 # Çapraz kontrol motoru
├── report.py                  # Excel rapor üretimi
├── report_pdf.py              # PDF rapor üretimi
├── ozetler.py                 # KDV dağılımı, BA formu
├── db.py                      # Veritabanı işlemleri
├── config.py                  # Yapılandırma
├── ayarlar.py                 # Kullanıcı ayarları
├── guncelleme.py              # Otomatik güncelleme
├── dashboard.py               # Dashboard grafiği
├── utils.py                   # Yardımcı fonksiyonlar
├── surum.py                   # Sürüm bilgisi
├── calistir.bat               # Çalıştırma dosyası
├── requirements.txt           # Python kütüphaneleri
├── test_akisi.py              # Test dosyası
└── test_veri/                 # Test verileri
```

---

## 🛠️ Teknik Detaylar

### Desteklenen Formatlar

| Kaynak | Format | Açıklama |
|--------|--------|----------|
| e-Fatura | XML (UBL) | GİB onaylı e-fatura formatı |
| E-Fatura | PDF | Tek veya çok sayfalı |
| E-Arşiv | PDF | Bireysel faturalar |
| MAHSUP Fişi | PDF | Hesap bazlı kayıtlar |
| Fatura Listesi | Excel | VKN, matrah, KDV sütunları |
| KDV Cetveli | PDF/Excel | Kontrol cetveli formatı |
| Satış Muavini | Excel | Hesap bazlı satış kayıtları |

### KDV Hesaplama

- **Matrah** = KDV Tutarı × 100 / KDV Oranı
- **Toplam** = Matrah + KDV
- **Oranlar** %1, %10, %20 desteklenir

---

## 📞 İletişim

Sorun mu yaşıyorsunuz? Bana ulaşın:

| Platform | Link |
|----------|------|
| 🐙 **GitHub** | [@ArdaEkiz0](https://github.com/ArdaEkiz0) |
| 🔗 **LinkedIn** | [Arda M. Ekiz](https://www.linkedin.com/in/arda-mehmet-ekiz-107640333/) |
| 📷 **Instagram** | [@ardaaekiz](https://www.instagram.com/ardaaekiz/) |
| 📧 **E-posta** | ardaekiz72@gmail.com |

---

## ⚖️ Lisans

Bu program MIT Lisansı ile korunmaktadır.

```
MIT License

Copyright (c) 2026 Arda M. Ekiz

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

<div align="center">

**Made with ❤️ by [Arda M. Ekiz](https://github.com/ArdaEkiz0)**

</div>
