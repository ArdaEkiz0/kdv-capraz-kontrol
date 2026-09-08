# Değişiklik Günlüğü

## [3.2.0] - 2026-09-08

### Yeni
- **`duzeltmeler.py`** — e-Fatura metin düzeltmeleri, gürültü desenleri ve KDV kuralları modülü (phobo3s'in issue #1 önerisiyle)
  - Düzeltme sözlüğü: Türkçe karakter, firma adı, para birimi hatalarını otomatik düzeltir
  - Gürültü desenleri: TCKN, ETTN, KDV özeti, POS satırlarını tespit eder
  - KDV kuralları: Matrah × Oran = KDV, tevkifat oranı, matrah + KDV = toplam kontrolleri
- **`pyproject.toml`** — Modern Python paketleme yapılandırması
- **`tests/`** — pytest ile kapsamlı test suitleri
  - `test_duzeltmeler.py` — duzeltmeler.py için 14 test
  - `test_matcher.py` — matcher.py için 16 test
  - `test_utils.py` — utils.py için 20 test
  - `test_db.py` — db.py için 6 test
  - `test_kurallar.py` — kurallar.py için 9 test
  - `test_config.py` — config.py için 5 test

### İyileştirmeler
- **`matcher.py`** — Type hints eklendi (`vkn_uyumlu`, `tutarlar_uyumlu` vb.)
- **`db.py`** — Type hints ve docstring'ler geliştirildi
- **`utils.py`** — Yeni yardımcı fonksiyonlar:
  - `donem_adi()` — Dönem adını Türkçe olarak döndürür
  - `sayiyi_bol()` — Tutarları eşit parçalara böler
  - `yuzde_hesapla()` — Yüzdelik oran hesaplar
  - `guvenli_decimal()` — Güvenli Decimal dönüşümü
  - `tarihleri_karsilastir()` — Tarih farkı hesaplama
  - `belge_no_normallestir()` — Belge numarası normalleştirme
- **`gib_api.py`** — Retry mekanizması eklendi
  - Exponential backoff ile 3 deneme hakkı
  - 429/5xx hatalarında otomatik bekleme ve tekrar deneme
  - Daha detaylı logging
- **`config.py`** — Gelişmiş ayar yönetimi
  - Varsayılan ayarlar sözlüğü
  - `ayar_al()` — Tek ayar okuma
  - `ayar_guncelle()` — Toplu ayar güncelleme
  - Eksik anahtar otomatik tamamlama

### Altyapı
- `requirements.txt` oluşturuldu
- CI/CD: test.yml GitHub Actions yapılandırması mevcut
- `.gitignore` güncellendi

---

## [3.1.46] - 2026-09-08

### Yeni
- `duzeltmeler.py` modülü eklendi (phobo3s izniyle)
  - Düzeltme sözlüğü, gürültü desenleri, KDV kuralları
  - `luca_cekme.py`'ye import eklendi (graceful fallback ile)

---

## [3.1.45] - 2026-09-06

### Düzeltmeler
- Luca muavininde kök neden düzeltildi
- Üst menü çerçevesindeki dönem tarihleri artık sahte "rapor dolu" sinyali üretmiyor
- Rapor gövdesi taraması üst menüyü dışlıyor
- HTML kaydı düzeltildi
- Teşhis dump'ı export aramasından önce yazılıyor

---

## [3.1.44] - 2026-09-06

### Düzeltmeler
- Luca muavininde rapor çerçevesinin HTML'i veri göründüğü an hemen diske yazılıyor

---

## [3.1.43] - 2026-09-06

### Düzeltmeler
- Luca muavininde ikinci hesap (391) bayat rapor yüzünden çekilemiyordu
- Rapor gövdesinde hesap kodu doğrulanıyor
- Eski rapor pencereleri kapatılıyor
- Bekleme süreleri kısaltıldı

---

## [3.1.42] - 2026-09-06

### Düzeltmeler
- Luca muavininde doğrudan Excel indirme + tam teşhis dökümü
- `_rapor_turu_excel_sec` fonksiyonu eklendi
- Export desenleri genişletildi
- `_luca_diag_dump` yeniden yapılandırıldı
