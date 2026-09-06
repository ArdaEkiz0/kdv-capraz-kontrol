# Katkıda Bulunma

KDV Çapraz Kontrol'e katkıda bulunduğunuz için teşekkürler! Aşağıdaki yönergeler
katkınızın hızlıca incelenip birleştirilmesine yardımcı olur.

## İlk Adımlar

1. Bu depoyu fork edin.
2. Katkınız için ayrı bir dal açın (`feature/x` veya `fix/y`).
3. Değişikliklerinizi yapın ve **mevcut testleri kırmadığınızdan** emin olun.
4. GitHub'a push edip main dalına bir **Pull Request** açın.

## Çalışma Dizini

- Kod öncelikle **İngilizce tanımlayıcı** kullanır; kullanıcıya görünen
  metinler Türkçe'dir.
- Muavin/cetvel/fatura formatları **müşteriye özgü** değişebildiği için yeni
  bir format tanıyorsanız bunu `excel_oku.py` içinde ayrı bir parser fonksiyonu
  olarak ekleyin ve `dosya.py` içindeki `cetvel_dosya_parse` zincirine bağlayın.
- Eşleştirme mantığıyla ilgili değişiklikler `matcher.py` içindedir; davranışı
  değiştiriyorsanız lütfen gerçek veri benzeri bir test senaryosu ekleyin.

## Testleri Çalıştırma

Windows + Python 3.12:

```cmd
py -3 -m py_compile *.py
py -3 test_akisi.py
py -3 test_html_parse.py
py -3 test_muavin_cikti.py
py -3 test_paralel_indirme.py
py -3 test_sorgula_regresyon.py
```

- `test_akisi.py` OCR içerdiği için Tesseract (Türkçe diliyle) gerekebilir;
  CI de aynı testi çalıştırır.
- Yeni bir parser ya da indirme davranışı eklerken beraberinde **birim test**
  getirmeniz beklenir (örn. `test_muavin_cikti.py`).

## Pull Request Kontrol Listesi

- [ ] Mevcut testler geçiyor mu?
- [ ] Yeni davranış için test eklendi mi?
- [ ] Görünür metinler Türkçe, kod tanımlayıcıları İngilizce mi?
- [ ] Sürüm artışı gerekli mi? (Yayına kadar `surum.py` + release notu
      beklenir; kod değişikliğiniz kullanıcıya görünür bir değişiklikse
      sürüm notu taslağını PR açıklamasına yazın.)

## Sorun Bildirme

Bir sorunla karşılaşırsanız **Issues** sekmesinden hata raporu açın:
- Adımları (neye tıkladınız, ne beklediniz, ne oldu)
- Ekran görüntüsü ve hata metni
- İlgili dosya formatından bir örnek (gizli bilgileri maskeleyerek)