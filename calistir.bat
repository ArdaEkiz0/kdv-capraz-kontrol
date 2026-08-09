@echo off
chcp 65001 >nul
cd /d "%~dp0"

py -3 -c "import pymupdf, openpyxl, pytesseract, PIL" >nul 2>nul
if errorlevel 1 (
    echo Gerekli kutuphaneler kuruluyor, bir dakika surebilir...
    py -3 -m pip install --quiet pymupdf openpyxl pytesseract pillow xlrd
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
