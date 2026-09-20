# Güvenlik Politikası

## Desteklenen Sürümler

| Sürüm | Destekleniyor |
|-------|--------------|
| En son sürüm | ✅ |

## Güvenlik Açığı Bildirme

Eğer bu projede bir güvenlik açığı bulursanız, lütfen doğrudan GitHub Security Advisory üzerinden bildirin:

**https://github.com/ArdaEkiz0/kdv-capraz-kontrol/security/advisories/new**

Lütfen şunları ekleyin:
- Açığın tanımı
- Tekrar üretme adımları
- Etkilenen sürümler
- Olası etki

Güvenlik açığı 96 saat içinde değerlendirilecektir.

## Güvenlik Uygulamaları

- Tüm bağımlılıklar `pip-audit` ile düzenli olarak taranır
- Depolama edilen şifreler Windows DPAPI ile şifrelenir
- PowerShell betikleri için özel kaçırtma (escape) fonksiyonları kullanılır
- ZIP çıkarma işlemlerinde Zip Slip koruması aktiftir
