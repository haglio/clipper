Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

projectRoot = fso.GetParentFolderName(WScript.ScriptFullName)
stateDir = projectRoot & "\state"
If Not fso.FolderExists(stateDir) Then fso.CreateFolder(stateDir)
launcherLog = stateDir & "\clipper_launcher.log"

Function Quote(s)
  Quote = Chr(34) & s & Chr(34)
End Function

Sub AppendLog(msg)
  On Error Resume Next
  Dim ts
  Set ts = fso.OpenTextFile(launcherLog, 8, True)
  ts.WriteLine Now & " " & msg
  ts.Close
End Sub

Function FindPythonCommand()
  Dim venvPython, candidates, i

' The copy a previous run left named for this app, ahead of the plain venv
' interpreter.  Windows identifies a process by the file it was started from, so
' a bare interpreter arrives as one more anonymous "Python" among every other
' Python app on the machine; app_support.process_identity makes a copy that says
' Clipper instead, and each run makes it for the run after.
  namedPython = projectRoot & "\.venv\Scripts\Clipper-Clipper.exe"
  If fso.FileExists(namedPython) Then
    FindPythonCommand = Quote(namedPython)
    Exit Function
  End If

  venvPython = projectRoot & "\.venv\Scripts\python.exe"
  If fso.FileExists(venvPython) Then
    FindPythonCommand = Quote(venvPython)
    Exit Function
  End If

  candidates = Array( _
    "python", _
    "py -3" _
  )
  For i = 0 To UBound(candidates)
    If shell.Run("cmd /c where " & Split(candidates(i), " ")(0) & " >nul 2>nul", 0, True) = 0 Then
      FindPythonCommand = candidates(i)
      Exit Function
    End If
  Next
  FindPythonCommand = ""
End Function

pythonCmd = FindPythonCommand()
If pythonCmd = "" Then
  AppendLog "ERROR: Could not find python launcher"
  MsgBox "Could not find python or py launcher.", vbCritical, "Clipper"
  WScript.Quit 1
End If

cmd = "cmd /c cd /d " & Quote(projectRoot) & " && " & pythonCmd & " -m clipper 1>>" & Quote(launcherLog) & " 2>&1"
AppendLog "INFO: Launching with command: " & cmd
shell.Run cmd, 0, False
