@echo off
chcp 65001 >nul
cd /d "%~dp0"
title KDV Capraz Kontrol - Kurulum

echo.
echo ============================================================
echo          KDV CAPRAZ KONTROL - BASLATICI
echo ============================================================
echo.

REM --- Python kontrol ---
py -3 --version >nul 2>nul
if errorlevel 1 (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python bulunamadi. Otomatik indirilip kuruluyor...
        echo (Iptal etmek icin pencereyi kapatabilirsiniz)
        echo.
        powershell -NoProfile -Command "Set-Variable -Name ProgressPreference -Value SilentlyContinue; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile '%TEMP%\python-installer.exe'"
        if errorlevel 1 (
            echo Python indirilemedi! Baglanti sorununuz olabilir.
            echo Manuel olarak suradan indirip kurun:
            echo https://www.python.org/downloads/release/python-31210/
            echo Kurulumda "Add python.exe to PATH" kutusunu isaretleyin.
            pause
            exit /b 1
        )
        echo Kurulum yapiliyor (bir dakika surebilir)...
        "%TEMP%\python-installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_launcher=1
        del "%TEMP%\python-installer.exe" >nul 2>nul
        echo Python kuruldu. PATH yenileniyor...
        set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts"
        py -3 --version >nul 2>nul
        if errorlevel 1 (
            echo Python kuruldu ama PATH bulunamadi. Lutfen yeni bir pencere acip tekrar calistirin.
            pause
            exit /b 1
        )
        echo Python kurulumu basarili!
        echo.
    )
)

REM --- Gerekli kutuphaneler ---
py -3 -c "import pymupdf, openpyxl, pytesseract, PIL, matplotlib, fpdf2" >nul 2>nul
if errorlevel 1 (
    echo Gerekli kutuphaneler kuruluyor, bir dakika surebilir...
    py -3 -m pip install --quiet pymupdf openpyxl pytesseract pillow xlrd matplotlib fpdf2
    if errorlevel 1 (
        echo Kutuphaneler kurulamadi. Asagidaki hatayi not edin:
        py -3 -m pip install pymupdf openpyxl pytesseract pillow xlrd matplotlib fpdf2
        pause
        exit /b 1
    )
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