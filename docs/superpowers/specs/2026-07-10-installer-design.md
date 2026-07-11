# Notro v2.3 — 설치형(인스톨러) 전환 설계

- 날짜: 2026-07-10
- 상태: 사용자 승인 완료
- 스코프: portable exe를 Inno Setup 인스톨러로 전환 (파일 유실·위치 기억 문제 해결) + 자동 업데이터 인스톨러 대응

## 1. 배경

현재 Notro는 PyInstaller onefile portable exe라 사용자가 파일을 직접 관리해야 하고(유실 시 실행 불가), 위치를 기억해야 한다. v2.2.0 자동 업데이터도 exe 위치(`sys.executable`)에 의존해 배치로 자기교체한다. 설치형으로 전환해 위치를 `%LOCALAPPDATA%\Programs\Notro`로 고정하고, 바로가기·언인스톨러·제어판 등록을 제공한다.

## 2. 확정 요구사항

| 항목 | 결정 |
|---|---|
| 인스톨러 | Inno Setup (`installer.iss`) |
| 설치 위치 | `%LOCALAPPDATA%\Programs\Notro` (사용자별, 관리자 권한 불필요) |
| 릴리스 구성 | `NotroSetup.exe`만 (portable `Notro.exe` 미첨부) |
| 바로가기 | 시작 메뉴 + 바탕화면(옵션 체크박스) |
| 자동 시작 | 인스톨러 체크박스 → 기존 HKCU `Run` 키(값 이름 `Notro`) 재사용 |
| 데이터 | `%APPDATA%\Notro`·HKCU `Software\Notro`는 설치/업데이트/언인스톨과 무관하게 보존 |

## 3. 인스톨러 (`installer.iss`)

Inno Setup 스크립트. 버전은 빌드 시 `ISCC /DAppVersion=X.Y.Z`로 주입.

- **[Setup]**: 고정 `AppId`(GUID), `AppName=Notro`, `AppVersion={#AppVersion}`, `DefaultDirName={localappdata}\Programs\Notro`, `PrivilegesRequired=lowest`, `DisableProgramGroupPage=yes`, `UninstallDisplayIcon={app}\Notro.exe`, `CloseApplications=yes`, `CloseApplicationsFilter=Notro.exe`, `OutputBaseFilename=NotroSetup`, `OutputDir=dist`.
- **[Files]**: `Source: dist\Notro.exe; DestDir: {app}; Flags: ignoreversion`.
- **[Tasks]**: `desktopicon`(바탕화면, 기본 체크), `startupicon`(Windows 시작 시 실행, 옵션).
- **[Icons]**: `{autoprograms}\Notro` → `{app}\Notro.exe`; `{autodesktop}\Notro` (Tasks: desktopicon).
- **[Registry]**: startupicon Task 선택 시 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` 값 `Notro` = `"{app}\Notro.exe"` (config.py의 자동시작과 동일 키·값 이름 → 중복 없음).
- **[Run]**: `Filename: {app}\Notro.exe; Flags: nowait postinstall skipifsilent` (설치 후 자동 실행, silent 업데이트 시엔 앱이 [Run]으로 재실행되도록 `skipifsilent` 제외한 별도 항목 검토 — §5 참조).
- 언인스톨러 자동 생성. 데이터 디렉터리는 삭제하지 않는다.

## 4. 빌드 파이프라인 (`release.yml`)

1. PyInstaller로 `dist\Notro.exe` 빌드 (기존 그대로).
2. Inno Setup 설치: `choco install innosetup -y`.
3. `iscc installer.iss /DAppVersion=<tag에서 v 제거>` → `dist\NotroSetup.exe`.
4. SHA256: `dist\NotroSetup.exe.sha256` 생성.
5. 릴리스에 **`NotroSetup.exe` + `NotroSetup.exe.sha256`**만 첨부 (`Notro.exe` 미첨부).

## 5. 자동 업데이터 조정 (`notro_app/updater.py`)

v2.2.0 배치 자기교체 → **인스톨러 silent install**로 변경:

- 상수 `ASSET_NAME = "NotroSetup.exe"` 도입. `check_latest`가 이 자산과 `NotroSetup.exe.sha256`을 찾도록 변경.
- `download_and_verify`는 `NotroSetup.exe`를 받아 SHA256 검증(로직 동일, 파일명만 상수화).
- `apply_and_restart(setup_path)`: 배치 헬퍼(`build_bat`) 제거. 대신
  `subprocess.Popen([setup_path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"])` 실행 후 앱을 종료(호출자 `on_quit`). Inno의 `CloseApplications`가 실행 중 앱 종료를 처리하고, `[Run]` 항목이 설치 후 앱을 재실행한다. 설치 위치가 LOCALAPPDATA라 UAC 없음.
- 재실행 보장: `installer.iss [Run]`에 silent에서도 실행되는 항목 추가 — `Filename: {app}\Notro.exe; Flags: nowait postinstall` (skipifsilent 없이) 또는 `runasoriginaluser`. silent 업데이트 후 앱이 다시 뜨도록.

## 6. 예외 처리

| 상황 | 처리 |
|---|---|
| silent install 실행 실패 | 앱 종료하지 않고 유지 + 트레이 알림 |
| 다운로드/SHA256 실패 | 기존과 동일: 폐기·스킵 |
| sha256 자산 없음(구 릴리스) | 자동 설치 안 함 (기존 정책 유지) |
| 개발 실행(non-frozen) | 업데이터 전체 비활성 (기존) |

## 7. 문서

- **README** (ko/en): "내려받기 & 실행" 섹션을 설치 안내로 교체 — `NotroSetup.exe`를 받아 실행하면 `%LOCALAPPDATA%\Programs\Notro`에 설치되고 시작 메뉴/바탕화면 바로가기 생성. 제거는 제어판 또는 시작 메뉴 언인스톨. SmartScreen 경고 안내 유지.
- **CHANGELOG** `[2.3.0]`.

## 8. 테스트

- `updater.py` 단위 테스트 갱신: `build_bat` 테스트 제거, `apply_and_restart`가 올바른 silent 인자로 Popen을 호출하는지(주입 가능한 `_spawn` 훅으로) 검증. `check_latest`가 `NotroSetup.exe` 자산을 파싱하는지.
- `installer.iss`는 CI 빌드로만 검증(로컬 pytest 대상 아님).
- 기존 pytest 회귀 없이 통과.

## 9. MVP 제외 (P2+)

코드 서명(인증서) / MSI·MSIX / 다국어 인스톨러 UI / 델타 업데이트 / 관리자(Program Files) 설치 옵션.

## 10. 버전 및 마이그레이션

v2.3.0 — 설치형 전환 + 자동 업데이터 인스톨러 대응.

**v2.2.0 → v2.3.0 자동 업데이트 불가(의도된 한계):** v2.2.0 업데이터는 릴리스에서 `Notro.exe` 자산을 찾지만 v2.3.0은 `NotroSetup.exe`만 첨부한다. 따라서 v2.2.0 사용자는 v2.3.0 `NotroSetup.exe`를 **수동으로 한 번 설치**해야 한다(릴리스 노트·CHANGELOG에 명시). 설치 후 기존 `%APPDATA%\Notro` 데이터·설정은 그대로 쓰인다. v2.3.0부터는 `NotroSetup.exe` 기반 자동 업데이트가 이어진다.
