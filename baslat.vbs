' KDV Capraz Kontrol - VBS Baslatici
' Bu dosya CMD penceresi gostermeden uygulamayi baslatir.
' Cift tiklanarak calistirilabilir.

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

projeYolu = fso.GetParentFolderName(WScript.ScriptFullName)

' Python bul: once py -3, sonra python
pyYolu = ""
On Error Resume Next
pyYolu = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python312\python.exe")
If fso.FileExists(pyYolu) Then
    On Error GoTo 0
Else
    pyYolu = "python"
    On Error GoTo 0
End If

' Gerekli kutuphaneleri kontrol et ve kur
shell.CurrentDirectory = projeYolu
shell.Run """" & pyYolu & """ -c ""import pymupdf, openpyxl, PIL, matplotlib, fpdf, pdfminer""", 0, True

' Uygulamayi baslat (pythonw kullanarak penceresiz)
pythonwYolu = Replace(pyYolu, "python.exe", "pythonw.exe")
If fso.FileExists(pythonwYolu) Then
    shell.Run """" & pythonwYolu & """ main.py", 0, False
Else
    shell.Run """" & pyYolu & """ main.py", 0, False
End If
