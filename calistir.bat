@echo off
chcp 65001 >nul
cd /d "%~dp0"
title KDV Capraz Kontrol - Baslatici

echo.
echo ============================================================
echo          KDV CAPRAZ KONTROL - BASLATICI
echo ============================================================
echo.

REM --- Python bulucu: py launcher veya python ---
set "PY="
set "PY_ARG="
py -3 --version >nul 2>nul
if errorlevel 1 (
    python --version >nul 2>nul
    if errorlevel 1 (
        set "PY="
        set "PY_ARG="
        echo Python bulunamadi. Python 3.12 indirilip kurulacak.
        echo Kurulum ekrani acilacak, lutfen bekleyin...
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
        echo Python indirildi. Simdi kurulum penceresi aciliyor...
        echo Kurulum penceresinde "Install Now" veya "Next" butonlarina tiklayin.
        echo.
        start /wait "%TEMP%\python-installer.exe" InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_launcher=1
        del "%TEMP%\python-installer.exe" >nul 2>nul
        echo Kurulum islemi tamamlandi. PATH yenileniyor...
        set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts"
        set "PY=python"
        set "PY_ARG="
        python --version >nul 2>nul
        if errorlevel 1 (
            echo Python kurulamadi veya PATH bulunamadi.
            echo Lutfen Python'u manuel olarak kurup tekrar calistirin.
            pause
            exit /b 1
        )
        echo Python kurulumu basarili!
        echo.
    ) else (
        set "PY=python"
        set "PY_ARG="
    )
) else (
    set "PY=py"
    set "PY_ARG=-3"
)

%PY% %PY_ARG% --version
echo.

REM --- Gerekli kutuphaneler ---
%PY% %PY_ARG% -c "import pymupdf, openpyxl, pytesseract, PIL, matplotlib, fpdf, pdfminer" >nul 2>nul
if errorlevel 1 (
    echo Gerekli kutuphaneler kuruluyor, bir dakika surebilir...
    %PY% %PY_ARG% -m pip install --quiet --upgrade --force-reinstall pymupdf openpyxl pytesseract pillow xlrd matplotlib fpdf2 pdfminer.six
    if errorlevel 1 (
        echo Kutuphaneler kurulamadi. Asagidaki hatayi not edin:
        %PY% %PY_ARG% -m pip install pymupdf openpyxl pytesseract pillow xlrd matplotlib fpdf2 pdfminer.six
        pause
        exit /b 1
    )
)

echo Uygulama kontrol ediliyor...
%PY% %PY_ARG% -c "import main" >nul 2>nul
if errorlevel 1 (
    echo.
    echo UYGULAMA BASLATILAMADI. Asagidaki hata bilgisini paylasin:
    echo ============================================================
    %PY% %PY_ARG% -c "import main"
    echo ============================================================
    echo Eksik kutuphane varsa su komutu calistirin:
    echo %PY% %PY_ARG% -m pip install pymupdf openpyxl pytesseract pillow xlrd matplotlib fpdf2
    pause
    exit /b 1
)

REM --- Eski hata logunu temizle ---
if exist "hata.log" del "hata.log" >nul 2>nul

echo Uygulama baslatiliyor...
start "" %PY% %PY_ARG% main.py

REM --- Kisa bekleme ve hata kontrolu ---
timeout /t 5 /nobreak >nul
if exist "hata.log" (
    echo.
    echo !!!!! UYGULAMA HATA VERDI !!!!!
    echo ============================================================
    type hata.log
    echo ============================================================
    echo Hatayi yukaridaki bilgilerle paylasin.
    pause
) else (
    echo.
    echo Uygulama acildi. Bu pencereyi kapatabilirsiniz.
    echo.
    timeout /t 3 /nobreak >nul
)