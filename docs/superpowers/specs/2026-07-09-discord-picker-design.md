# ClipShrink v2.0 — 디스코드 이모지·스티커·GIF 피커 설계

- 날짜: 2026-07-09
- 상태: 사용자 승인 대기
- 스코프: 디스코드 입력창의 이모지/스티커/GIF 버튼이 여는 피커 패널을 **클라이언트 수정 없이** 보조도구로 대체 (니트로 3대 기능 대체 프로젝트의 1단계)

## 1. 배경

ClipShrink는 클립보드 이미지를 디스코드 무료 업로드 한도(10MB)에 맞춰 자동 압축하는 트레이 상주 앱이다. 2026-07-09 딥리서치 결과, 니트로가 잠근 이모지·스티커를 ToS를 지키며 다루는 **독립 데스크톱 도구는 존재하지 않는다**(클라이언트 모드인 Vencord FakeNitro는 ToS 위반, NQN 봇은 봇이 설치된 서버에서만 동작). 디스코드가 업로드된 APNG를 재생하지 않아 FakeNitro도 스티커를 GIF로 변환해 첨부하며, 한국 커뮤니티에는 이 과정을 수동으로 하는 다단계 공략이 존재한다 — 자동화 공백이 검증됐다.

핵심 ToS 경계 (설계 불변 조건):

1. **디스코드 클라이언트를 수정하지 않는다** (프로세스·파일·메모리 일절 불가침)
2. **유저 토큰으로 API를 호출하지 않는다** (셀프봇 = 계정 종료 사유)
3. 도구는 클립보드 준비와 OS 수준 키 입력(Ctrl+V 시뮬)까지만 하고, **전송(Enter)은 항상 사용자가 한다**

## 2. 확정 요구사항

| 항목 | 결정 |
|---|---|
| 라이브러리 소스 | 디스코드에서 복사한 CDN 링크/이미지 붙여넣기 등록 + 감시 폴더 자동 표시 (둘 다) |
| GIF 탭 | 내 로컬 GIF 컬렉션 (Tenor 검색 없음 — 디스코드 GIF탭은 원래 무료라 재현 가치 낮음) |
| 호출 방식 | 글로벌 핫키(기본 `Ctrl+Shift+E`, 변경 가능) → 커서 근처 팝업. 트레이 클릭으로도 열림 |
| 선택 후 동작 | 창 숨김 → 직전 포커스 창 복귀 → Ctrl+V 자동 입력 → 전송은 사용자 |
| UI | 디스코드 다크 테마를 HTML/CSS로 최대 재현 (자체 제작 — 디스코드 로고·아이콘·gg sans 폰트 자산은 복사하지 않음) |
| 접근법 | ClipShrink에 통합, 피커 창만 pywebview(WebView2). exe 하나 유지 |

## 3. 아키텍처

660줄 단일 파일을 패키지로 분리한다. 진입점 `clipshrink.py`는 `main()` 호출만 남겨 `build.bat`/`pythonw` 호환을 유지한다.

```
clipshrink.py          # 진입점 (main() 호출만)
clipshrink_app/
  config.py            # 레지스트리 설정 (기존 이관)
  i18n.py              # 다국어 (기존 이관 + 피커 신규 키; 신규 키는 en/ko 우선, 나머지 en 폴백)
  compress.py          # 압축 로직 (기존 이관)
  clipboard_win.py     # CF_HDROP/PNG 클립보드 (기존 이관) + SendInput Ctrl+V 시뮬 (ctypes)
  monitor.py           # 클립보드 감시 루프 (기존 Monitor 이관)
  tray.py              # pystray 메뉴 (기존 + 피커 열기·핫키 설정·폴더 관리 항목)
  hotkey.py            # RegisterHotKey 글로벌 핫키 + 메시지 루프 스레드 (신규, ctypes)
  library.py           # 라이브러리 CRUD·검색·폴더 스캔 (신규)
  fetch.py             # 디스코드 CDN URL 파싱·다운로드·APNG→GIF 변환 (신규)
  picker/
    window.py          # pywebview 창 생성/표시/숨김 + Python↔JS 브리지 (신규)
    ui/index.html, app.css, app.js   # 디스코드 다크테마 피커 UI (신규)
```

- 의존성 추가: **pywebview 하나** (WebView2 런타임은 Windows 11 내장). 핫키·키 시뮬은 ctypes 직접 구현으로 pywin32를 피한다.
- 스레딩: pywebview 이벤트 루프(메인 스레드) + pystray(detached) + 핫키 메시지 루프(전용 스레드) + 기존 Monitor 스레드. **이 동거가 최대 통합 리스크**이므로 구현 계획의 첫 태스크는 넷을 합친 walking skeleton이다.
- 피커 창은 시작 시 생성 후 숨겨두고 핫키에 show/hide만 한다 (팝업 지연 제거).

## 4. 데이터 모델 (`%APPDATA%\ClipShrink\`)

- `library.json` — 항목 배열:
  `{id, type: "emoji"|"sticker"|"gif", name, keywords: [], source: {kind: "discord-cdn"|"local", url?, orig_path?}, animated: bool, added_at, use_count, last_used}`
- `assets\{id}.{png|gif|webp}` — 등록 시 다운로드/복사한 원본 캐시. 등록 이후에는 오프라인·원본 삭제와 무관하게 동작
- `folders.json` — 감시 폴더 배열 `{path, default_type}`; 피커 열 때 mtime 기반 재스캔, PNG/GIF/WebP/APNG 자동 표시 (등록 절차 없음)
- 기존 압축 임시파일(`%TEMP%\ClipShrink`)과 분리 — 라이브러리는 영구 데이터

## 5. 등록 플로우

| 입력 | 처리 |
|---|---|
| 이모지 CDN 링크 (`cdn.discordapp.com/emojis/{id}.*` — 디스코드 우클릭→링크 복사) | id 파싱 → size 파라미터 제거한 원본 다운로드 → 이름·키워드 입력 → `emoji` 저장 |
| 스티커 CDN 링크 (`media.discordapp.net/stickers/{id}.*`) | 동일. **APNG 감지 시 GIF 자동 변환** (디스코드는 업로드된 APNG를 애니메이션 재생하지 않음 — FakeNitro와 동일한 해법) |
| 이미지 파일 드래그앤드롭 / 클립보드 이미지 붙여넣기 | 캐시로 복사 후 등록 (스티커를 수동 저장한 경우의 주 경로) |
| 감시 폴더 | 스캔 자동 표시 |

지원하지 않는 것 (명시적 한계):

- 메시지 링크로 스티커 가져오기 — API 인증 필요 = 셀프봇 경계 위반이라 영구 제외
- Tenor 페이지 URL 파싱 — 스크레이핑이라 MVP 제외

## 6. 피커 동작

1. 핫키 → `GetForegroundWindow()` 저장 → 커서 근처 표시(모니터 경계 클램프) → 검색창 자동 포커스. 창 크기는 디스코드 피커와 유사한 고정 ~440×420px(리사이즈 없음, MVP)
2. UI: 상단 검색바(이름·키워드 부분일치), 이모지/스티커/GIF 3탭, 그리드(이모지 48px 셀, 스티커·GIF 큰 셀), 최상단 "최근 사용" 섹션. 움짤 썸네일은 WebView 엔진이 네이티브 재생. 항목이 많으면 lazy-load(IntersectionObserver)
3. 선택(클릭 또는 Enter=첫 항목): 창 숨김 → `SetForegroundWindow(저장 핸들)` → `set_clipboard_file()`(기존 함수 재사용, marker 포함해 Monitor 재처리 방지) → `SendInput` Ctrl+V → 사용자가 Enter로 전송
4. ESC/포커스 아웃 → 숨김
5. 출력 형태: 기본 = **파일 첨부**(받는 쪽에 URL 텍스트 노출 없음). CDN 소스 항목은 우클릭 → "링크로 붙여넣기"(CF_UNICODETEXT로 URL 삽입) 선택 가능
6. 10MB 초과 항목은 기존 압축 파이프라인이 이어받는다 (두 기능의 결합점)

## 7. 예외 처리

| 상황 | 처리 |
|---|---|
| `SetForegroundWindow` 거부 (포그라운드 잠금) | `AttachThreadInput` 폴백 → 실패 시 "클립보드에 담아뒀습니다, Ctrl+V 하세요" 트레이 알림. 클립보드 세팅까지는 항상 보장 |
| CDN 404/네트워크 오류 | 등록 시점에 즉시 다운로드·검증하므로 사용 시점 오류 없음. 등록 실패는 그 자리에서 안내 |
| WebView2 런타임 부재 (구형 Win10) | 감지 후 Evergreen 설치 안내 링크. Win11은 내장 |
| APNG→GIF 변환 실패 | 정지 PNG 폴백 저장 + 항목 경고 배지 |
| 10MB 초과 GIF | 그대로 첨부 시도 + 초과 경고 (GIF 재압축은 품질 저하가 커서 P2) |
| 감시 폴더 소실 | 항목 회색 처리, 복구 시 자동 복귀 |
| `RegisterHotKey` 등록 실패 (다른 앱이 조합 선점) | 트레이 알림으로 실패 고지 + 트레이 메뉴에서 다른 조합으로 변경 유도. 핫키 없이도 트레이 클릭으로 피커 사용 가능 |

## 8. 테스트

- 기존 pytest 체계 연장, 코어 모듈 TDD: `library.py`(CRUD·검색·중복·폴더 스캔·JSON 마이그레이션), `fetch.py`(CDN URL 정규식, APNG 감지, GIF 변환 — 픽스처 파일), 리팩터링 후 기존 압축 테스트 전부 통과 확인
- OS 상호작용(핫키·포커스 복귀·실제 붙여넣기·멀티모니터·ESC)은 릴리스 전 수동 체크리스트로 검증

## 9. MVP 제외 (P2+)

Tenor 검색 내장 / 봇 연동 서버 이모지 일괄 수집 / 클립보드 이전 내용 복원 / GIF 재압축(gifsicle) / 영상 압축(프로젝트 ②) / 외부 호스팅 폴백(프로젝트 ③) / 신규 문자열의 ja·zh·es 번역(우선 en 폴백)

## 10. 리스크

| 리스크 | 완화 |
|---|---|
| pywebview+pystray+핫키 루프 동거 실패 | 첫 태스크 = walking skeleton으로 조기 검증. 실패 시 폴백: 피커를 별도 프로세스로 분리하고 트레이와 IPC |
| 포커스 복귀의 Windows 제약 | 폴백 체인 설계 완료 (§7). 최악에도 클립보드 수동 붙여넣기로 강등 |
| exe 크기 증가 (pywebview) | pywebview 자체는 소형 (WebView2는 OS 제공). PyInstaller 결과물 실측 후 문서화 |
| 디스코드 CDN URL 형식 변경 | 정규식을 fetch.py 한 곳에 격리, 테스트 픽스처로 회귀 감지 |

## 11. 버전

v2.0.0 — 기능 추가(피커) + 구조 리팩터링(패키지 분리). CHANGELOG에 리팩터링·신기능 분리 기재.
