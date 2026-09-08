"""GIB e-Arsiv Portali REST istemcisi.

Tarayici otomasyonuna gerek birakmadan kullanici kodu + sifre ile giris yapip
adima duzenlenen (alis) ve duzenlenen (satis) e-Arsiv belge listelerini getirir.

Not: Liste kayitlari tutar icermez; tutarli Excel ciktisi icin
gib_cekme.cek_e_arsiv_alis kullanilir. Bu modul o akisin hizli on-dogrulama
ve sayim katmanidir.

v3.2.0: Retry mekanizması, timeout geliştirme, daha iyi hata yönetimi.
"""
from __future__ import annotations

import json
import logging
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

logger = logging.getLogger(__name__)

TEMEL_ADRES = "https://earsivportal.efatura.gov.tr"
GIRIS_ADRESI = TEMEL_ADRES + "/earsiv-services/assos-login"
SORGU_ADRESI = TEMEL_ADRES + "/earsiv-services/dispatch"

_ALIS_KOMUTU = "EARSIV_PORTAL_ADIMA_KESILEN_BELGELERI_GETIR"
_ALIS_SAYFA = "RG_ALICI_TASLAKLAR"
_SATIS_KOMUTU = "EARSIV_PORTAL_TASLAKLARI_GETIR"
_SATIS_SAYFA = "R_G_BASITTASLAKLAR"

# Retry ayarları
MAX_DENEME = 3
BEKLEME_SURESI = [1, 2, 4]  # saniye cinsinden exponential backoff


class GibApiHata(Exception):
    """GIB e-Arsiv REST cagrisinda olusan hata."""


def _oturum_doldu_mu(metin):
    metin = str(metin).lower()
    return "oturum" in metin or "zamana" in metin


def _sayac_sifirla():
    return [0]


def _isteg_yap(adres: str, govde: str, yonlendirme: str,
               zaman_asimi: int = 45, max_deneme: int = MAX_DENEME) -> Any:
    """GİB'e HTTP isteği yapar; hatalarda retry uygular."""
    son_hata = None
    for deneme in range(1, max_deneme + 1):
        istek = urllib.request.Request(
            adres,
            data=govde.encode("utf-8"),
            headers={
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "Referer": yonlendirme,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            },
        )
        try:
            yanit = urllib.request.urlopen(istek, timeout=zaman_asimi)
            return json.loads(yanit.read().decode("utf-8"))
        except urllib.error.HTTPError as hata:
            detay = ""
            try:
                detay = hata.read().decode("utf-8", "replace")[:200]
            except Exception:
                pass
            son_hata = GibApiHata("GIB sunucusu %s dondu. %s" % (hata.code, detay))
            # 429 Too Many Requests veya 5xx sunucu hatası -> bekle ve tekrar dene
            if hata.code in (429, 500, 502, 503, 504) and deneme < max_deneme:
                bekleme = BEKLEME_SURESI[min(deneme - 1, len(BEKLEME_SURESI) - 1)]
                logger.warning("GİB %s hatası, %s sn bekleniyor... (deneme %s/%s)",
                               hata.code, bekleme, deneme, max_deneme)
                time.sleep(bekleme)
                continue
            raise son_hata
        except (urllib.error.URLError, TimeoutError, OSError) as hata:
            son_hata = GibApiHata("GIB sunucusuna ulasilamadi: %s" % hata)
            if deneme < max_deneme:
                bekleme = BEKLEME_SURESI[min(deneme - 1, len(BEKLEME_SURESI) - 1)]
                logger.warning("GİB bağlantı hatası, %s sn bekleniyor... (deneme %s/%s)",
                               bekleme, deneme, max_deneme)
                time.sleep(bekleme)
                continue
            raise son_hata
        except ValueError:
            raise GibApiHata("GIB sunucusundan beklenmeyen yanit geldi.")
    raise son_hata or GibApiHata("Maksimum deneme sayısına ulaşıldı.")


def giris_token(kullanici_kodu, sifre):
    """e-Arsiv portali token'i alir. Basarisizsa GibApiHata firlatir."""
    govde = (
        "assoscmd=anologin&rtype=json&userid=%s&sifre=%s&sifre2=%s&parola=1&"
        % (
            urllib.parse.quote(str(kullanici_kodu)),
            urllib.parse.quote(sifre),
            urllib.parse.quote(sifre),
        )
    )
    yanit = _isteg_yap(GIRIS_ADRESI, govde, TEMEL_ADRES + "/intragiris.html")
    if not isinstance(yanit, dict):
        raise GibApiHata("Giris yaniti anlasilamadi.")
    token = yanit.get("token")
    if not token:
        mesajlar = yanit.get("messages") or []
        metin = "; ".join(m.get("text", "") for m in mesajlar if isinstance(m, dict))
        if not metin:
            metin = "kullanici kodu veya sifre gecersiz"
        raise GibApiHata("Giris basarisiz: %s" % metin)
    return token


def _sorgu(token, komut, sayfa, payload, sayac=None):
    if sayac is None:
        sayac = _sayac_sifirla()
    sayac[0] += 1
    onek = format(random.getrandbits(52), "x")[:13]
    callid = "%s-%d" % (onek, sayac[0])
    jp = urllib.parse.urlencode({"jp": json.dumps(payload, ensure_ascii=False)})
    govde = "cmd=%s&callid=%s&pageName=%s&token=%s&%s" % (
        komut, callid, sayfa, token, jp)
    yanit = _isteg_yap(SORGU_ADRESI, govde, TEMEL_ADRES + "/index.jsp")
    hata = yanit.get("error") if isinstance(yanit, dict) else None
    if hata not in (None, "", "0"):
        mesajlar = (yanit.get("messages") or []) if isinstance(yanit, dict) else []
        metin = "; ".join(m.get("text", "") for m in mesajlar if isinstance(m, dict)) or str(hata)
        raise GibApiHata("Belge sorgusu basarisiz: %s" % metin)
    veri = yanit.get("data") if isinstance(yanit, dict) else None
    if isinstance(veri, dict):
        veri = veri.get("data") or []
    return veri or []


def _tarih_donustur(tarih):
    """dd.mm.yyyy veya date nesnesini dd.mm.yyyy metnine cevirir."""
    if hasattr(tarih, "strftime"):
        return tarih.strftime("%d.%m.%Y")
    return str(tarih)


class GibApi:
    """Oturum yenilemeyi kendiliginden yapan e-Arsiv istemcisi."""

    def __init__(self, kullanici_kodu, sifre):
        self.kullanici_kodu = kullanici_kodu
        self.sifre = sifre
        self.token = None
        self._sayac = _sayac_sifirla()

    def giris(self):
        self.token = giris_token(self.kullanici_kodu, self.sifre)
        return self.token

    def _sorgu_yenilemeli(self, komut, sayfa, baslangic, bitis):
        payload = {
            "baslangic": _tarih_donustur(baslangic),
            "bitis": _tarih_donustur(bitis),
            "hourlySearchInterval": "NONE",
            "hangiTip": "5000/30000",
            "table": [],
        }
        for deneme in (1, 2):
            if not self.token:
                self.giris()
            try:
                return _sorgu(self.token, komut, sayfa, payload, sayac=self._sayac)
            except GibApiHata as hata:
                if deneme == 2 or not _oturum_doldu_mu(hata):
                    raise
                self.giris()

    def adima_duzenlenen_belgeler(self, baslangic, bitis):
        """Adina duzenlenen (alis) e-Arsiv belgelerini listeler."""
        return self._sorgu_yenilemeli(_ALIS_KOMUTU, _ALIS_SAYFA, baslangic, bitis)

    def duzenlenen_belgeler(self, baslangic, bitis):
        """Duzenlenen (satis) e-Arsiv belgelerini listeler."""
        return self._sorgu_yenilemeli(_SATIS_KOMUTU, _SATIS_SAYFA, baslangic, bitis)


def adima_duzenlenen_belgeler(token, baslangic, bitis):
    """Adina duzenlenen (alis) e-Arsiv belgelerini listeler."""
    payload = {
        "baslangic": _tarih_donustur(baslangic),
        "bitis": _tarih_donustur(bitis),
        "hourlySearchInterval": "NONE",
        "hangiTip": "5000/30000",
        "table": [],
    }
    return _sorgu(token, _ALIS_KOMUTU, _ALIS_SAYFA, payload)


def duzenlenen_belgeler(token, baslangic, bitis):
    """Duzenlenen (satis) e-Arsiv belgelerini listeler."""
    payload = {
        "baslangic": _tarih_donustur(baslangic),
        "bitis": _tarih_donustur(bitis),
        "hourlySearchInterval": "NONE",
        "hangiTip": "5000/30000",
        "table": [],
    }
    return _sorgu(token, _SATIS_KOMUTU, _SATIS_SAYFA, payload)
