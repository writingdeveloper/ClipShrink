# Notro v2.4 — 즐겨찾기 · 컬렉션 · 폴더 열기 설계

- 날짜: 2026-07-10
- 상태: 사용자 승인 완료
- 스코프: 피커에 즐겨찾기(Favorites), 컬렉션 구분(세로 바), 저장 폴더 열기 추가. 디스코드 이모지 피커의 즐겨찾기·서버별 구분을 Notro 방식으로 재현.

## 1. 배경

현재 피커는 상단 탭(emoji/sticker/gif) + 검색 + 최근 섹션 + 그리드 구조다. 라이브러리가 커지면(예: 미쿠 팩 64개) 자주 쓰는 항목 고정과 그룹 구분이 필요하다. 디스코드 피커의 ★Favorites와 서버별 이모지 세로 바를 참고해 즐겨찾기와 컬렉션을 추가한다. 저장 폴더(자산 캐시)를 직접 열 수단도 제공한다.

## 2. 확정 요구사항

| 항목 | 결정 |
|---|---|
| 즐겨찾기 | 항목별 `favorite` 플래그. 세로 바 ★ + 전체/폴더 볼 때 상단 Favorites 섹션 |
| 컬렉션 | 항목별 `collection` 문자열. 폴더 스캔 항목은 폴더명 자동, 등록 항목은 수동 태그(기본 "") |
| 세로 바 | ★즐겨찾기 / 전체 / 각 컬렉션(miku·폴더명…) — 상단 탭(타입)과 교차 필터 |
| 초기 데이터 | 기존 미쿠 등록 항목 전부(이모지 35 + 스티커 17 + GIF 12 = 64) → `collection="miku"` |
| 폴더 열기 | 트레이 "라이브러리 폴더 열기"(`%APPDATA%\Notro`) + 피커 설정(⚙) 버튼 |

## 3. 데이터 모델 변경 (`library.py`)

항목 dict에 두 필드 추가 (하위호환은 `_apply_lib`의 `setdefault`):

- `favorite: bool` (기본 False)
- `collection: str` (기본 "", 빈 문자열 = "전체")

`add_item(..., favorite=False, collection="")` 매개변수 추가. `scan_folders()`가 만드는 폴더 항목은 `collection = 폴더 basename`(자동).

신규 메서드:

- `toggle_favorite(item_id) -> bool` — favorite 반전, 저장, 새 값 반환
- `favorites() -> list[dict]` — favorite=True 항목 (등록 항목만; 폴더 항목은 영속 안 되므로 제외)
- `set_collection(item_id, name) -> None` — 등록 항목의 collection 설정
- `collections() -> list[str]` — 등록 항목의 distinct collection(빈 값 제외) + 폴더 basename 목록, 정렬

## 4. PickerApi (`picker/window.py`)

- `_display`에 `favorite`, `collection` 노출
- `get_state`에 `collections`(세로 바용 목록) 추가
- `toggle_favorite(item_id) -> {ok, favorite}`
- `set_collection(item_id, name) -> {ok}` (빈 문자열이면 "전체"로 이동)
- `open_data_dir() -> True` — `os.startfile(config.DATA_DIR)`

## 5. UI (`picker/ui/*`)

**레이아웃** — 왼쪽 세로 바(48px) 추가, 피커 폭 440→**500px**:

```
┌──┬──────────────────────────┐
│★ │ 검색바           +  ⚙   │
│전│ Emoji  Sticker  GIF      │
│체│──────────────────────────│
│mi│ ★ Favorites (전체/폴더시) │
│ku│ 🕐 최근 사용             │
│📁│ [그리드]                 │
└──┴──────────────────────────┘
```

- 세로 바 항목: ★즐겨찾기, 전체, 각 컬렉션. 클릭 시 `state.collection` 설정 후 재렌더.
- 필터: `filtered()`가 `type === tab && (collection view)`. ★뷰=favorite만, 전체=collection==="", 특정 컬렉션=collection===name (폴더 항목은 폴더명).
- Favorites 섹션: ★뷰가 아니고 검색 없을 때 상단에 favorite 항목 표시(최근 섹션 위).
- 우클릭 메뉴에 추가: "즐겨찾기 추가/제거"(토글), "컬렉션 이동…"(프롬프트로 이름 입력 또는 기존 선택; 등록 항목만).
- 셀 배지: favorite면 ★ 코너 배지.
- 설정(⚙) 모달에 "라이브러리 폴더 열기" 버튼.

## 6. 트레이 (`tray.py`)

기존 "출력 폴더 열기"(TEMP_DIR) 아래에 "라이브러리 폴더 열기"(`config.DATA_DIR`) 항목 추가. 기존 `os.startfile` 패턴 재사용.

## 7. 초기 데이터 마이그레이션

기존 미쿠 등록 항목(이모지/스티커/GIF, source_kind=local) 64개에 `collection="miku"` 부여. 일회성 스크립트로 `%APPDATA%\Notro\library.json`을 갱신(각 항목 name/keywords에 miku 포함 여부로 식별하거나, 현재 등록 항목 전체를 miku로 — 현재 라이브러리엔 미쿠만 있으므로 후자로 단순 처리하되, "miku" 키워드 보유 항목으로 한정).

## 8. i18n (5개 언어)

신규 키: `picker_ctx_favorite`(즐겨찾기 추가), `picker_ctx_unfavorite`(즐겨찾기 제거), `picker_ctx_collection`(컬렉션 이동…), `picker_col_all`(전체), `picker_col_favorites`(즐겨찾기), `picker_open_library`(라이브러리 폴더 열기), `open_library_folder`(트레이). en/ko 우선, ja·zh·es 포함.

## 9. 테스트

- `library.py`: `toggle_favorite`, `favorites`, `set_collection`, `collections`(폴더+등록 distinct), `add_item` 신규 매개변수, `_apply_lib` 하위호환(구항목 favorite/collection 기본값).
- 기존 pytest 회귀 없이.
- UI(세로 바·필터·우클릭)는 릴리스 전 수동 체크리스트.

## 10. 예외 처리

| 상황 | 처리 |
|---|---|
| 폴더 항목 즐겨찾기 시도 | 영속 불가 → 무시(등록 항목만 즐겨찾기) |
| collection 빈 문자열 | "전체"로 취급 |
| 컬렉션 이동 취소/빈 입력 | 변경 없음 |
| DATA_DIR 열기 실패 | 조용히 무시 |

## 11. MVP 제외 (P2+)

컬렉션별 커스텀 아이콘 업로드 / 컬렉션 순서 드래그 정렬 / 컬렉션 이름 변경·삭제 UI(초기엔 이동으로 충분) / 즐겨찾기 순서 정렬.

## 12. 버전

v2.4.0 — 즐겨찾기 + 컬렉션 + 폴더 열기.
