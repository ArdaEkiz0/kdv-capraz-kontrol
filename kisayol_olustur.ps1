$ws = New-Object -ComObject WScript.Shell
$m = [Environment]::GetFolderPath('Desktop')
$l = $ws.CreateShortcut((Join-Path $m 'KDV Capraz Kontrol.lnk'))
$l.TargetPath = Join-Path $PSScriptRoot 'calistir.bat'
$l.WorkingDirectory = $PSScriptRoot
$l.IconLocation = Join-Path $PSScriptRoot 'logo.ico'
$l.Description = 'KDV Capraz Kontrol'
$l.Save()
Test-Path (Join-Path $m 'KDV Capraz Kontrol.lnk')
