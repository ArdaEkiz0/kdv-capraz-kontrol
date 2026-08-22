"""GitHub'dan yeni sürüm kontrolü ve otomatik güncelleme kurulumu."""
import json
import os
import shutil
import ssl
import sys
import tempfile
import urllib.request
import zipfile

from surum import REPO, SURUM

API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"


def _token_oku():
    """Özel repo için GitHub erişim anahtarı (ortam değişkeni veya github_token.txt)."""
    tok = os.environ.get("GITHUB_TOKEN")
    if tok and tok.strip():
        return tok.strip()
    yol = os.path.join(os.path.dirname(os.path.abspath(__file__)), "github_token.txt")
    try:
        with open(yol, "r", encoding="utf-8") as f:
            icerik = f.read().strip()
        return icerik.splitlines()[0].strip() if icerik else None
    except Exception:
        return None


def _basliklar():
    basliklar = {"User-Agent": "kdv-capraz-kontrol", "Accept": "application/vnd.github+json"}
    tok = _token_oku()
    if tok:
        basliklar["Authorization"] = f"Bearer {tok}"
    return basliklar


def versiyon_karsilastir(mevcut, yeni):
    """'2.1.0' vs '2.10.0' gibi sürümleri karşılaştırır. yeni > mevcut ise True."""
    def parcala(v):
        v = (v or "").lstrip("vV")
        return [int(x) for x in v.split(".") if x.isdigit()] or [0]

    a, b = parcala(mevcut), parcala(yeni)
    return b > a


def _istek_yap(url, zaman_asimi=8):
    context = ssl.create_default_context()
    istek = urllib.request.Request(url, headers=_basliklar())
    with urllib.request.urlopen(istek, timeout=zaman_asimi, context=context) as yanit:
        return json.loads(yanit.read().decode("utf-8"))


def son_surum_bilgisi():
    """GitHub'daki en son release'i çeker.

    Döner: {"surum": "2.1.0", "ad": "...", "notlar": "...", "indirme_url": "..."}
    Internet yok veya release yoksa None döner.
    """
    try:
        veri = _istek_yap(API_URL)
        surum = (veri.get("tag_name") or "").lstrip("v")
        indirme_url = ""
        assetler = veri.get("assets") or []
        for a in assetler:
            if (a.get("name") or "").endswith(".zip"):
                # Özel repo için API uç noktası gerekli (browser linki 404 verir)
                indirme_url = a.get("url") or a.get("browser_download_url") or ""
                break
        return {
            "surum": surum,
            "ad": veri.get("name") or "",
            "notlar": veri.get("body") or "",
            "indirme_url": indirme_url,
        }
    except Exception:
        return None


def guncelleme_kontrol(mevcut_surum=SURUM):
    """Yeni sürüm varsa bilgi dict'i, yoksa None döner."""
    bilgi = son_surum_bilgisi()
    if not bilgi or not bilgi["surum"]:
        return None
    if not versiyon_karsilastir(mevcut_surum, bilgi["surum"]):
        return None
    if not bilgi["indirme_url"]:
        bilgi["indirme_url"] = f"https://github.com/{REPO}/archive/refs/tags/v{bilgi['surum']}.zip"
    return bilgi


def _indir(url, hedef):
    """URL'den dosya indirir (https, API asset veya yerel dosya yolu desteklenir)."""
    context = ssl.create_default_context()
    if url.lower().startswith("file:"):
        yerel_yol = url.replace("file://", "").replace("file:", "")
        if not os.path.isabs(yerel_yol):
            yerel_yol = os.path.abspath(yerel_yol)
        shutil.copy2(yerel_yol, hedef)
        return
    basliklar = _basliklar()
    if "api.github.com" in url and "/assets/" in url:
        # Release asset ikili içeriği
        basliklar["Accept"] = "application/octet-stream"
    istek = urllib.request.Request(url, headers=basliklar)
    with urllib.request.urlopen(istek, timeout=120, context=context) as yanit:
        with open(hedef, "wb") as f:
            shutil.copyfileobj(yanit, f)


def guncellemeyi_kur(indirme_url, hedef_yol, ilerleme_callback=None):
    """Release zip'ini indirip proje klasörüne kopyalar.

    Döner: {"kopyalanan": n, "klasor": temp_klasor}
    Temp klasörü silinmez (yeniden başlatma sonrası temizlik kullanıcıya bırakılır).
    """
    gecici = tempfile.mkdtemp(prefix="kdv_guncelleme_")
    zip_yolu = os.path.join(gecici, "guncelleme.zip")

    _indir(indirme_url, zip_yolu)
    if ilerleme_callback:
        ilerleme_callback("Zip indirildi, açılıyor...")

    cikti = os.path.join(gecici, "icerik")
    os.makedirs(cikti, exist_ok=True)
    with zipfile.ZipFile(zip_yolu) as z:
        z.extractall(cikti)

    # GitHub archive zip'i tek bir kök klasör içerir; onu bul
    kok = cikti
    icerik = os.listdir(cikti)
    if len(icerik) == 1 and os.path.isdir(os.path.join(cikti, icerik[0])):
        kok = os.path.join(cikti, icerik[0])

    kopyalanan = 0
    os.makedirs(hedef_yol, exist_ok=True)
    for kok_ad, _, dosyalar in os.walk(kok):
        for dosya in dosyalar:
            if not dosya.lower().endswith((".py", ".bat", ".ico", ".png")):
                continue
            kaynak = os.path.join(kok_ad, dosya)
            hedef = os.path.join(hedef_yol, dosya)
            try:
                shutil.copy2(kaynak, hedef)
                kopyalanan += 1
            except Exception:
                pass
    if ilerleme_callback:
        ilerleme_callback(f"{kopyalanan} dosya kopyalandı.")
    return {"kopyalanan": kopyalanan, "klasor": gecici}


def uygulamayi_yeniden_baslat():
    """Ana modülü tekrar çalıştırır (calistir.bat üzerinden)."""
    proje = os.path.dirname(os.path.abspath(__file__))
    betik = os.path.join(proje, "calistir.bat")
    if os.path.exists(betik):
        os.startfile(betik)
    else:
        import subprocess
        subprocess.Popen([sys.executable, os.path.join(proje, "main.py")])
    sys.exit(0)
