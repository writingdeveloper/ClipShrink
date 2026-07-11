# Notro v2.2 — 자동 업데이터 설계

- 날짜: 2026-07-10
- 상태: 사용자 승인 완료
- 스코프: Notro가 GitHub Releases를 확인해 새 버전을 **반자동**으로 설치 (지속적 기능 배포 인프라)

## 1. 배경

Notro(구 ClipShrink)는 v2.0에서 디스코드 이모지·스티커·GIF 피커로 피벗했고, 앞으로 팩 import 등 기능이 계속 추가된다. 현재 배포는 `release.yml`이 버전 태그(`v*`)에 단일 `Notro.exe`를 GitHub Release에 첨부하는 구조이며, 사용자는 수동으로 새 exe를 내려받아야 한다. 자동 업데이터는 이 수동 과정을 없애 이후 모든 업데이트가 자연히 전달되게 한다.

## 2. 확정 요구사항

| 항목 | 결정 |
|---|---|
| 자동화 수준 | **반자동** — 감지·다운로드는 자동, 교체·재시작은 사용자 동의 시 |
| 구현 방식 | **직접 구현** (urllib + GitHub Releases API + 배치 헬퍼). 신규 의존성 없음 |
| 확인 주기 | 앱 시작 시 + 24시간마다 백그라운드 확인 + 트레이 수동 확인 |
| 무결성 | GitHub HTTPS + SHA256 체크섬 검증 |
| 서명 | exe는 unsigned 유지 (첫 실행 SmartScreen 감수, README 안내됨) |
| 동작 조건 | frozen(exe)일 때만. 개발 실행(`pythonw notro.py`)에선 비활성 |

## 3. 아키텍처

신규 모듈 `notro_app/updater.py`:

- `current_version() -> str` — `__version__` 반환
- `parse_version(s) -> tuple[int, ...]` — semver 파싱 (비교용, pre-release 접미사 무시)
- `check_latest() -> LatestRelease | None` — GitHub API `/repos/writingdeveloper/Notro/releases/latest` 조회 → `{tag, exe_url, sha256_url}` 반환
- `is_newer(latest_tag, current) -> bool` — semver 비교
- `download_and_verify(rel) -> str | None` — exe를 `%TEMP%\Notro\update\`에 다운로드 → SHA256 검증 → 경로 반환(실패 시 None)
- `apply_and_restart(new_exe_path)` — 배치 헬퍼 생성 → 프로세스 종료 → 교체·재시작
- `UpdateChecker` — 백그라운드 스레드(시작 시 + 24h 주기), 상태 콜백으로 트레이 알림/메뉴 갱신

앱 통합: `app.py`가 frozen일 때만 `UpdateChecker` 기동, `tray.py`에 업데이트 메뉴 항목 추가.

## 4. 업데이트 플로우 (반자동)

1. 시작 시 + 24시간마다 `UpdateChecker`가 `check_latest()` (백그라운드 스레드, 실패는 조용히 스킵)
2. `is_newer`면 `download_and_verify()` — 백그라운드 다운로드 + SHA256 검증
3. 검증 성공 → 트레이 알림 "Notro vX.Y.Z 준비됨 — 재시작하면 적용" + 트레이 메뉴 "지금 재시작해 업데이트" 활성화
4. 사용자가 메뉴 클릭 시에만 `apply_and_restart()`

## 5. 자기 교체 메커니즘

Windows는 실행 중 exe 파일을 잠가 덮어쓰기가 불가하므로 외부 배치 헬퍼로 교체한다:

1. `%TEMP%\Notro\apply_update.bat` 생성:
   - 현재 프로세스(PID) 종료 대기 (`tasklist` 폴링 루프)
   - 기존 exe를 `.bak`으로 백업
   - 새 exe를 기존 위치로 `move /Y`
   - 새 exe 실행 (`start "" "<path>"`)
   - 성공 시 `.bak`·임시파일 정리
2. Notro가 배치를 숨김 콘솔로 실행한 뒤 자기 종료
3. 교체 실패 시 배치가 `.bak` 복구

경로 기준은 `sys.executable`(frozen exe의 실제 경로).

## 6. 무결성

- GitHub Releases 자산은 HTTPS 전송 (전송 계층 보안)
- `release.yml`에 SHA256 생성 단계 추가: 빌드 후 `Notro.exe.sha256` 생성·첨부
- `download_and_verify()`가 내려받은 exe의 SHA256을 릴리스 체크섬과 대조 (손상·변조 감지). 불일치 시 폐기
- exe 코드 서명은 인증서 비용 문제로 범위 밖. 첫 실행 SmartScreen 경고는 유지 (README에 안내됨)

## 7. UX / 설정

- 트레이 메뉴: "업데이트 확인"(수동 즉시), "자동 업데이트 확인"(토글), 새 버전 준비 시 "지금 재시작해 업데이트"
- HKCU `Software\Notro`: `last_update_check`(시각), `auto_update`(플래그, 기본 on)
- i18n: 업데이트 관련 문자열을 5개 언어(en/ko/ja/zh/es)에 추가

## 8. 예외 처리

| 상황 | 처리 |
|---|---|
| 네트워크 오류 | 조용히 스킵, 다음 주기 재시도 |
| GitHub API rate limit (unauth 60/h) | 하루 1회+수동이라 여유. 초과 시 스킵 |
| 다운로드/SHA256 실패 | 임시파일 폐기, 알림 없이 스킵 |
| 배치 교체 실패 | `.bak` 롤백, 기존 버전 유지 |
| 개발 실행(non-frozen) | 업데이터 전체 비활성 |
| 릴리스에 sha256 자산 없음 (구버전) | 검증 불가 → 자동 설치 안 함, "수동 다운로드" 알림으로 강등 |

## 9. 테스트

- `parse_version`/`is_newer` semver 비교 (동일·상위·하위·pre-release 접미사)
- `check_latest` API 응답 파싱 (mock JSON 픽스처)
- SHA256 검증 (일치/불일치)
- 배치 헬퍼 생성 문자열 (PID·경로 삽입 정확성)
- OS 상호작용(실제 교체·재시작·트레이)은 릴리스 전 수동 체크리스트

## 10. 릴리스 파이프라인 변경

`release.yml`: EXE 빌드 후 SHA256 생성 단계 추가, 릴리스 자산에 `Notro.exe.sha256` 포함. v2.2.0부터 적용.

## 11. MVP 제외 (P2+)

델타(차등) 업데이트 / 코드 서명 / 롤백 UI / 업데이트 채널(베타) / 릴리스 노트 팝업 표시.

## 12. 버전

v2.2.0 — 자동 업데이터 추가. v2.1.0→v2.2.0 첫 업데이트만 수동(v2.1.0 미탑재), 이후는 자동.
