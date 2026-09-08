# -*- coding: utf-8-sig -*-
"""Tum duzeltmeleri yapar."""
import re
import sys

# ============================================================
# GOREV 1: mukellef_panel.py - if/else girinti duzeltmesi
# ============================================================
def gorev1():
    with open('mukellef_panel.py', encoding='utf-8-sig') as f:
        satirlar = f.readlines()

    # Satir 463'te (0-indexed: 462) "# Luca hesabi yok: klasik GIB yolu." yorumu
    # ve 464-471 satirlari (0-indexed 463-470) else blogu olmali
    # Simdi satirlara bakalim
    hedef_yorum_idx = None
    for i, s in enumerate(satirlar):
        if '# Luca hesab' in s and 'yok' in s and 'klasik' in s:
            hedef_yorum_idx = i
            break

    if hedef_yorum_idx is None:
        print('GOREV 1: HATA - yorum satiri bulunamadi')
        return False

    # 4 satir once if luca_planli: olmali (veya yakin satirda else: olmali)
    # Simdi bu satirin girintisini inceleyelim
    yorum_satiri = satirlar[hedef_yorum_idx]
    girinti = len(yorum_satiri) - len(yorum_satiri.lstrip())

    # Bunun ustundeki satirlarda elif/else:  ya da if luca_planli: varsa
    # ve try: alttaysa - else: blogunun girintisini duzeltelim
    # try: satirini bul (hedef_yorum_idx+1)
    try_idx = hedef_yorum_idx + 1
    if try_idx < len(satirlar) and satirlar[try_idx].lstrip().startswith('try:'):
        # try girintisi
        try_girinti = len(satirlar[try_idx]) - len(satirlar[try_idx].lstrip())
        if try_girinti <= girinti:
            # Bu try/except blogu if luca_planli: blogu icinde
            # Duzeltme: yorum satirini ve try/except blogunu 'else:' ile degistir
            # once else: satirini ekle (ayni girinti ile)
            bosluk = ' ' * girinti
            satirlar[hedef_yorum_idx] = bosluk + 'else:\r\n'

            # try satirinin girintisini bir seviye artir (4 bosluk)
            # except blogu bitene kadar giden satirlar
            j = hedef_yorum_idx + 1
            while j < len(satirlar):
                s = satirlar[j]
                s_strip = s.lstrip()
                s_girinti = len(s) - len(s_strip)
                if s_strip == '' or s_strip == '\r\n' or s_strip == '\n':
                    break
                if s_girinti < girinti:
                    break
                satirlar[j] = '    ' + s
                j += 1

            with open('mukellef_panel.py', 'w', encoding='utf-8-sig', newline='') as f:
                f.writelines(satirlar)
            print('GOREV 1: OK - else blogu duzeltildi (yorum+girinti)')
            return True
        else:
            print(f'GOREV 1: try girintisi zaten farkli: yorum={girinti}, try={try_girinti}')
            return False
    else:
        print(f'GOREV 1: HATA - try bulunamadi, hedef_yorum_idx={hedef_yorum_idx}')
        return False


# ============================================================
# GOREV 2: luca_cekme.py - regex duzeltmeleri
# ============================================================
def gorev2():
    with open('luca_cekme.py', encoding='utf-8-sig') as f:
        icerik = f.read()

    degisiklik = 0

    # BUYUK_DESEN regex duzeltmesi
    eski1 = r'_BUYUK_DESEN = re.compile(\n    r"^\s*(t[u\xfc\xfcm][u\xfc]|hepsi|all|500|1000|2000)\s*$", re.IGNORECASE)'
    # Genel arama - re ile bul
    buyuk_desen_eski = re.search(
        r'_BUYUK_DESEN\s*=\s*re\.compile\(\s*\n?\s*r"[^"]*"\s*,\s*re\.IGNORECASE\)',
        icerik)
    if buyuk_desen_eski:
        yeni1 = '_BUYUK_DESEN = re.compile(\n    r"(?i)^\\s*(t.{0,2}m.{0,2}|hepsi|all|500|1000|2000)\\s*$")'
        icerik = icerik[:buyuk_desen_eski.start()] + yeni1 + icerik[buyuk_desen_eski.end():]
        degisiklik += 1
        print('GOREV 2a: OK - _BUYUK_DESEN duzeltildi')
    else:
        print('GOREV 2a: HATA - _BUYUK_DESEN bulunamadi')

    # _indir_butonu_tikla cagrisindaki regex (satir 2114-2116)
    eski2 = re.search(
        r'return _indir_butonu_tikla\(\s*\n\s*sayfa,\s*\(r"[^"]*",\s*\n?\s*r"[^"]*"\)',
        icerik)
    if eski2:
        yeni2 = ('return _indir_butonu_tikla(\n'
                 '            sayfa, (r"(?i)^\\s*(t.{0,2}m.{0,2}|500|1000|2000)\\s*$",\n'
                 '                    r"sat.r.say.s"))')
        icerik = icerik[:eski2.start()] + yeni2 + icerik[eski2.end():]
        degisiklik += 1
        print('GOREV 2b: OK - _indir_butonu_tikla regex duzeltildi')
    else:
        print('GOREV 2b: HATA - _indir_butonu_tikla satiri bulunamadi, elle kontrol et')

    if degisiklik > 0:
        with open('luca_cekme.py', 'w', encoding='utf-8-sig', newline='') as f:
            f.write(icerik)
    return degisiklik > 0


# ============================================================
# GOREV 3: luca_cekme.py - iptal_itiraz_durumu duzeltmesi
# ============================================================
def gorev3():
    with open('luca_cekme.py', encoding='utf-8-sig') as f:
        icerik = f.read()

    # Eski pattern
    eski = re.search(
        r'iptal_ibare\s*=\s*str\(belge\.get\("iptal_itiraz"\)\s*or\s*\n?\s*'
        r'belge\.get\("iptal_itiraz_durumu"\)\s*\n?\s*or\s*""\)\.strip\(\)',
        icerik)
    if eski:
        girinti = '                        '  # satir girintisi
        yeni = (
            'iptal_ibare_raw = str(belge.get("iptal_itiraz") or\n'
            + girinti + '                      belge.get("iptal_itiraz_durumu") or "").strip()\n'
            + girinti + '# "0", "false", "hayir" = iptal degil\n'
            + girinti + 'iptal_ibare = "" if iptal_ibare_raw.lower() in ("", "0", "false", "hayir", "yok") else iptal_ibare_raw'
        )
        icerik = icerik[:eski.start()] + yeni + icerik[eski.end():]
        with open('luca_cekme.py', 'w', encoding='utf-8-sig', newline='') as f:
            f.write(icerik)
        print('GOREV 3: OK - iptal_itiraz_durumu duzeltildi')
        return True
    else:
        print('GOREV 3: HATA - iptal_itiraz pattern bulunamadi')
        return False


# ============================================================
# GOREV 4: luca_cekme.py - _gib530_frame hata loglama
# ============================================================
def gorev4():
    with open('luca_cekme.py', encoding='utf-8-sig') as f:
        icerik = f.read()

    # Son kisim: "bildir("gib530 frame yuklenemedi.")\n    return None"
    eski = re.search(
        r'bildir\("gib530 frame y\xfcklenemedi\."\)\s*\r?\n\s*return None',
        icerik)
    if eski:
        # Girintiyi bul
        onceki = icerik[:eski.start()].splitlines()
        girinti = '    '  # fonksiyon icinde

        yeni = (
            'bildir("gib530 frame yuklenemedi.")\n'
            '    if bildir is not None:\n'
            '        try:\n'
            '            nerede = erp.evaluate(\n'
            '                "top.frames[\'frm3\'] "\n'
            '                "? top.frames[\'frm3\'].location.href : \'frm3 yok\'")\n'
            '            bildir(f"frm3 durumu: {str(nerede)[:100]}")\n'
            '        except Exception:\n'
            '            pass\n'
            '        # Ek: tum frame URL\'lerini logla\n'
            '        try:\n'
            '            frame_urls = [f.url for f in erp.frames if f.url]\n'
            '            bildir(f"Mevcut frame\'ler ({len(frame_urls)}): " + ", ".join(frame_urls[:5]))\n'
            '        except Exception:\n'
            '            pass\n'
            '    return None'
        )
        icerik = icerik[:eski.start()] + yeni + icerik[eski.end():]
        with open('luca_cekme.py', 'w', encoding='utf-8-sig', newline='') as f:
            f.write(icerik)
        print('GOREV 4: OK - _gib530_frame hata loglama eklendi')
        return True
    else:
        print('GOREV 4: HATA - bildir("gib530 frame yuklenemedi") bulunamadi')
        # Alternatif arama
        with open('luca_cekme.py', encoding='utf-8-sig') as f:
            satirlar = f.readlines()
        for i, s in enumerate(satirlar, 1):
            if 'frame' in s.lower() and ('yuklenemedi' in s or 'y\xfcklenemedi' in s):
                print(f'  {i}: {repr(s[:80])}')
        return False


# ============================================================
# GOREV 5: excel_oku.py - luca_ozet_xlsx_parse ekle
# ============================================================
def gorev5():
    with open('excel_oku.py', encoding='utf-8-sig') as f:
        icerik = f.read()

    # fatura_luca_ozet_parse var mi ve yeterli mi?
    if 'fatura_luca_ozet_parse' in icerik:
        print('GOREV 5: fatura_luca_ozet_parse zaten mevcut - luca_ozet_xlsx_parse wrapper ekleniyor')
        # luca_ozet_xlsx_parse var mi?
        if 'luca_ozet_xlsx_parse' in icerik:
            print('GOREV 5: luca_ozet_xlsx_parse zaten mevcut - dokunulmadi')
            return True
        # Wrapper ekle: dosyanin sonuna
        wrapper = '''

def luca_ozet_xlsx_parse(dosya_yolu):
    """Luca ozet xlsx dosyasini parse eder.

    luca_cekme.py tarafindan uretilen ozet tablolarini okur:
    belge_numarasi, belge_tarihi, karsi_vkn, matrah, kdv_toplam kolonlari.
    Baslik satiri otomatik tespit edilir.

    Her satirdan {belge_no, tarih, vkn, matrah, kdv, tutar, tip, kaynak: 'luca'}
    dondurulen sozlukler listesi.
    """
    from utils import fatura_no_temizle, tarih_parse, tutar_parse, vkn_temizle

    # Once fatura_luca_ozet_parse dene (daha zengin format)
    sonuc = fatura_luca_ozet_parse(dosya_yolu)
    if sonuc is not None:
        # Sonuclara kaynak='luca' ekle
        for kayit in sonuc:
            kayit.setdefault('kaynak', 'luca')
            kayit.setdefault('tutar', kayit.get('toplam'))
        return sonuc

    # Alternatif: sade Luca ozet formati (belge_no, tarih, vkn, matrah, kdv)
    satirlar = excel_satirlar(dosya_yolu)
    baslik_i = None
    kolon = {}
    LUCA_OZET_ALANLARI = {
        'belge': ['BELGE NO', 'BELGE NUMARASI', 'BELGE_NUMARASI', 'FATURA NO'],
        'tarih': ['TARIH', 'BELGE TARIHI', 'BELGE_TARIHI', 'FATURA TARIHI'],
        'vkn':   ['VKN', 'KARSI VKN', 'KARSI_VKN', 'VERGI NO', 'TCKN'],
        'matrah':['MATRAH', 'KDV MATRAHI', 'KDV HARIC TUTAR'],
        'kdv':   ['KDV', 'KDV TUTARI', 'KDV TOPLAM', 'KDV_TOPLAM', 'HESAPLANAN KDV'],
        'tutar': ['GENEL TOPLAM', 'TOPLAM', 'FATURA TOPLAMI'],
    }

    def norm(d):
        if d is None:
            return ''
        metin = str(d).upper()
        for k, v in {'I': 'I', 'I': 'I', 'G': 'G', 'U': 'U', 'S': 'S', 'O': 'O', 'C': 'C'}.items():
            pass
        tr = {'\\u0130': 'I', '\\u011e': 'G', '\\xdc': 'U', '\\u015e': 'S',
               '\\xd6': 'O', '\\xc7': 'C', '\\u0131': 'I', '\\u011f': 'G',
               '\\xfc': 'U', '\\u015f': 'S', '\\xf6': 'O', '\\xe7': 'C'}
        for k, v in tr.items():
            metin = metin.replace(k, v)
        return ' '.join(''.join(c if c.isalnum() else ' ' for c in metin).split())

    for i, satir in enumerate(satirlar):
        normlar = [norm(c) for c in satir]
        eslesen = 0
        gecici_kolon = {}
        for alan, adaylar in LUCA_OZET_ALANLARI.items():
            for j, n in enumerate(normlar):
                if any(n == norm(a) or n.startswith(norm(a)) for a in adaylar):
                    gecici_kolon[alan] = j
                    eslesen += 1
                    break
        if eslesen >= 3 and 'belge' in gecici_kolon:
            baslik_i = i
            kolon = gecici_kolon
            break

    if baslik_i is None:
        return None

    sonuc = []
    for i in range(baslik_i + 1, len(satirlar)):
        satir = satirlar[i]
        if not any(c is not None and str(c).strip() for c in satir):
            continue
        belge_ham = satir[kolon['belge']] if kolon.get('belge') is not None and kolon['belge'] < len(satir) else None
        if belge_ham is None or not str(belge_ham).strip():
            continue
        def h(alan):
            j = kolon.get(alan)
            if j is None or j >= len(satir):
                return None
            return satir[j]
        tarih_val = h('tarih')
        t = tarih_parse(str(tarih_val).strip()) if tarih_val else None
        kayit = {
            'belge_no': fatura_no_temizle(str(belge_ham)),
            'tarih': str(t) if t else None,
            'vkn': vkn_temizle(str(h('vkn') or '')),
            'matrah': tutar_parse(h('matrah')),
            'kdv': tutar_parse(h('kdv')),
            'tutar': tutar_parse(h('tutar')),
            'tip': 'luca_ozet',
            'kaynak': 'luca',
            'dosya': dosya_yolu,
            'satir': i + 1,
        }
        sonuc.append(kayit)

    return sonuc if sonuc else None
'''
        icerik = icerik.rstrip() + '\n' + wrapper + '\n'
        with open('excel_oku.py', 'w', encoding='utf-8-sig', newline='') as f:
            f.write(icerik)
        print('GOREV 5: OK - luca_ozet_xlsx_parse eklendi')
        return True
    else:
        print('GOREV 5: fatura_luca_ozet_parse yok! Baslik bazli parse ekleniyor...')
        return False


if __name__ == '__main__':
    print('=== GOREV 1 ===')
    gorev1()
    print()
    print('=== GOREV 2 ===')
    gorev2()
    print()
    print('=== GOREV 3 ===')
    gorev3()
    print()
    print('=== GOREV 4 ===')
    gorev4()
    print()
    print('=== GOREV 5 ===')
    gorev5()
    print()
    print('Tum gorevler tamamlandi.')
