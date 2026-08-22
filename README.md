<div align="center">



# KDV Çapraz Kontrol

**e-Fatura, MAHSUP fişi ve Excel faturalarınızı KDV kontrol cetveli ile otomatik karşılaştırın.**
Farkları, eksikleri ve hataları saniyeler içinde bulun.

[![Sürüm](https://img.shields.io/github/v/release/ArdaEkiz0/kdv-capraz-kontrol?style=for-the-badge&label=s%C3%BCr%C3%BCm&color=7C3AED)](https://github.com/ArdaEkiz0/kdv-capraz-kontrol/releases/latest)
[![İndirme](https://img.shields.io/github/downloads/ArdaEkiz0/kdv-capraz-kontrol/total?style=for-the-badge&label=indirme&color=2563EB)](https://github.com/ArdaEkiz0/kdv-capraz-kontrol/releases)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Windows](https://img.shields.io/badge/Platform-Windows-0078D4?style=for-the-badge&logo=windows&logoColor=white)](https://microsoft.com)
[![Lisans](https://img.shields.io/badge/Lisans-MIT-16A34A?style=for-the-badge)](LICENSE)

<img src="screenshot.png" width="100%" alt="KDV Çapraz Kontrol ana ekran">

</div>

---

## ✨ Özellikler

| Özellik | Açıklama |
|---------|----------|
| 📄 **Çoklu Format** | e-Fatura XML (UBL), e-Fatura/e-Arşiv PDF, MAHSUP fişi, Excel fatura listeleri ve taranmış belgeler (OCR) |
| 🔍 **Akıllı Eşleştirme** | VKN + belge no + tutar ile çapraz kontrol; iade faturaları otomatik ayristirma |
| 🧮 **KDV Oran Kontrolü** | Faturadaki KDV oranı ↔ cetvel tutarlılığını ayrıca doğrular (%1 / %5 / %10 / %20) |
| ✂️ **Tevkifat Desteği** | KDV tevkifatlı kayıtları muavin ile oran bazında karşılaştırır |
| 📊 **Dashboard** | KPI kartları, KDV dağılım grafiği ve aylık trend analizi |
| 🏪 **Satıcı Özeti** | Satıcı bazında toplam matrah/KDV kırılımı |
| 🧾 **Beyanname Karşılaştırma** | Kontrol sonuçlarını 2 Beyanname dönem toplamlarıyla karşılaştırır |
| 📑 **Ba/Bs Formu** | Muhtasar Ba-Bs formu üretimi |
| 💾 **Veritabanı Geçmişi** | Her kontrol otomatik saklanır; eski kontrollerle karşılaştırın |
| 🔎 **Gelişmiş Filtre** | Tarih aralığı, VKN, tutar aralığı ve duruma göre filtreleme |
| 📋 **Rapor Üretimi** | Detaylı Excel ve PDF raporları |
| ✉️ **Mail Gönderimi** | Outlook veya SMTP ile tek tıkla muhasebecinize gönderin |
| 🖥️ **Komut Satırı Modu** | Toplu işlerde GUI olmadan çalıştırın (`cli.py`) |
| 🔄 **Otomatik Güncelleme** | Program açılışta yeni sürümü kontrol eder, tek tıkla güncellenir |

---

## 🚀 Hızlı Kurulum

### Tek Tıkla (Önerilen)

1. Son sürümü indirin: [**Releases → Latest**](https://github.com/ArdaEkiz0/kdv-capraz-kontrol/releases/latest) → `kdv-kontrol-vX.X.X.zip` → klasöre çıkartın
2. **`calistir.bat`** dosyasını çift tıklayın — hepsi bu!

> `calistir.bat` gerekirse Python'u otomatik indirip kurar, tüm kütüphaneleri yükler ve programı başlatır. İlk kurulumdan sonra masaüstünde logolu kısayol oluşturulur.

### Manuel Kurulum (Alternatif)

Python 3.12+ zaten kuruluysa:

```cmd
git clone https://github.com/ArdaEkiz0/kdv-capraz-kontrol.git
cd kdv-capraz-kontrol
py -3 -m pip install -r requirements.txt
calistir.bat
```

---

## 📖 Kullanım

### 1️⃣ Faturaları Seçin
- **Fatura Dosyaları Seç** → tek tek dosya seçin (XML / PDF / Excel)
- **Fatura Klasörü Seç** → klasördeki tüm faturaları bir kerede yükleyin

### 2️⃣ Cetveli Seçin
- **Kontrol Cetveli Seç** → KDV kontrol cetvelinizi seçin (.xlsx)
- Birden fazla cetvel dosyasını birlikte seçebilirsiniz
- 💡 Satış muavinini de seçerseniz MAHSUP fişleri muavinle karşılaştırılır

### 3️⃣ Kontrolü Başlatın
Sonuçlar renk kodlarıyla anında listelenir:

| Durum | Renk | Anlam |
|-------|------|-------|
| **EŞLEŞTİ** | 🟢 Yeşil | Fatura ↔ cetvel tam uyumlu |
| **TEVKİFATLI** | 🔵 Mavi | Tevkifat sonrası muavinle uyumlu |
| **İNDİRİMLİ** | 🔵 Mavi | İndirimli orandan hesaplandı |
| **TUTAR FARKI** | 🔴 Kırmızı | Matrah/KDV tutarları farklı |
| **VKN FARKI** | 🔴 Kırmızı | Aynı belge no, farklı VKN |
| **MÜKERRER** | 🔴 Kırmızı | Aynı belge iki kez kayıtlı |
| **CETVELDE YOK** | 🔴 Kırmızı | Fatura cetvele işlenmemiş |
| **FATURALARDA YOK** | 🔴 Kırmızı | Cetvelde kayıt var, fatura yok |

### 4️⃣ Rapor Alın
- **Excel Raporu** / **PDF Raporu** → detaylı rapor kaydedin
- **Mail** → raporu doğrudan gönderin
- Herhangi bir satıra çift tıklayın → belge detay penceresi açılır; belge numarasını tek tıkla kopyalayabilirsiniz

---

## 🔧 Gelişmiş Araçlar

<details>
<summary><b>📊 Dashboard</b> — KPI kartları, KDV dağılım grafiği, aylık trend</summary>

Kontrol sonuçlarınızı görsel olarak özetler; geçmiş kontrollerle karşılaştırma yapabilirsiniz.
</details>

<details>
<summary><b>🧮 Oran Kontrolü</b> — KDV oranı tutarlılık denetimi</summary>

Her eşleşen kayıt için faturadaki KDV oranı ile cetvel tutarının matematiksel uyumunu ayrıca doğrular. Yanlış oranla kesilmiş faturaları yakalar.
</details>

<details>
<summary><b>🏪 Satıcı Özeti</b> — satıcı bazlı kırılım</summary>

VKN başına toplam fatura adedi, matrah ve KDV toplamları.
</details>

<details>
<summary><b>🧾 Beyanname Karşılaştırma</b></summary>

2 Beyanname dönem toplamlarını kontrol sonuçlarınızla karşılaştırır; beyannameye girmeyen KDV'yi gösterir.
</details>

<details>
<summary><b>📑 Muhtasar Ba/Bs Formu</b></summary>

Muavin verisinden Ba-Bs formu taslağı üretir.
</details>

<details>
<summary><b>✉️ Mail Gönderimi</b></summary>

Outlook veya SMTP (Gmail için [Uygulama Şifresi](https://myaccount.google.com/apppasswords)) ile raporu tek tıkla gönderin.
</details>

---

## 🖥️ Komut Satırı Modu

GUI açmadan, toplu işlerde veya zamanlanmış görevlerde kullanın:

```cmd
py -3 cli.py --fatura C:\faturalar\ --cetvel C:\cetvel\191.xlsx --cikti rapor.xlsx --donem 2026-07
```

| Argüman | Açıklama |
|---------|----------|
| `--fatura` | Fatura dosya/klasör yolları (birden fazla verilebilir) |
| `--cetvel` | Cetvel dosya yolları (birden fazla verilebilir) |
| `--cikti` | Excel rapor çıktı yolu (isteğe bağlı) |
| `--donem` | Sadece belirli dönem, örn. `2026-07` |

---

## 🔄 Otomatik Güncelleme

Program her açılışta GitHub'daki son sürümü kontrol eder:

1. Yeni sürüm varsa üst şeritte **Güncelleme** butonu görünür
2. Butona tıklayın → sürüm notlarını okuyun → **İndir & Kur**
3. Program kendini günceller ve yeniden başlar — masaüstü kısayolu da otomatik korunur

---

## ❓ Sık Sorulan Sorular

<details>
<summary><b>Program açılmıyor?</b></summary>

`calistir.bat` dosyasını tekrar çift tıklayın; eksik bileşen varsa otomatik tamamlanır. Sorun sürüyorsa `py -3 denetim.py` komutuyla sistem denetimi çalıştırabilirsiniz.
</details>

<details>
<summary><b>"Python bulunamadı" hatası alıyorum?</b></summary>

`calistir.bat` Python'u otomatik indirir. Elle kurmak isterseniz [Python 3.12](https://www.python.org/downloads/release/python-31210/) kurulumunda **"Add python.exe to PATH"** kutusunu işaretleyin.
</details>

<details>
<summary><b>Taranmış (fotoğraf) fatura okunuyor mu?</b></summary>

Evet — OCR desteğiyle taranmış PDF/görsel faturalar da işlenebilir ([Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) kurulu olmalıdır).
</details>

<details>
<summary><b>500+ fatura yükledim, yavaşladı?</b></summary>

**Dönem filtresini** kullanın ("Tümü" yerine belirli ay). 500+ fatura için optimize edilmiştir.
</details>

<details>
<summary><b>Türkçe karakterler bozuk görünüyor?</b></summary>

Bilgisayarınızın bölgesel ayarlarında **"Türkiye"** seçili olduğundan emin olun.
</details>

---

## 📁 Proje Yapısı

```
kdv-capraz-kontrol/
├── main.py                # Ana uygulama (GUI)
├── cli.py                 # Komut satırı modu
├── matcher.py             # Çapraz kontrol motoru
├── xml_oku.py             # UBL XML parse
├── efatura.py             # E-Fatura/E-Arşiv PDF parse
├── fis_listesi.py         # MAHSUP fişi parse
├── excel_oku.py           # Excel fatura/cetvel okuma
├── cetvel.py              # KDV cetvel parse
├── ocr.py                 # OCR desteği
├── iade_ayristirici.py    # İade faturası ayrıştırma
├── oran_kontrol.py        # KDV oranı tutarlılık denetimi
├── beyanname.py           # 2 Beyanname karşılaştırma
├── ozetler.py             # Satıcı özeti, KDV dağılımı, BA/Bs
├── report.py / report_pdf.py   # Excel / PDF rapor
├── dashboard.py           # Dashboard grafikleri
├── db.py                  # Veritabanı (kontrol geçmişi)
├── guncelleme.py          # Otomatik güncelleme
├── denetim.py             # Sistem denetim aracı (py -3 denetim.py)
├── calistir.bat           # Tek tıkla kurulum + çalıştırma
└── logo.ico / logo.png    # Uygulama logosu
```

---

## 🛠️ Teknik Detaylar

| Kaynak | Format | Açıklama |
|--------|--------|----------|
| e-Fatura | XML (UBL) | GİB onaylı e-fatura formatı |
| E-Fatura | PDF | Tek veya çok sayfalı |
| E-Arşiv | PDF | Bireysel faturalar |
| MAHSUP Fişi | PDF | Hesap bazlı kayıtlar |
| Fatura Listesi | Excel | VKN, matrah, KDV sütunları |
| KDV Cetveli | Excel | Kontrol cetveli formatı |
| Satış Muavini | Excel | Hesap bazlı satış kayıtları |

**KDV hesaplama:** Matrah = KDV × 100 / Oran · Toplam = Matrah + KDV · Oranlar: %1, %5, %10, %20

---

## 📞 İletişim

| Platform | Link |
|----------|------|
| 🐙 **GitHub** | [@ArdaEkiz0](https://github.com/ArdaEkiz0) |
| 🔗 **LinkedIn** | [Arda M. Ekiz](https://www.linkedin.com/in/arda-mehmet-ekiz-107640333/) |
| 📷 **Instagram** | [@ardaaekiz](https://www.instagram.com/ardaaekiz/) |
| 📧 **E-posta** | ardaekiz72@gmail.com |

---

## ⚖️ Lisans

[MIT License](LICENSE) © 2026 Arda M. Ekiz

---

<div align="center">

**Made with ❤️ by [Arda M. Ekiz](https://github.com/ArdaEkiz0)**

</div>
