; Notro installer (Inno Setup).
; Build:  iscc installer.iss /DAppVersion=X.Y.Z
#define AppName "Notro"
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{5F8A1E2B-3C4D-4E5F-A6B7-C8D9E0F1A2B3}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=writingdeveloper
AppSupportURL=https://github.com/writingdeveloper/Notro
DefaultDirName={localappdata}\Programs\Notro
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=NotroSetup
UninstallDisplayIcon={app}\Notro.exe
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
CloseApplicationsFilter=Notro.exe
RestartApplications=no
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"
Name: "startupicon"; Description: "Run Notro at Windows startup"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "dist\Notro.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Notro"; Filename: "{app}\Notro.exe"
Name: "{autodesktop}\Notro"; Filename: "{app}\Notro.exe"; Tasks: desktopicon

[Registry]
; "Run at Windows startup" — same HKCU Run value name ("Notro") the app itself uses,
; so the tray toggle and this installer option never create duplicate entries.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Notro"; ValueData: """{app}\Notro.exe"""; Tasks: startupicon; Flags: uninsdeletevalue

[Run]
; Launch Notro only after the install fully completes. Inno runs [Run] entries
; when installation has finished, which avoids relaunching the app while the exe
; is still being replaced (that mid-swap relaunch broke onefile's Python DLL
; extraction). No "postinstall" flag -> this runs in silent auto-update installs
; too, not just manual ones; runasoriginaluser keeps it at the user's privilege.
Filename: "{app}\Notro.exe"; Description: "Launch Notro"; Flags: nowait runasoriginaluser
