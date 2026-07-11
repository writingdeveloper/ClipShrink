# Notro v2.5 — 컬렉션별 폴더 저장 + 대표 아이콘 설계

- 날짜: 2026-07-11
- 상태: 사용자 승인 완료
- 스코프: `assets/` 캐시를 컬렉션별 하위 폴더로 재구성하고, 피커 세로 바에 텍스트 대신 대표 이미지 아이콘을 표시한다.

## 1. 배경

v2.4.0에서 즐겨찾기·컬렉션(세로 바)을 추가했지만, 실제 자산 파일은 `assets/{uuid}.ext`로 평면 저장되고 분류는 `library.json`의 `collection` 필드에만 있다. 사용자가 트레이 "라이브러리 폴더 열기"로 탐색기를 직접 열면 uuid 파일명만 잔뜩 보여 관리가 어렵다. 또한 세로 바가 컬렉션명 앞 2글자 텍스트라 컬렉션이 늘수록 식별이 어렵다.

## 2. 확정 요구사항

| 항목 | 결정 |
|---|---|
| 저장 구조 | `assets/{slug(collection)}/{uuid}.ext`. 미분류(`collection=""`)는 `assets/_uncategorized/` |
| 진실 소스 | `collection` 필드가 유일한 source of truth. 폴더 위치는 여기서 파생. 폴더를 직접 옮겨도 반영 안 됨(감시 폴더와는 다른 개념) |
| 이동 시점 | `set_collection()` 호출 시 파일을 물리적으로 이동. **이동 성공 후에만** 메타데이터 갱신(실패 시 상태 불변) |
| 기존 파일 | `Library` 로드 시 1회 자동 마이그레이션(평면 잔존 파일 발견 시 계산된 위치로 이동). 멱등 |
| 대표 아이콘 | 컬렉션의 첫 항목(등록 항목 우선, 그다음 감시 폴더 스캔 순서) 썸네일. 항목 없으면 텍스트 폴백(기존 방식) |
| 감시 폴더와의 관계 | 완전 별개. 감시 폴더 항목은 `abs_path`(사용자 폴더)를 그대로 쓰며 `assets/`에 캐시되지 않음 — 이번 변경과 무관 |

## 3. 데이터 흐름 변경 (`library.py`)

- `_slug(name) -> str`: 컬렉션명을 파일시스템 안전 문자열로. 빈 문자열은 `_uncategorized`, Windows 금지 문자(`<>:"/\|?*` 등)는 `_`로 치환, 길이 제한.
- `collection_dir(name) -> str`: `assets/{slug}/` 생성 후 경로 반환 (쓰기 시 사용, `os.makedirs`).
- `asset_path(item)`: `abs_path`(감시 폴더) 우선은 유지. 등록 항목은 `os.path.join(assets_dir, _slug(item["collection"]), item["filename"])`로 변경(순수 계산, I/O 없음).
- `set_collection(id, name)`: 새 경로를 먼저 계산 → 파일이 존재하면 `os.makedirs` + `os.replace`로 이동 시도 → **성공(또는 이동 불필요)한 경우에만** `item["collection"]` 갱신 + 저장. `OSError` 시 아무것도 바꾸지 않고 조용히 반환.
- `remove_item(id)`: 삭제 경로를 `os.path.join(assets_dir, filename)`(평면 가정, 버그)에서 `asset_path(item)`(컬렉션 인지)로 수정.
- `_migrate_flat_assets_to_folders()`: `__init__`의 `_load()` 직후 1회 실행. 각 등록 항목에 대해 평면 경로(`assets_dir/filename`)에 파일이 남아 있으면 `asset_path(item)`(신규 계산 경로)로 이동. 이미 이전됐으면(평면 위치에 파일 없음) 스킵 — 멱등.
- `collection_icon(name) -> str | None`: `all_display_items()`를 순회해 해당 컬렉션의 첫 항목 id 반환(없으면 None).

## 4. 등록 파이프라인 (`fetch.py`)

`_finalize_asset`이 최종 파일을 쓰는 대상을 `library.assets_dir`(평면) → `library.collection_dir("")`(미분류 폴더)로 변경. 새로 등록된 항목은 항상 미분류로 시작해 사용자가 이후 우클릭으로 컬렉션을 지정하는 기존 흐름과 일치한다. 임시 다운로드 파일(`_dl*`, `_cp*`, `_pb*`)은 즉시 소비·삭제되므로 계속 `assets_dir` 루트에 둬도 무방(변경 불필요).

## 5. PickerApi (`picker/window.py`)

`get_state()`의 `collections` 필드를 `list[str]` → `list[{name, icon}]`로 변경. `icon`은 `collection_icon()`이 반환한 item id를 `asset_server.url_for()`로 변환한 URL, 없으면 `null`.

## 6. UI (`picker/ui/*`)

- `app.js`: `state.collections`가 객체 배열이 됨. `renderRail()`이 `icon`이 있으면 `<img>`(원형, `object-fit: cover`)를, 없으면 기존 텍스트(이름 앞 2글자)를 렌더. `inCollection()` 등 필터 로직은 `col.name` 문자열 비교로 변경 없음.
- `app.css`: `#rail button`에 `overflow: hidden`, 내부 `img`에 `border-radius: 50%; object-fit: cover; width/height: 100%`.
- `mock()`: 아이콘 있는/없는 컬렉션 혼합 데이터로 갱신(브라우저 미리보기용).

## 7. 예외 처리

| 상황 | 처리 |
|---|---|
| `set_collection`에서 파일 이동 실패(OSError) | 메타데이터도 변경하지 않고 반환 — 컬렉션·파일 위치 불일치 방지 |
| 마이그레이션 중 개별 파일 이동 실패 | 해당 항목만 스킵(다음 로드 시 재시도), 앱 시작 막지 않음 |
| 컬렉션명에 경로 금지 문자 | `_slug()`가 치환 |
| 대표 아이콘 후보 없음(빈 컬렉션) | `icon: null` → 프런트가 텍스트 폴백 |

## 8. 테스트

`library.py`: `_slug` 규칙, `asset_path`가 컬렉션 하위 폴더를 가리키는지, `set_collection`이 실제 파일을 이동시키는지, 이동 실패 시 상태 불변, 마이그레이션이 평면 파일을 옮기고 멱등인지, `collection_icon`이 등록 항목·폴더 스캔 항목 모두에서 찾는지 및 빈 컬렉션에 None. `fetch.py`: 신규 등록이 `_uncategorized/` 아래에 쓰이는지(기존 테스트는 전부 `lib.asset_path(item)` 경유라 무변경으로 통과, `test_library.py`의 `put_asset` 헬퍼만 새 위치에 쓰도록 수정). 기존 pytest 79개 회귀 없이.

## 9. MVP 제외 (P2+)

컬렉션 이름 변경 시 하위 폴더 rename(현재는 이동으로 충분) / 빈 폴더 자동 정리 / 대표 아이콘 수동 지정 / 최다사용 기준 아이콘 로테이션.

## 10. 버전

v2.5.0.
