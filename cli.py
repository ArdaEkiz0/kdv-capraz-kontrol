"""GUI'siz toplu KDV kontrol modu.

Kullanım:
    py -3 -X utf8 cli.py --fatura <klasör|dosya ...> --cetvel <klasör|dosya ...> [--cikti rapor.xlsx] [--donem YYYY-MM]

Örnek:
    py -3 -X utf8 cli.py --fatura C:\\faturalar --cetvel 191.xlsx 391.xlsx --cikti rapor.xlsx
"""
import argparse
import os
import sys

from dosya import cetvel_dosya_parse, fatura_birlestir, fatura_dosya_parse
from matcher import (DURUM_CETVELDE_YOK, DURUM_FATURADA_YOK,
                     DURUM_TUTAR_FARKI, DURUM_VKN_FARKI,
                     capraz_kontrol_iade_destekli)
from report import rapor_olustur
from utils import tl_format

FATURA_UZANTILARI = (".xml", ".zip", ".xlsx", ".xlsm", ".xls", ".pdf")
CETVEL_UZANTILARI = (".xlsx", ".xlsm", ".xls", ".pdf", ".txt")


def _dosyalari_topla(yollar, uzantilar):
    """Yol listesindeki klasörleri alt klasörlerle birlikte dosyalara açar."""
    dosyalar = []
    for yol in yollar:
        if os.path.isdir(yol):
            for kok, _, adlar in os.walk(yol):
                for ad in sorted(adlar):
                    if ad.lower().endswith(uzantilar):
                        dosyalar.append(os.path.join(kok, ad))
        elif os.path.isfile(yol):
            dosyalar.append(yol)
        else:
            print(f"[Uyarı] Bulunamadı: {yol}")
    return dosyalar


def _ozet_yaz(ozet):
    print("\n=== ÖZET ===")
    print(f"Fatura sayısı      : {ozet.get('fatura_adet', 0)}")
    print(f"Cetvel kaydı       : {ozet.get('cetvel_adet', 0)}")
    print(f"Eşleşen            : {ozet.get('eslesen', 0)}")
    print(f"Tutar farkı        : {ozet.get('tutar_farki', 0)}")
    print(f"VKN farkı          : {ozet.get('vkn_farki', 0)}")
    print(f"Muavinde yok       : {ozet.get('cetvelde_yok', 0)}")
    print(f"Faturalarda yok    : {ozet.get('faturada_yok', 0)}")
    print(f"Mükerrer           : {ozet.get('mukerrer', 0)}")
    print(f"Okunamayan         : {ozet.get('parse_sorunu', 0)}")
    if ozet.get("tevkifatli"):
        print(f"Tevkifatlı         : {ozet['tevkifatli']}")
    if ozet.get("indirimli"):
        print(f"İndirimli          : {ozet['indirimli']}")


def _sorunlari_yaz(satirlar, sinir=30):
    sorunlar = [s for s in satirlar if s.get("durum") in (
        DURUM_TUTAR_FARKI, DURUM_VKN_FARKI, DURUM_CETVELDE_YOK, DURUM_FATURADA_YOK)]
    if not sorunlar:
        return
    print(f"\n=== SORUNLU KAYITLAR ({len(sorunlar)}) ===")
    for s in sorunlar[:sinir]:
        kdv = tl_format(s["kdv"]) if s.get("kdv") else "-"
        print(f"[{s['durum']}] {s.get('belge_no') or '?'} | {s.get('tarih') or '?'} "
              f"| {kdv} | {(s.get('unvan') or '')[:40]}")
        if s.get("detay"):
            print(f"    {s['detay'][:120]}")
    if len(sorunlar) > sinir:
        print(f"... ve {len(sorunlar) - sinir} kayıt daha (rapora bakın)")


def main(argv=None):
    cozucu = argparse.ArgumentParser(
        description="KDV Çapraz Kontrol - komut satırı modu")
    cozucu.add_argument("--fatura", nargs="+", required=True,
                        help="Fatura XML/PDF/ZIP/Excel dosya veya klasörleri")
    cozucu.add_argument("--cetvel", nargs="+", required=True,
                        help="191/391 defter veya cetvel dosya/klasörleri")
    cozucu.add_argument("--cikti", help="Excel rapor çıktı yolu (isteğe bağlı)")
    cozucu.add_argument("--donem", help="Sadece bu dönem (YYYY-MM), örn. 2026-07")
    argumanlar = cozucu.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    fatura_yollari = _dosyalari_topla(argumanlar.fatura, FATURA_UZANTILARI)
    cetvel_yollari = _dosyalari_topla(argumanlar.cetvel, CETVEL_UZANTILARI)
    if not fatura_yollari and not cetvel_yollari:
        print("[Hata] Okunacak dosya bulunamadı.")
        return 1

    faturalar = []
    for i, yol in enumerate(fatura_yollari, 1):
        print(f"[{i}/{len(fatura_yollari)}] Fatura: {os.path.basename(yol)}")
        try:
            faturalar.extend(fatura_dosya_parse(yol))
        except Exception as hata:
            print(f"  [Hata] {hata}")
    faturalar = fatura_birlestir(faturalar)

    cetvel_kayitlari = []
    for i, yol in enumerate(cetvel_yollari, 1):
        print(f"[{i}/{len(cetvel_yollari)}] Cetvel: {os.path.basename(yol)}")
        try:
            c = cetvel_dosya_parse(yol)
            cetvel_kayitlari.extend(c["kayitlar"])
            for n in c["notlar"]:
                print(f"  [Cetvel] {n}")
        except Exception as hata:
            print(f"  [Hata] {hata}")

    if not faturalar and not cetvel_kayitlari:
        print("[Hata] Hiç kayıt okunamadı.")
        return 1

    donem_not = ""
    if argumanlar.donem:
        faturalar = [f for f in faturalar if (f.get("tarih") or "")[:7] == argumanlar.donem]
        cetvel_kayitlari = [c for c in cetvel_kayitlari
                            if (c.get("tarih") or "")[:7] == argumanlar.donem]
        donem_not = f" (dönem {argumanlar.donem})"
    print(f"\nKontrol ediliyor{donem_not}: {len(faturalar)} fatura, "
          f"{len(cetvel_kayitlari)} cetvel kaydı...")

    satirlar, ozet = capraz_kontrol_iade_destekli(faturalar, cetvel_kayitlari)
    _ozet_yaz(ozet)
    _sorunlari_yaz(satirlar)

    if argumanlar.cikti:
        rapor_olustur(satirlar, ozet, faturalar, cetvel_kayitlari, argumanlar.cikti)
        print(f"\nRapor kaydedildi: {argumanlar.cikti}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
