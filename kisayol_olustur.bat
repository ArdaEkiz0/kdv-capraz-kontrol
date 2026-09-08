@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Masaustune "KDV Capraz Kontrol" kisayolu olusturuluyor...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0kisayol_olustur.ps1"
if errorlevel 1 (
    echo Kisayol olusturulamadi.
) else (
    echo Tamam! Masaustunde "KDV Capraz Kontrol" kisayolu hazir.
    echo Bundan sonra uygulamayi masaustundeki logolu kisayoldan acabilirsiniz.
)
pause
