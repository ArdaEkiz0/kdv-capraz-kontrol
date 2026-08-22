@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Masaustune "KDV Capraz Kontrol" kisayolu olusturuluyor...
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $masaustu = [Environment]::GetFolderPath('Desktop'); $lnk = $ws.CreateShortcut((Join-Path $masaustu 'KDV Capraz Kontrol.lnk')); $lnk.TargetPath = '%~dp0calistir.bat'; $lnk.WorkingDirectory = '%~dp0'; $lnk.IconLocation = '%~dp0logo.ico'; $lnk.Description = 'KDV Capraz Kontrol'; $lnk.Save()"
if errorlevel 1 (
    echo Kisayol olusturulamadi.
) else (
    echo Tamam! Masaustunde "KDV Capraz Kontrol" kisayolu hazir.
    echo Bundan sonra uygulamayi masaustundeki logolu kisayoldan acabilirsiniz.
)
pause
