"""Son denetim: sozdizimi, ice aktarma, GUI ve CLI uctan uca."""
import glob
import importlib
import os
import py_compile
import subprocess
import sys
import tempfile

SONUC = []


def adim(ad, fonk):
    try:
        detay = fonk()
        SONUC.append((ad, True, detay or ""))
    except Exception as hata:
        SONUC.append((ad, False, f"{type(hata).__name__}: {hata}"))


def sozdizimi():
    dosyalar = glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "*.py"))
    for f in dosyalar:
        py_compile.compile(f, doraise=True)
    return f"{len(dosyalar)} dosya"


def ice_aktarma():
    kok = os.path.dirname(os.path.abspath(__file__))
    moduller = sorted(set(os.path.basename(f)[:-3] for f in glob.glob(os.path.join(kok, "*.py"))))
    moduller = [m for m in moduller if m not in ("logo_olustur",)]
    hatalar = []
    for m in moduller:
        try:
            importlib.import_module(m)
        except Exception as hata:
            hatalar.append(f"{m}: {hata!r}")
    if hatalar:
        raise RuntimeError("; ".join(hatalar))
    return f"{len(moduller)} modul"


def gui():
    import tkinter as tk
    import main
    kok = tk.Tk()
    app = main.KdvKontrolApp(kok)
    kok.update()
    assert app.tablo and app.log and app.ozet_alani and app.guncelleme_butonu
    kok.destroy()
    return "acilis + widgetlar OK"


def cli():
    kok = os.path.dirname(os.path.abspath(__file__))
    cikti = os.path.join(tempfile.gettempdir(), "denetim_rapor.xlsx")
    if os.path.exists(cikti):
        os.remove(cikti)
    r = subprocess.run(
        [sys.executable, "-X", "utf8", os.path.join(kok, "cli.py"),
         "--fatura", "C:/faturalar",
         "--cetvel", "C:/cetvel/191.xlsx",
         "C:/cetvel/391.xlsx",
         "--cikti", cikti],
        capture_output=True, text=True, timeout=240, cwd=kok)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-300:])
    if not os.path.exists(cikti):
        raise RuntimeError("rapor olusmadi")
    return f"rapor {os.path.getsize(cikti)} bayt"


def test_paketi():
    kok = os.path.dirname(os.path.abspath(__file__))
    r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(kok, "test_akisi.py")],
                       capture_output=True, text=True, timeout=300, cwd=kok)
    son = [l for l in r.stdout.splitlines() if l.strip()][-1]
    if "TAMAM" not in son:
        raise RuntimeError(son)
    return son.strip()


adim("1 Sozdizimi (py_compile)", sozdizimi)
adim("2 Ice aktarma (tum moduller)", ice_aktarma)
adim("3 Test paketi (test_akisi)", test_paketi)
adim("4 GUI acilis", gui)
adim("5 CLI uctan uca (gercek veri)", cli)

print()
for ad, ok, detay in SONUC:
    print(("OK   " if ok else "HATA ") + ad + (" — " + detay if detay else ""))
kalan = [s for s in SONUC if not s[1]]
print()
print("NETICE:", "HER SEY SAGLAM" if not kalan else f"{len(kalan)} SORUN VAR")
sys.exit(1 if kalan else 0)
