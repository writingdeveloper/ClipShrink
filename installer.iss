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
SetupIconFile=assets\notro.ico
UninstallDisplayIcon={app}\Notro.exe
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
CloseApplicationsFilter=Notro.exe
RestartApplications=no
WizardStyle=modern

[Messages]
; The first-time wizard's finish page tells the user where Notro lives and how to use it:
; Notro is a windowless tray app and Windows 11 hides new tray icons by default, so
; without this a fresh install can feel like nothing happened. Silent auto-updates
; (/VERYSILENT) never show this page, so existing users are not interrupted by it.
; Deliberately ASCII-only: an .iss without a UTF-8 BOM is read with the system ANSI
; codepage, so non-ASCII text here could render as mojibake on the finish page.
FinishedHeadingLabel=Notro is ready
FinishedLabel=Notro has no window - it runs in the system tray, next to the clock.%n%n- Press Ctrl+Shift+E anywhere to open the emoji / sticker / GIF picker.%n- Copy an image too big for Discord and Notro compresses it automatically - just paste.%n- Right-click the tray icon for settings.%n%nWindows 11 hides new tray icons by default: click the ^ arrow near the clock, then drag the Notro icon onto the taskbar to keep it visible.
FinishedLabelNoIcons=Notro has no window - it runs in the system tray, next to the clock.%n%n- Press Ctrl+Shift+E anywhere to open the emoji / sticker / GIF picker.%n- Copy an image too big for Discord and Notro compresses it automatically - just paste.%n- Right-click the tray icon for settings.%n%nWindows 11 hides new tray icons by default: click the ^ arrow near the clock, then drag the Notro icon onto the taskbar to keep it visible.

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"
Name: "startupicon"; Description: "Run Notro at Windows startup"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "dist\Notro\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

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
