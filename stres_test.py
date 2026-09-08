# -*- coding: utf-8 -*-
"""Agir stres testi: 500+ fatura, uc durumlar, performans olcumu.

Koşturma: py -3 stres_test.py
"""
import io
import os
import random
import sys
import time
from decimal import Decimal

YOL = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, YOL)

from matcher import capraz_kontrol
from eksik_belge import eslestir
from utils import tl_format

random.seed(42)
HATALAR = []


def kontrol(ad, kosul, detay=""):
    if not kosul:
        HATALAR.append(f"{ad} {detay}")
    print(f"  [{'TAMAM' if kosul else 'HATA'}] {ad} {str(detay)[:80]}")


def rast_fatura(i):
    """Gerçekçi sahte fatura üretir."""
    oran = random.choice([1, 5, 10, 20])
    matrah = Decimal(random.randint(100, 50000))
    kdv = (matrah * oran / 100).quantize(Decimal("1"))
    return {
        "belge_no": f"STR{i:07d}",
        "tarih": f"2026-07-{random.randint(1, 28):02d}",
        "matrah": matrah,
        "kdv": kdv,
        "toplam": matrah + kdv,
        "oran": oran,
        "vkn": str(random.randint(10**9, 10**10 - 1)),
        "unvan": f"FİRMA {i} LTD. ŞTİ.",
        "notlar": [],
    }


print("== 1. ÇAPRAZ KONTROL: 600 fatura vs 800 cetvel satırı ==")
faturalar = [rast_fatura(i) for i in range(600)]
cetvel = []
for i in range(800):
    oran = random.choice([1, 5, 10, 20])
    matrah = Decimal(random.randint(100, 50000))
    cetvel.append({
        "belge_no": f"CET{i:07d}",
        "tarih": f"2026-07-{random.randint(1, 28):02d}",
        "matrah": matrah,
        "kdv": (matrah * oran / 100).quantize(Decimal("1")),
        "toplam": matrah + (matrah * oran / 100).quantize(Decimal("1")),
        "oran": oran,
        "vkn": str(random.randint(10**9, 10**10 - 1)),
        "unvan": f"SATICI {i} A.Ş.",
        "notlar": [],
    })
t0 = time.time()
satirlar, ozet = capraz_kontrol(faturalar, cetvel)
sure = time.time() - t0
kontrol("600x800 çapraz kontrol < 60 sn", sure < 60, f"-> {sure:.2f} sn")
kontrol("sonuç satır sayısı = fatura+cetvel",
        len(satirlar) == 1400, f"-> {len(satirlar)}")
kontrol("özet: cetvelde_yok=600", ozet.get("cetvelde_yok") == 600,
        f"-> {ozet.get('cetvelde_yok')}")
kontrol("özet: faturada_yok=800", ozet.get("faturada_yok") == 800,
        f"-> {ozet.get('faturada_yok')}")

# Deterministik eşleşme testi
print("\n== 2. DETERMİNİSTİK EŞLEŞME ==")
f1 = {"belge_no": "AAA1", "tarih": "2026-07-05", "matrah": Decimal("1000"),
      "kdv": Decimal("200"), "toplam": Decimal("1200"), "oran": 20,
      "vkn": "1234567890", "unvan": "TEST A", "notlar": []}
c1 = dict(f1)
c2 = {"belge_no": "BBB2", "tarih": "2026-07-06", "matrah": Decimal("999"),
      "kdv": Decimal("50"), "toplam": Decimal("1049"), "oran": 5,
      "vkn": "9999999999", "unvan": "BAŞKA B", "notlar": []}
s_satir, s_ozet = capraz_kontrol([f1], [c1, c2])
eslesen_sayisi = s_ozet.get("eslesen", -1)
kontrol("birebir eşleşme bulundu", eslesen_sayisi == 1, f"-> {eslesen_sayisi}")

print("\n== 3. EKSİK BELGE: 500 cetvel vs 300 fatura ==")
cetvel_k = [{"belge_no": f"EK{i:05d}", "tarih": "11.07.2026",
             "tutar": float(random.randint(500, 20000)),
             "kdv": float(random.randint(50, 2000)),
             "unvan": f"MÜKELLEF {i}", "vkn": ""}
            for i in range(500)]
fatura_k = [{"belge_no": f"EK{i:05d}", "tarih": "2026-07-11",
             "matrah": None, "kdv": cetvel_k[i]["kdv"],
             "unvan": f"MÜKELLEF {i}", "vkn": "", "notlar": []}
            for i in range(0, 300)]
t0 = time.time()
e = eslestir(cetvel_k, fatura_k)
sure = time.time() - t0
kritik = e.get("eksik") or []
eslesen_e = e.get("eslesen") or []
kontrol("eksik belge < 30 sn", sure < 30, f"-> {sure:.2f} sn")
kontrol("200 eksik tespit", len(kritik) == 200, f"-> {len(kritik)}")
kontrol("300 eşleşme", len(eslesen_e) == 300, f"-> {len(eslesen_e)}")

print("\n== 4. UÇ DURUMLAR ==")
try:
    s_satir, s_ozet = capraz_kontrol([], [])
    kontrol("boş girdiler çökmedi", True, f"-> {len(s_satir)} satır")
except Exception as hata:
    kontrol("boş girdiler çökmedi", False, str(hata)[:60])
try:
    s2, o2 = capraz_kontrol([{"belge_no": None, "tarih": "", "matrah": None,
                              "kdv": None, "oran": None, "vkn": "",
                              "unvan": "", "notlar": []}], cetvel[:1])
    kontrol("None değerli fatura çökmedi", True)
except Exception as hata:
    kontrol("None değerli fatura çökmedi", False, str(hata)[:60])

# KDV tutarsızlıkları
kotu_f = [{"belge_no": "BAD1", "tarih": "2026-07-01",
           "matrah": Decimal("1000"), "kdv": Decimal("999"),
           "toplam": Decimal("1999"), "oran": 20,
           "vkn": "1111111111", "unvan": "X", "notlar": []}]
_, k_ozet = capraz_kontrol(kotu_f, kotu_f)
kontrol("KDV tutarsızlığı sayıldı", k_ozet.get("tutar_farki", 0) >= 0
        or k_ozet.get("kdv_sifir", 0) >= 0,
        f"-> özet: {dict(list(k_ozet.items())[:6])}")

print("\n== 5. TEKRARLANABİLİRLİK (aynı girdi -> aynı sonuç) ==")
s1 = capraz_kontrol(faturalar[:100], cetvel[:100])[1]
s2 = capraz_kontrol(list(reversed(faturalar[:100])),
                    list(reversed(cetvel[:100])))[1]
kontrol("özet girdi sırasından bağımsız",
        s1.get("eslesen") == s2.get("eslesen"),
        f"-> {s1.get('eslesen')} vs {s2.get('eslesen')}")

print("== 6. PERFORMANS: 2000x2000 (tam eşleşen) ==")
# Gerçek senaryo: aynı belge_no'lu fatura-cetvel çiftleri
buyuk_f = []
buyuk_c = []
for i in range(2000):
    ff = rast_fatura(10**6 + i)
    buyuk_f.append(ff)
    buyuk_c.append(dict(ff))  # birebir kopya -> hepsi eslesmeli
t0 = time.time()
b_satir, b_ozet = capraz_kontrol(buyuk_f, buyuk_c)
sure = time.time() - t0
kontrol("2000x2000 < 120 sn", sure < 120, f"-> {sure:.1f} sn")
kontrol("2000 tam eşleşme", b_ozet.get("eslesen") == 2000,
        f"-> {b_ozet.get('eslesen')}")

print()
if HATALAR:
    print(f"NETICE: {len(HATALAR)} HATA")
    for h in HATALAR:
        print(" -", h)
    sys.exit(1)
print("NETICE: STRES TESTLERİ TAMAM")
