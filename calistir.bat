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
%PY% %PY_ARG% -c "import pymupdf, openpyxl, pytesseract, PIL, matplotlib, fpdf, pdfminer, playwright" >nul 2>nul
if errorlevel 1 (
    echo Gerekli kutuphaneler kuruluyor, bir dakika surebilir...
    %PY% %PY_ARG% -m pip install --quiet --upgrade --force-reinstall pymupdf openpyxl pytesseract pillow xlrd matplotlib fpdf2 pdfminer.six playwright
    if errorlevel 1 (
        echo Kutuphaneler kurulamadi. Asagidaki hatayi not edin:
        %PY% %PY_ARG% -m pip install pymupdf openpyxl pytesseract pillow xlrd matplotlib fpdf2 pdfminer.six playwright
        pause
        exit /b 1
    )
)

echo Uygulama kontrol ediliyor...
REM Agir kutuphaneleri import etmeden hizli sozdizimi denetimi
%PY% %PY_ARG% -c "import py_compile; py_compile.compile('main.py', doraise=True)" >nul 2>nul
if errorlevel 1 (
    echo.
    echo UYGULAMA BASLATILAMADI. Asagidaki hata bilgisini paylasin:
    echo ============================================================
    %PY% %PY_ARG% -c "import py_compile; py_compile.compile('main.py', doraise=True)"
    echo ============================================================
    pause
    exit /b 1
)

REM --- Eski hata logunu temizle ---
if exist "hata.log" del "hata.log" >nul 2>nul

echo Uygulama baslatiliyor (ilk acilis 1-2 dakika surebilir)...
start "" %PY% %PY_ARG% main.py

REM --- Bekle ve hata kontrolu ---
set /a BEKLEME=0
:bekle_dongu
timeout /t 5 /nobreak >nul
if exist "hata.log" goto hata_var
set /a BEKLEME+=5
if %BEKLEME% LSS 30 goto bekle_dongu
echo.
echo Uygulama acildi. Bu pencereyi kapatabilirsiniz.
timeout /t 3 /nobreak >nul
exit /b 0

:hata_var
echo.
echo !!!!! UYGULAMA HATA VERDI !!!!!
echo ============================================================
type hata.log
echo ============================================================
echo Hatayi yukaridaki bilgilerle paylasin.
pause