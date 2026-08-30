# -*- coding: utf-8 -*-
"""Şule Çatal faturalarını Luca'dan çeker (captcha kullanıcı tarafından girilir)."""
import os
import sys
import traceback

YOL = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, YOL)

import mukellefler
import luca_cekme
from datetime import date

LOG = os.path.join(os.environ.get("TEMP", "."), "sule_cekme.log")


def logla(metin):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(metin + "\n")
    print(metin, flush=True)


def main():
    veri = mukellefler.yukle()
    kayit = None
    for m in veri:
        if "SULE" in (m.get("ad") or "").upper() or "ÇATAL" in (m.get("ad") or "").upper():
            kayit = mukellefler.coz_ve_getir(m)
            break
    if kayit is None:
        logla("HATA: Şule ÇATAL kaydı bulunamadı")
        return 1

    logla(f"ŞULE ÇATAL çekimi başlıyor... (üye {kayit.get('luca_uye')})")
    kimlik = kayit.get("vkn") or kayit.get("gib_tc") or "sule_catal"
    hedef = mukellefler.coz_klasor(kimlik, 2026, 8)
    os.makedirs(hedef, exist_ok=True)
    logla(f"Hedef klasör: {hedef}")

    bas = date(2026, 8, 1)
    bit = date(2026, 8, 31)

    # Muavin önce
    try:
        logla("Muavin (191/391) çekiliyor...")
        muavinler = luca_cekme.cek_muavin(
            kayit["luca_uye"], kayit["ent_kullanici"], kayit["ent_sifre"],
            bas, bit, hedef, firma_adi=kayit.get("ad", ""),
            ilerleme=logla)
        logla(f"Muavin tamam: {len(muavinler)} dosya")
    except luca_cekme.LucaHata as h:
        logla(f"Muavin hatası: {h}")
        return 1

    # 4'lü e-belge grubu
    try:
        logla("e-Belgeler (4 grup) çekiliyor...")
        sonuc = luca_cekme.cek_luca_belgeleri(
            kayit["luca_uye"], kayit["ent_kullanici"], kayit["ent_sifre"],
            bas, bit, hedef,
            kategoriler=("earsiv_alis", "earsiv_satis",
                         "efatura_alis", "efatura_satis"),
            ilerleme=logla, firma_adi=kayit.get("ad", ""), duz_yaz=True)
        for k, v in (sonuc or {}).items():
            logla(f"  {k}: {v.get('belge_sayisi', 0)} belge")
        logla("e-Belge çekimi tamam.")
    except luca_cekme.LucaHata as h:
        logla(f"e-Belge hatası: {h}")
        return 1

    logla("TAMAM: ŞULE ÇATAL Ağustos 2026 çekimi bitti.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("BEKLENMEDIK HATA:\n" + traceback.format_exc())
        raise