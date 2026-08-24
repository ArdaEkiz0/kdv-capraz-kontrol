"""Cetvel kayıtları ile fatura listesi arasında esnek eşleştirme.

Muavin (191/391) satırları ile GİB'den indirilen e-Arşiv faturalarını
belge numarası, VKN, unvan benzerliği ve tutar üzerinden eşleştirir;
faturasız kalan cetvel kayıtlarını ayıklar.
"""
import re

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


def _tutar_esit(a, b):
    if a is None or b is None:
        return False
    fark = abs(abs(float(a)) - abs(float(b)))
    olcek = max(abs(float(a)), abs(float(b)), 1.0)
    return fark <= TOLERANS or fark / olcek <= 0.01


def _ay(tarih):
    return str(tarih or "")[:7]


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

    for i in sorted(c_kalan):
        c = cetvel_kayitlari[i]
        ct = str(c.get("tarih") or "")
        cv = (c.get("vkn") or "").strip()
        tam_adaylar, vkn_adaylar, puanlar = [], [], []
        for j in list(f_kalan):
            f = fatura_kayitlari[j]
            ft = str(f.get("tarih") or "")
            fv = (f.get("satici_vkn") or "").strip()
            tutar_ok = _tutar_esit(c.get("kdv"), f.get("kdv"))
            if tutar_ok and ct and ct == ft:
                tam_adaylar.append(j)
            if tutar_ok and len(cv) >= 10 and cv == fv:
                vkn_adaylar.append(j)
            puan = 0
            benzerlik = _unvan_benzer(c.get("unvan"), f.get("unvan"))
            if benzerlik >= 0.5:
                puan += 2
            elif benzerlik >= 0.34:
                puan += 1
            if len(cv) >= 10 and cv == fv:
                puan += 4
            if tutar_ok:
                puan += 3
            if ct and ft:
                if ct[:7] == ft[:7]:
                    puan += 1
                    if ct == ft:
                        puan += 1
                else:
                    puan -= 2
            if puan >= 4:
                puanlar.append((puan, j))
        if len(tam_adaylar) == 1:
            j = tam_adaylar[0]
            eslesen.append((i, j, "tutar+tarih"))
            c_kalan.discard(i)
            f_kalan.discard(j)
            continue
        if not tam_adaylar and len(vkn_adaylar) == 1:
            j = vkn_adaylar[0]
            eslesen.append((i, j, "vkn+tutar"))
            c_kalan.discard(i)
            f_kalan.discard(j)
            continue
        if not puanlar:
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
            adaylar = [(j, p) for p, j in puanlar[:3]]
            belirsiz.append((i, adaylar))
            c_kalan.discard(i)

    return {
        "eslesen": eslesen,
        "belirsiz": belirsiz,
        "eksik": sorted(c_kalan),
        "fazla": sorted(f_kalan),
    }
