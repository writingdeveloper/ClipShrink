# Notro v2.7 — 클립보드 캡처 라이브러리 설계

- 날짜: 2026-07-23
- 상태: 사용자 승인 완료
- 릴리스 목표: v2.7.0
- 스코프: 클립보드의 새 PNG/비트맵 이미지를 피커의 전용 버튼 또는 선택적 자동 저장으로 `캡처` 이모지 컬렉션에 등록하고, 관련 피커 UI와 기존 등록 오류 피드백을 개선한다.

## 1. 배경과 현재 상태

Notro에는 피커가 열린 상태에서 이미지 붙여넣기 이벤트를 받으면 `PickerApi.register_clipboard()`를 호출하는 경로가 이미 있다. 그러나 이 기능은 버튼·빈 상태·하단 도움말에서 안내되지 않아 발견하기 어렵다. 또한 JavaScript가 `clipboardData.items`에서 이미지 MIME을 확인한 경우에만 백엔드를 호출하고, 백엔드는 Windows 클립보드의 등록된 PNG 포맷만 읽는다. 따라서 Python에서는 읽을 수 있는 `CF_DIB` 비트맵도 일부 캡처 도구에서 저장하지 못한다.

기존 `Monitor`는 클립보드 시퀀스가 두 번의 폴 동안 안정된 뒤 읽고, Notro가 쓴 데이터는 전용 마커로 제외한다. 새 감시 스레드를 만들지 않고 이 검증된 흐름을 재사용해야 중복 처리와 클립보드 경합을 피할 수 있다.

현재 기준선은 `python -m pytest -q`에서 **150 passed**이다.

## 2. 확정 요구사항

| 항목 | 결정 |
|---|---|
| 수동 저장 | 피커 검색창 오른쪽에 **클립보드 이미지 추가 전용 버튼**을 배치한다. 기존 `Ctrl+V`도 유지한다. |
| 자동 저장 | 설정 스위치로 켜고 끈다. **기본값은 꺼짐**이다. |
| 자동 저장 대상 | 새 클립보드의 등록 PNG 또는 비트맵 이미지. `CF_HDROP` 이미지 파일 복사는 제외한다. |
| 저장 위치 | 타입은 `emoji`, 컬렉션은 예약 컬렉션 `캡처`이다. |
| 이름 | `capture-YYYYMMDD-HHMMSS-ffffff` 형식으로 충돌을 피한다. |
| 중복 | 이미지 PNG 바이트의 SHA-256을 영속 메타데이터에 저장한다. 동일 캡처는 한 번만 등록한다. |
| 성공 피드백 | 수동 저장은 하단 상태 문구와 해당 컬렉션 이동으로 확인시킨다. 자동 저장은 조용히 처리한다. |
| 실패 피드백 | 수동 저장은 하단에 원인을 표시한다. 자동 저장 실패는 트레이 알림으로 알린다. |
| 대용량 이미지 | 원본을 라이브러리에 저장한 뒤 기존 Discord 업로드용 압축 흐름도 계속 수행한다. |
| 언어 | en·ko·ja·zh·es 5개 언어의 신규 문자열 키를 동일하게 유지한다. |
| 배포 | SemVer minor인 **v2.7.0**으로 버전·CHANGELOG·README를 갱신하고 태그 기반 GitHub Actions 릴리스를 수행한다. |

## 3. 접근법 결정

### 선택: 기존 `Monitor` 확장

`Monitor`가 이미 수행하는 시퀀스 안정화, Notro 마커 제외, 단일 읽기 흐름을 재사용한다. PNG/비트맵을 읽은 직후 선택적 캡처 콜백을 호출하고, 같은 데이터로 기존 크기 판정과 압축을 이어 간다.

### 기각한 접근

- **라이브러리 전용 감시 스레드:** 압축 감시와 같은 클립보드를 경쟁적으로 읽고 동일 이미지를 중복 처리할 수 있다.
- **피커가 열릴 때만 확인:** 피커를 열지 않아도 저장되어야 한다는 자동 저장 요구를 충족하지 못한다.

## 4. 구성 요소와 책임

### 4.1 `notro_app/capture_store.py` — 캡처 저장 서비스

새 `CaptureStore`가 클립보드 캡처 등록의 단일 진입점이 된다.

- `CAPTURE_COLLECTION_ID = "__notro_captures__"`를 영속 컬렉션 식별자로 사용한다.
- `read_clipboard_png() -> CaptureReadResult`는 `clipboard_win.get_clipboard_png()`를 우선 사용한다. PNG가 없으면 `ImageGrab.grabclipboard()`의 `Image.Image`만 PNG로 인코딩한다. 결과는 `data`와 `error`(`no_image` 또는 `read`)를 구분하며, 경로 리스트는 이미지 없음으로 반환해 파일 복사를 제외한다.
- `save_png(data) -> CaptureSaveResult`는 SHA-256을 계산하고 잠금 안에서 기존 `content_hash`를 검색한다.
- 중복이면 새 파일을 만들지 않고 기존 항목 ID와 `duplicate=True`를 반환한다.
- 신규면 `fetch.register_from_png_bytes()`로 `emoji` 항목을 예약 컬렉션에 저장하고 `content_hash`를 기록한다.
- 저장 도중 예외가 나면 부분 파일을 남기지 않고 `error="register"` 결과를 반환한다.
- 수동 버튼과 Monitor 콜백은 동일 인스턴스를 사용하여 동시 저장을 직렬화한다.

### 4.2 `notro_app/fetch.py`와 `notro_app/library.py` — 영속 메타데이터

- `_finalize_asset()`과 `register_from_png_bytes()`에 선택적 `collection`·`content_hash` 인자를 추가해 최종 자산을 처음부터 대상 컬렉션 디렉터리에 두고 메타데이터와 함께 해시를 기록한다.
- 최종 자산 쓰기 뒤 메타데이터 추가가 실패하면 방금 만든 자산을 제거해 파일과 JSON을 트랜잭션처럼 함께 성공시키거나 함께 실패시킨다.
- `Library.add_item()`에 선택적 `content_hash`를 추가한다.
- 구버전 JSON 항목에는 로드 시 `content_hash=""` 기본값을 넣는다. 스키마 버전 증가는 필요하지 않은 추가 필드로 처리한다.
- `Library.find_by_content_hash(hash_, type_, collection)`은 같은 타입·컬렉션에서 일치 항목을 찾는다.
- 컬렉션 이동과 삭제의 기존 파일 일관성 규칙은 그대로 유지한다.

### 4.3 `notro_app/monitor.py` — 자동 저장 신호

- `on_capture_image` 콜백과 `capture_enabled` 판정 콜백을 주입한다. Monitor는 Library나 레지스트리를 직접 알지 않는다.
- 등록 PNG를 읽으면 업로드 한도 이하로 조기 반환하기 전에 캡처 콜백을 한 번 호출한다.
- PNG가 없고 `ImageGrab`이 비트맵을 반환하면 PNG로 인코딩해 한 번 호출한다.
- `ImageGrab`이 경로 리스트를 반환하면 자동 캡처 콜백을 호출하지 않는다.
- 캡처 저장 실패가 기존 압축을 막지 않도록 콜백 예외를 격리한다.
- Notro 마커, 비활성 Monitor, 동일 시퀀스 처리는 기존 규칙대로 제외한다.

### 4.4 `notro_app/app.py` — 배선과 알림

- 앱 시작 시 `CaptureStore(library)`를 하나 만든다.
- `monitor.capture_enabled`는 `config.get_setting_flag("auto_capture_save")`를 읽는다. 미설정 기본값은 false다.
- `monitor.on_capture_image`는 저장 서비스를 호출한다. 신규·중복 성공은 조용히 처리하고 실제 실패만 현지화된 트레이 알림으로 보낸다.
- 같은 `CaptureStore`를 `PickerApi`에 전달한다.

### 4.5 `notro_app/picker/window.py` — API 계약

- `get_state()`에 `auto_capture_save`와 예약 컬렉션의 현지화된 표시명을 포함한다.
- `register_capture()`는 현재 클립보드를 PNG로 읽고 저장한다. 반환 계약은 다음과 같다.
  - 신규: `{ok: true, duplicate: false, item_id: "...", collection: "__notro_captures__"}`
  - 중복: `{ok: true, duplicate: true, item_id: "...", collection: "__notro_captures__"}`
  - 이미지 없음: `{ok: false, error: "no_image"}`
  - 저장 실패: `{ok: false, error: "register"}`
- `set_auto_capture_save(enabled)`는 DWORD 설정을 저장하고 실제 저장값을 반환한다.
- 기존 `register_clipboard(type_)`는 현재 탭에 저장하는 고급 `Ctrl+V` 흐름으로 유지하되 비트맵 폴백과 구체적인 오류 계약을 공유한다.
- `register_files()`는 `count=0`을 무조건 성공으로 숨기지 않고 성공·실패 개수를 반환한다.

### 4.6 피커 UI (`index.html`, `app.js`, `app.css`)

- 검색창 오른쪽 순서는 `[클립보드 추가] [+ 링크 추가] [설정]`이다.
- 전용 버튼은 클립보드+ 의미의 아이콘과 현지화된 툴팁/접근성 레이블을 갖는다.
- 클릭 성공 후 상태를 새로 받고 `state.collection`을 예약 컬렉션으로 바꿔 저장 항목을 즉시 보여 준다.
- 하단 문구를 1.8초 동안 다음 중 하나로 바꾼다: 저장 성공, 이미 저장됨, 이미지 없음, 저장 실패.
- 설정 모달은 일반 제목 아래 자동 저장 스위치와 설명을 먼저 보여 주고, 기존 감시 폴더 영역을 별도 소제목 아래 유지한다.
- 컬렉션 데이터는 내부 `name`과 표시 `label`을 분리한다. 예약 ID만 현지화하고 사용자 컬렉션 이름은 그대로 보여 준다.
- 항목 표시 데이터에도 `collection_label`을 제공한다. 우클릭 컬렉션 변경 UI는 예약 컬렉션의 내부 ID를 노출하지 않으며, 현지화된 예약 이름 입력은 다시 예약 ID로 매핑한다.
- 기존 paste 이벤트는 모든 붙여넣기에서 백엔드 저장을 비동기로 시도하되, 이미지 MIME이 명확할 때만 기본 이벤트를 막는다. 따라서 MIME이 누락된 비트맵도 저장을 시도하고, 검색창·등록 모달의 텍스트 붙여넣기는 계속 네이티브로 동작한다. 텍스트 전용 붙여넣기의 `no_image` 결과는 오류로 표시하지 않는다.
- 드롭 등록이 전부 실패하거나 일부 실패하면 하단 상태로 알린다.

## 5. 데이터 흐름

### 자동 저장

1. 클립보드 시퀀스가 두 폴 연속 안정된다.
2. Notro 마커가 없고 Monitor가 활성 상태인지 확인한다.
3. PNG 또는 비트맵을 읽는다. 파일 경로 리스트는 자동 저장에서 제외한다.
4. `auto_capture_save`가 켜져 있으면 PNG 바이트를 `CaptureStore.save_png()`에 전달한다.
5. 신규이면 원본을 예약 컬렉션에 저장한다. 중복이면 아무것도 추가하지 않는다.
6. 이미지가 업로드 한도를 넘으면 기존 압축·클립보드 교체를 이어 간다.

### 수동 저장

1. 사용자가 피커의 전용 버튼을 누른다.
2. `PickerApi.register_capture()`가 현재 클립보드의 PNG 또는 비트맵을 읽는다.
3. `CaptureStore`가 저장 또는 중복 판정을 한다.
4. UI가 결과 문구를 보여 주고 예약 컬렉션으로 이동한다.

## 6. 오류와 경합 처리

| 상황 | 처리 |
|---|---|
| 클립보드에 이미지 없음 | 수동: 하단 안내. 자동: 아무 작업 없음 |
| 클립보드 잠김/읽기 실패 | 수동: 이미지 없음과 구분한 읽기 실패 안내. 자동: 다음 시퀀스까지 대기하며 기존 압축 흐름은 중단하지 않음 |
| 동일 이미지 재저장 | 기존 항목을 반환하고 파일·메타데이터를 추가하지 않음 |
| 자동/수동 동시 저장 | `CaptureStore` 잠금과 해시 재검사로 한 항목만 생성 |
| 자산 파일 쓰기 실패 | 부분 파일 정리, 메타데이터 미추가, 오류 안내 |
| 자동 저장 실패 | 트레이 실패 알림, 원본 클립보드와 기존 압축 흐름 유지 |
| 언어 변경 | 예약 컬렉션 ID는 유지하고 표시명만 현재 언어로 변경 |
| 큰 이미지 압축 중 새 복사 | 기존 `guard_seq` 규칙으로 새 클립보드를 덮어쓰지 않음 |

## 7. 테스트와 QA

모든 동작 변경은 실패 테스트를 먼저 실행하는 TDD로 구현한다.

### 자동화 테스트

- `CaptureStore`: PNG 우선 읽기, 비트맵 폴백, 파일 리스트 제외, 신규 저장, 예약 컬렉션, 이름 형식, 영속 해시, 중복, 동시 호출, 실패 정리.
- `Library`/`fetch`: 컬렉션 직접 저장, 구버전 `content_hash` 기본값, 해시 검색, APNG 변환 회귀.
- `Monitor`: 작은 PNG 콜백, 큰 PNG 저장 후 압축, 비트맵 콜백, 파일 복사 제외, 설정 꺼짐, 마커 제외, 콜백 실패 격리.
- `PickerApi`: 수동 신규·중복·이미지 없음·읽기 실패·저장 실패, 설정 기본값 false와 토글 영속, 파일 드롭 부분 실패.
- UI 계약: 버튼/스위치 DOM, 클릭과 paste 핸들러, 예약 컬렉션 이동, 결과별 문자열 사용.
- i18n: 신규 키가 5개 언어에 모두 존재하고 placeholder 집합이 일치한다.

### 최종 자동 검증

```powershell
python -m pytest -q
python -m compileall -q notro_app tests
python build_version_file.py
```

### Windows 수동 QA

1. 자동 저장 기본값이 꺼져 있는지 확인한다.
2. 캡처 후 전용 버튼 한 번으로 `캡처` 컬렉션에 저장되고 즉시 표시되는지 확인한다.
3. 같은 캡처로 버튼을 다시 눌러 항목이 늘지 않고 중복 안내가 나오는지 확인한다.
4. 자동 저장을 켜고 피커를 닫은 채 캡처한 뒤, 다시 열었을 때 항목이 보이는지 확인한다.
5. 이미지 파일을 Explorer에서 `Ctrl+C`해도 자동 저장되지 않는지 확인한다.
6. Snipping Tool과 Chromium 이미지 복사 각각에서 PNG/비트맵 경로를 확인한다.
7. 10MB 초과 캡처가 원본 라이브러리에 저장되고 Discord용 클립보드는 기존처럼 압축되는지 확인한다.
8. 피커 `Ctrl+V`, URL 등록, 파일 드롭, 항목 선택·Discord 붙여넣기, 언어 변경을 회귀 확인한다.
9. 자동 저장 실패 시 원본 클립보드가 유지되고 트레이 오류만 표시되는지 확인한다.

## 8. 문서와 배포

- `README.md`, `README.ko.md`, `README.ja.md`, `README.zh.md`, `README.es.md`의 등록 방법에 전용 버튼·선택적 자동 저장·파일 복사 제외를 반영한다.
- `CHANGELOG.md`에 v2.7.0 Added/Changed/Fixed 항목을 기록한다.
- `notro_app.__version__`을 `2.7.0`으로 변경한다.
- 자동화·컴파일·빌드와 가능한 수동 QA를 통과한 뒤 커밋한다.
- `v2.7.0` 태그를 생성하고 원격에 푸시하여 `.github/workflows/release.yml`이 `NotroSetup.exe` GitHub Release를 만들게 한다.
- 배포 전 원격 권한 또는 인증이 없으면 로컬 변경·검증·태그 준비까지 완료하고 정확한 차단 원인을 보고한다. 자격 증명 우회는 하지 않는다.

## 9. 비목표

- 캡처 이미지 편집·크롭·OCR.
- 클립보드 기록 전체 보관.
- 파일 복사 자동 등록.
- 자동 저장 성공마다 Windows 토스트 표시.
- 기존 라이브러리 전체의 중복 제거 또는 컬렉션 스키마 전면 개편.
