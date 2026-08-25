"""Mükellef profillerinin yerel ve şifreli saklanması.

Kayıt yolu bilerek deponun DIŞINDADIR: %APPDATA%\\KDVCaprazKontrol\\mukellefler.json
Böylece şifreler hiçbir koşulda git deposuna veya yayın arşivine girmez.
Şifre alanları Windows DPAPI (kullanıcı kapsamlı) ile şifrelenir; sadece aynı
Windows kullanıcısı çözebilir.
"""
import base64
import ctypes
import json
import os
import uuid
from ctypes import wintypes

KLASOR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                      "KDVCaprazKontrol")
DOSYA = os.path.join(KLASOR, "mukellefler.json")
ON_EK = "dpapi:"


class _VeriBlobu(ctypes.Structure):
    _fields_ = [("uzunluk", wintypes.DWORD),
                ("veri", ctypes.POINTER(ctypes.c_char))]


def _dpapi_isle(veri, sifreleme):
    crypt32 = ctypes.windll.crypt32
    tampon = ctypes.create_string_buffer(veri, len(veri))
    giris = _VeriBlobu(len(veri),
                       ctypes.cast(tampon, ctypes.POINTER(ctypes.c_char)))
    cikis = _VeriBlobu()
    if sifreleme:
        tamam = crypt32.CryptProtectData(
            ctypes.byref(giris), "KDVCaprazKontrol", None, None, None, 0,
            ctypes.byref(cikis))
    else:
        tamam = crypt32.CryptUnprotectData(
            ctypes.byref(giris), None, None, None, None, 0,
            ctypes.byref(cikis))
    if not tamam:
        raise OSError("DPAPI işlemi başarısız")
    try:
        sonuc = ctypes.string_at(cikis.veri, cikis.uzunluk)
    finally:
        ctypes.windll.kernel32.LocalFree(cikis.veri)
    return sonuc


def sifrele(metin):
    """Metni DPAPI ile şifreleyip 'dpapi:<base64>' biçiminde döndürür."""
    if not metin:
        return ""
    if not hasattr(ctypes, "windll"):
        return "b64:" + base64.b64encode(metin.encode("utf-8")).decode("ascii")
    sifreli = _dpapi_isle(metin.encode("utf-8"), True)
    return ON_EK + base64.b64encode(sifreli).decode("ascii")


def sifre_coz(deger):
    """'dpapi:<base64>' değerini çözer; çözülemezse boş metin döner."""
    if not deger:
        return ""
    try:
        if deger.startswith(ON_EK):
            ham = base64.b64decode(deger[len(ON_EK):])
            return _dpapi_isle(ham, False).decode("utf-8")
        if deger.startswith("b64:"):
            return base64.b64decode(deger[4:]).decode("utf-8")
    except Exception:
        pass
    return ""


def yeni_mukellef():
    return {
        "id": uuid.uuid4().hex[:12],
        "ad": "",
        "vkn": "",
        "gib_tc": "",
        "gib_sifre": "",
        "ivd_kod": "",
        "ivd_sifre": "",
        "ent_kurum": "",
        "ent_kullanici": "",
        "ent_sifre": "",
        "luca_uye": "",
        "not": "",
    }


def yukle():
    veri = _yukle_ham()
    return veri.get("mukellefler", [])


def _yukle_ham():
    try:
        with open(DOSYA, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"surum": 1, "mukellefler": []}


def kaydet(mukellefler):
    os.makedirs(KLASOR, exist_ok=True)
    veri = {"surum": 1, "mukellefler": mukellefler}
    gecici = DOSYA + ".gecici"
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=2)
    try:
        if os.name == "nt":
            ctypes.windll.kernel32.SetFileAttributesW(gecici, 0x80)
    except Exception:
        pass
    if os.path.exists(DOSYA):
        os.remove(DOSYA)
    os.replace(gecici, DOSYA)


def coz_ve_getir(mukellef):
    """Panelin çekim akışı için şifreleri çözülmüş kopya döndürür."""
    k = dict(mukellef)
    k["gib_sifre"] = sifre_coz(mukellef.get("gib_sifre"))
    k["ivd_sifre"] = sifre_coz(mukellef.get("ivd_sifre"))
    k["ent_sifre"] = sifre_coz(mukellef.get("ent_sifre"))
    return k


def coz_klasor(kimlik, yil, ay):
    """Seçilen mükellef ve dönem için indirme klasörünü döndürür."""
    guvenli = "".join(c if c.isalnum() else "_" for c in (kimlik or "mukellef"))
    return os.path.join(KLASOR, "Faturalar", guvenli, f"{yil}{ay:02d}")


def sifirla():
    """Depodaki tüm mükellefleri siler (yerel testler için)."""
    try:
        os.remove(DOSYA)
    except OSError:
        pass
