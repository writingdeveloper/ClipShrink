; Notro installer (Inno Setup).
; Build:  iscc installer.iss /DAppVersion=X.Y.Z
;
; 이 파일은 반드시 UTF-8 **with BOM**으로 저장한다. BOM이 없으면 Inno이 시스템 ANSI
; 코드페이지로 읽어, 아래 다국어 메시지가 전부 깨진다.
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
; 빌드는 64비트 파이썬이라 32비트 Windows에서는 실행되지 않는다. 설치 자체를 막아
; "설치는 됐는데 실행만 안 되는" 상태를 방지한다.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
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

[Languages]
; 앱이 지원하는 5개 언어와 동일하게 맞춘다. Korean/Japanese/Spanish는 Inno Setup 공식
; 배포에 들어 있다. ChineseSimplified만 아직 공식 릴리스에 없어(개발 브랜치에만 있다)
; Inno 공식 소스에서 가져와 저장소에 동봉했다 — UTF-8 BOM을 붙여 두었으며, BOM이 없으면
; Inno이 ANSI로 읽어 중국어가 전부 깨진다.
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "ko"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "ja"; MessagesFile: "compiler:Languages\Japanese.isl"
Name: "zh"; MessagesFile: "installer\languages\ChineseSimplified.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Messages]
; 첫 설치 마법사의 완료 화면. Notro는 창이 없는 트레이 앱이고 Windows 11은 새 트레이
; 아이콘을 기본으로 숨기므로, 이 안내가 없으면 "설치했는데 아무 일도 안 일어난다"고
; 느끼기 쉽다. 자동 업데이트(/VERYSILENT)는 이 화면을 띄우지 않으므로 방해되지 않는다.
en.FinishedHeadingLabel=Notro is ready
en.FinishedLabel=Notro has no window — it runs in the system tray, next to the clock.%n%n• Press Ctrl+Shift+E anywhere to open the emoji / sticker / GIF picker.%n• Copy an image too big for Discord and Notro compresses it automatically — just paste.%n• Right-click the tray icon for settings.%n%nWindows 11 hides new tray icons: click the ^ arrow near the clock, then drag the Notro icon onto the taskbar to keep it visible.
ko.FinishedHeadingLabel=Notro 준비 완료
ko.FinishedLabel=Notro는 창이 없어요 — 트레이(시계 옆)에 상주합니다.%n%n• 어디서든 Ctrl+Shift+E를 누르면 이모지·스티커·GIF 피커가 열립니다.%n• 디스코드에 올리기엔 큰 이미지를 복사하면 자동으로 압축돼요 — 그대로 붙여넣으세요.%n• 트레이 아이콘을 우클릭하면 모든 설정이 있어요.%n%nWindows 11은 새 트레이 아이콘을 숨깁니다: 시계 옆 ^ 를 누른 뒤, Notro 아이콘을 작업 표시줄로 끌어다 놓아 고정하세요.
ja.FinishedHeadingLabel=Notro の準備ができました
ja.FinishedLabel=Notro にはウィンドウがありません — システムトレイ（時計の横）に常駐します。%n%n• どこでも Ctrl+Shift+E を押すと絵文字・スタンプ・GIF ピッカーが開きます。%n• Discord には大きすぎる画像をコピーすると自動で圧縮されます — そのまま貼り付けてください。%n• トレイアイコンを右クリックすると、すべての設定にアクセスできます。%n%nWindows 11 は新しいトレイアイコンを隠します: 時計の横の ^ をクリックし、Notro のアイコンをタスクバーにドラッグして表示させてください。
zh.FinishedHeadingLabel=Notro 已就绪
zh.FinishedLabel=Notro 没有窗口 — 它常驻在系统托盘（时钟旁）。%n%n• 在任意位置按 Ctrl+Shift+E 打开表情·贴纸·GIF 选择器。%n• 复制一张对 Discord 来说过大的图片，Notro 会自动压缩 — 直接粘贴即可。%n• 右键点击托盘图标可访问所有设置。%n%nWindows 11 会隐藏新的托盘图标: 请点击时钟旁的 ^ 箭头，然后把 Notro 图标拖到任务栏上以保持显示。
es.FinishedHeadingLabel=Notro está listo
es.FinishedLabel=Notro no tiene ventana — reside en la bandeja del sistema, junto al reloj.%n%n• Pulsa Ctrl+Shift+E en cualquier lugar para abrir el selector de emojis, stickers y GIF.%n• Copia una imagen demasiado grande para Discord y Notro la comprime automáticamente — solo pégala.%n• Haz clic derecho en el icono de la bandeja para todos los ajustes.%n%nWindows 11 oculta los iconos nuevos de la bandeja: haz clic en la flecha ^ junto al reloj y arrastra el icono de Notro a la barra de tareas para mantenerlo visible.

[CustomMessages]
en.DesktopIcon=Create a desktop shortcut
en.AdditionalIcons=Additional icons:
en.RunAtStartup=Run Notro at Windows startup
en.StartupGroup=Startup:
en.LaunchNotro=Launch Notro
en.InstallingWebView2=Installing the Microsoft Edge WebView2 Runtime (needed by the picker)...
ko.DesktopIcon=바탕화면 바로가기 만들기
ko.AdditionalIcons=추가 아이콘:
ko.RunAtStartup=Windows 시작 시 Notro 자동 실행
ko.StartupGroup=시작 프로그램:
ko.LaunchNotro=Notro 실행
ko.InstallingWebView2=Microsoft Edge WebView2 런타임을 설치하는 중입니다(피커에 필요)...
ja.DesktopIcon=デスクトップにショートカットを作成する
ja.AdditionalIcons=追加アイコン:
ja.RunAtStartup=Windows 起動時に Notro を実行する
ja.StartupGroup=スタートアップ:
ja.LaunchNotro=Notro を実行
ja.InstallingWebView2=Microsoft Edge WebView2 ランタイムをインストールしています（ピッカーに必要）...
zh.DesktopIcon=创建桌面快捷方式
zh.AdditionalIcons=附加图标:
zh.RunAtStartup=开机时自动运行 Notro
zh.StartupGroup=启动:
zh.LaunchNotro=运行 Notro
zh.InstallingWebView2=正在安装 Microsoft Edge WebView2 运行时（选择器需要）...
es.DesktopIcon=Crear un acceso directo en el escritorio
es.AdditionalIcons=Iconos adicionales:
es.RunAtStartup=Ejecutar Notro al iniciar Windows
es.StartupGroup=Inicio:
es.LaunchNotro=Ejecutar Notro
es.InstallingWebView2=Instalando Microsoft Edge WebView2 Runtime (necesario para el selector)...

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startupicon"; Description: "{cm:RunAtStartup}"; GroupDescription: "{cm:StartupGroup}"; Flags: unchecked

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
; 1) 피커는 WebView2 런타임을 필요로 한다. Windows 11에는 내장이지만 Windows 10에는
;    없을 수 있고, 없으면 설치 후 피커가 조용히 죽은 채로 남는다. 그래서 마법사에서
;    미설치를 감지하면 MS 공식 부트스트래퍼를 받아 조용히 설치한다. 실패해도 설치는
;    계속 진행된다 — 압축 기능은 WebView2 없이도 동작한다.
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "{cm:InstallingWebView2}"; Check: WebView2Downloaded; Flags: waituntilterminated
; 2) 설치가 완전히 끝난 뒤에만 앱을 실행한다(교체 중 실행 방지). postinstall 플래그가
;    없으므로 무인(/VERYSILENT) 자동 업데이트에서도 실행되어 앱이 되돌아온다.
Filename: "{app}\Notro.exe"; Description: "{cm:LaunchNotro}"; Flags: nowait runasoriginaluser

[Code]
var
  gDownloadPage: TDownloadWizardPage;
  gWebView2Downloaded: Boolean;

function WebView2Installed(): Boolean;
var
  V: String;
begin
  { notro_app/app.py의 webview2_available()과 동일한 레지스트리 키를 확인한다. }
  Result :=
    (RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', V) and (V <> '') and (V <> '0.0.0.0')) or
    (RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', V) and (V <> '') and (V <> '0.0.0.0')) or
    (RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', V) and (V <> '') and (V <> '0.0.0.0'));
end;

function WebView2Downloaded(): Boolean;
begin
  { [Run]의 Check — 실제로 내려받았을 때만 부트스트래퍼를 실행한다.
    무인 설치(/VERYSILENT)에서는 마법사 페이지가 없어 다운로드가 일어나지 않으므로
    이 값이 False로 남고, 기존 사용자의 자동 업데이트를 방해하지 않는다. }
  Result := gWebView2Downloaded;
end;

function OnDownloadProgress(const Url, FileName: String; const Progress, ProgressMax: Int64): Boolean;
begin
  Result := True;
end;

procedure InitializeWizard();
begin
  gWebView2Downloaded := False;
  gDownloadPage := CreateDownloadPage(SetupMessage(msgWizardPreparing), SetupMessage(msgPreparingDesc), @OnDownloadProgress);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = wpReady) and (not WebView2Installed()) then begin
    gDownloadPage.Clear;
    gDownloadPage.Add('https://go.microsoft.com/fwlink/p/?LinkId=2124703', 'MicrosoftEdgeWebview2Setup.exe', '');
    gDownloadPage.Show;
    try
      try
        gDownloadPage.Download;
        gWebView2Downloaded := True;
      except
        { 다운로드 실패는 치명적이지 않다 — 피커만 비활성화되고 압축은 그대로 동작한다.
          설치를 막지 않고 조용히 넘어간다. }
        gWebView2Downloaded := False;
      end;
    finally
      gDownloadPage.Hide;
    end;
  end;
end;
