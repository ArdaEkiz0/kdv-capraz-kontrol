"""Cetvel kayıtları ile fatura listesi arasında esnek eşleştirme.

Muavin (191/391) satırları ile GİB'den indirilen e-Arşiv faturalarını
belge numarası, VKN, unvan benzerliği ve tutar üzerinden eşleştirir;
faturasız kalan cetvel kayıtlarını ayıklar.

Eşleştirme sırası: belge no -> tutar+tam tarih -> VKN+tutar ->
puanlama (unvan benzerligi + tarih yakınlığı). Tüm kesin yollar
tutar eşleşmesi gerektirir; işaret farkı (iade/gider pusulası
karışması) asla eşleştirmez.
"""
import re
from bisect import bisect_left, bisect_right

TOLERANS = 0.02

_TURKCE = str.maketrans("ığüşöçİĞÜŞÖÇ", "igusocIGUSOC")


def _metin_norm(metin):
    metin = str(metin or "").upper().translate(_TURKCE)
    return re.sub(r"[^A-Z0-9 ]+", " ", metin)


def _tokenler(unvan):
    return {t for t in _metin_norm(unvan).split() if len(t) > 1}


def _unvan_benzer(a, b):
    ta, tb = _tokenler(a), _tokenler(b)
    if not ta or not tb:
        return 0.0
    ortak = len(ta & tb)
    return ortak / min(len(ta), len(tb))


def _sayi(deger):
    try:
        return float(deger)
    except (TypeError, ValueError):
        return None


def _anlamli_tutar(v):
    s = _sayi(v)
    return s is not None and s != 0


_TARIH_DESEN = re.compile(r"^(\d{1,2})[./](\d{1,2})[./](\d{2}|\d{4})$")


def _tarih_norm(metin):
    """ISO'yu olduğu gibi bırakır, GG.AA.YYYY/GG.AA.YY -> YYYY-AA-GG,
    anlaşılmayanı None döndürür."""
    metin = str(metin or "").strip()
    if not metin:
        return None
    m = _TARIH_DESEN.match(metin)
    if m:
        gun, ay, yil = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if yil < 100:
            yil += 2000
        if 1 <= ay <= 12 and 1 <= gun <= 31:
            return f"{yil:04d}-{ay:02d}-{gun:02d}"
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}", metin):
        return metin[:10]
    return None


def _tutar_esit(a, b):
    fa, fb = _sayi(a), _sayi(b)
    if fa is None or fb is None:
        return False
    if fa == 0 or fb == 0:
        return abs(fa - fb) <= TOLERANS
    if (fa > 0) != (fb > 0):
        return False
    fark = abs(fa - fb)
    olcek = max(abs(fa), abs(fb), 1.0)
    return fark <= TOLERANS or fark / olcek <= 0.01


def _kdv_pencere_siniri(v):
    return abs(v) * 0.01 + TOLERANS + 0.001


def eslestir(cetvel_kayitlari, fatura_kayitlari):
    """Dönen sözlük:
      eslesen: [(c_i, f_i, yontem)]
      belirsiz: [(c_i, [(f_i, puan), ...])]
      eksik:   [c_i]   cetvelde var, faturası yok
      fazla:   [f_i]   faturada var, cetvelde yok
    """
    n_c, n_f = len(cetvel_kayitlari), len(fatura_kayitlari)
    eslesen = []
    belirsiz = []
    c_kalan = set(range(n_c))
    f_kalan = set(range(n_f))

    # Belge numarasi dogrudan eslesme
    belge_f = {}
    for j in range(n_f):
        ana = (fatura_kayitlari[j].get("belge_no") or "").strip().upper()
        if ana:
            belge_f.setdefault(ana, []).append(j)
    for i in range(n_c):
        ana = (cetvel_kayitlari[i].get("belge_no") or "").strip().upper()
        adaylar = belge_f.get(ana) if ana else None
        if not adaylar:
            continue
        uygun = [j for j in adaylar if j in f_kalan]
        if len(uygun) == 1:
            eslesen.append((i, uygun[0], "belge no"))
            c_kalan.discard(i)
            f_kalan.discard(uygun[0])

    # KDV kovasi: sadece tutari uyumlu faturalar adaydir
    degerler = []
    kova = {}
    for j in range(n_f):
        v = _sayi(fatura_kayitlari[j].get("kdv"))
        if v is None:
            continue
        anahtar = round(v, 2)
        if anahtar not in kova:
            kova[anahtar] = []
            degerler.append(anahtar)
        kova[anahtar].append(j)
    degerler.sort()

    def aday_bul(v):
        fv = _sayi(v)
        if fv is None:
            return []
        sinir = _kdv_pencere_siniri(fv)
        lo = bisect_left(degerler, fv - sinir)
        hi = bisect_right(degerler, fv + sinir)
        sonuc = []
        for d in degerler[lo:hi]:
            for j in kova[d]:
                if j in f_kalan and _tutar_esit(fv, d):
                    sonuc.append(j)
        return sonuc

    # FAZ A: dogrudan kanitli talepler once toplanir, cakismalar
    # sonra cozulur (erken zayif esnek iddia guclu talebi calamaz)
    talep = {}           # i -> (j, yontem)
    belirsiz_bilgi = {}  # i -> adaylar listesi
    for i in sorted(c_kalan):
        c = cetvel_kayitlari[i]
        ct = _tarih_norm(c.get("tarih"))
        cv = (c.get("vkn") or "").strip()
        havuz = aday_bul(c.get("kdv"))
        tam_adaylar, vkn_adaylar = [], []
        for j in havuz:
            f = fatura_kayitlari[j]
            ft = _tarih_norm(f.get("tarih"))
            fv = (f.get("satici_vkn") or "").strip()
            if ct and ct == ft and _anlamli_tutar(c.get("kdv")):
                tam_adaylar.append(j)
            if len(cv) >= 10 and cv == fv and _anlamli_tutar(c.get("kdv")):
                vkn_adaylar.append(j)
        if len(tam_adaylar) == 1:
            talep[i] = (tam_adaylar[0], "tutar+tarih")
        elif not tam_adaylar and len(vkn_adaylar) == 1:
            talep[i] = (vkn_adaylar[0], "vkn+tutar")
        elif len(tam_adaylar) > 1 or len(vkn_adaylar) > 1:
            belirsiz_bilgi[i] = [(j, 9) for j in
                                 (tam_adaylar or vkn_adaylar)[:3]]

    hedef_sayisi = {}
    for i, (j, y) in talep.items():
        hedef_sayisi[j] = hedef_sayisi.get(j, 0) + 1
    for i, (j, y) in sorted(talep.items()):
        if hedef_sayisi[j] == 1 and j in f_kalan:
            eslesen.append((i, j, y))
            c_kalan.discard(i)
            f_kalan.discard(j)
        else:
            belirsiz_bilgi[i] = [(j, 9)]

    # FAZ B: kalan satirlarda esnek puanlama
    for i in sorted(c_kalan):
        if i in belirsiz_bilgi or i not in c_kalan:
            continue
        c = cetvel_kayitlari[i]
        ct = _tarih_norm(c.get("tarih"))
        cv = (c.get("vkn") or "").strip()
        puanlar = []
        for j in aday_bul(c.get("kdv")):
            f = fatura_kayitlari[j]
            ft = _tarih_norm(f.get("tarih"))
            fv = (f.get("satici_vkn") or "").strip()
            puan = 3
            benzerlik = _unvan_benzer(c.get("unvan"), f.get("unvan"))
            if benzerlik >= 0.5:
                puan += 2
            elif benzerlik >= 0.34:
                puan += 1
            if len(cv) >= 10 and cv == fv:
                puan += 4
            if ct and ft:
                if ct[:7] == ft[:7]:
                    puan += 1
                    if ct == ft:
                        puan += 1
                else:
                    puan -= 2
            if puan >= 3:
                puanlar.append((puan, j))
        if not puanlar:
            continue
        guclu_kanal = (_anlamli_tutar(c.get("kdv"))
                       or _unvan_benzer(c.get("unvan"),
                                        fatura_kayitlari[puanlar[0][1]]
                                        .get("unvan")) >= 0.5)
        if not guclu_kanal:
            belirsiz_bilgi[i] = [(j, p) for p, j in
                                 sorted(puanlar, reverse=True)[:3]]
            continue
        puanlar.sort(reverse=True)
        en_iyi = puanlar[0][0]
        liderler = [j for p, j in puanlar if p == en_iyi]
        if len(liderler) == 1 and en_iyi >= 5 and \
                (len(puanlar) == 1 or puanlar[1][0] <= en_iyi - 1):
            j = liderler[0]
            eslesen.append((i, j, "esnek"))
            c_kalan.discard(i)
            f_kalan.discard(j)
        else:
            belirsiz_bilgi[i] = [(j, p) for p, j in puanlar[:3]]

    belirsiz = [(i, belirsiz_bilgi[i]) for i in sorted(belirsiz_bilgi)]
    return {
        "eslesen": eslesen,
        "belirsiz": belirsiz,
        "eksik": sorted(c_kalan),
        "fazla": sorted(f_kalan),
    }
