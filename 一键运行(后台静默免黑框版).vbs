Set ws = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
currentDir = fso.GetParentFolderName(WScript.ScriptFullName)

' 隐藏黑框执行一键运行脚本 (0 = vbHide)
ws.Run "cmd.exe /c """ & currentDir & "\run.bat""", 0, False
