Set WshShell = CreateObject("WScript.Shell")
' Run pythonw instead of python to avoid creating a command prompt window
WshShell.Run ".venv\Scripts\pythonw.exe -m clients.windows.codesk_tray", 0, False
