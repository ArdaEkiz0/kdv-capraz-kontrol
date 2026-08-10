@echo off
chcp 65001 >nul
cd /d "%~dp0"

py -3 --version >nul 2>nul
if errorlevel 1 (
    echo Python bulunamadi!
    echo Python 3.12'yi suradan indirip kurun:
    echo https://www.python.org/downloads/release/python-31210/
    echo Kurulumda "Add python.exe to PATH" kutusunu isaretlemeyi unutmayin.
    pause
    exit /b 1
)

py -3 -c "import pymupdf, openpyxl, pytesseract, PIL, matplotlib, fpdf2" >nul 2>nul
if errorlevel 1 (
    echo Gerekli kutuphaneler kuruluyor, bir dakika surebilir...
    py -3 -m pip install --quiet pymupdf openpyxl pytesseract pillow xlrd matplotlib fpdf2
)

echo Uygulama kontrol ediliyor...
py -3 -c "import main" >nul 2>nul
if errorlevel 1 (
    echo.
    echo UYGULAMA BASLATILAMADI. Asagidaki hata bilgisini paylasin:
    echo ============================================================
    py -3 -c "import main"
    echo ============================================================
    echo Eksik kutuphane varsa su komutu calistirin:
    echo py -3 -m pip install pymupdf openpyxl pytesseract pillow xlrd matplotlib fpdf2
    pause
    exit /b 1
)

set "PYW="
for /f "delims=" %%i in ('py -3 -c "import sys,os;print(os.path.join(sys.base_prefix,'pythonw.exe'))"') do set "PYW=%%i"

if not exist "%PYW%" (
    echo pythonw.exe bulunamadi. Konsolda calistiriliyor:
    py -3 main.py
    pause
    exit /b 1
)

start "" "%PYW%" main.py
if errorlevel 1 (
    echo Hata olustu, konsolda calistiriliyor:
    py -3 main.py
    pause
)
