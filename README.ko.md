# ClipShrink

<p align="center">
  <img src="docs/icon.png" width="96" alt="ClipShrink 아이콘">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows-blue.svg" alt="Platform: Windows">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT">
</p>

<p align="center"><a href="README.md">English</a> | <b>한국어</b></p>

픽픽(PicPick) 등으로 캡처한 이미지가 디스코드 무료 업로드 한도(10MB)를 넘으면,
클립보드의 이미지를 **자동으로 압축**해서 <kbd>Ctrl</kbd>+<kbd>V</kbd>로 바로 업로드할 수 있게 해주는
트레이 상주 프로그램입니다.

## 동작 방식

1. 트레이에 상주하며 클립보드를 감시합니다.
2. 새 이미지가 복사되면 디스코드가 붙여넣기 시 변환하는 **PNG 기준 용량**을 계산합니다.
3. **10MB 이하면 아무것도 하지 않습니다.** (원본 그대로 붙여넣기 가능)
4. 초과하면 해상도를 유지한 채 WebP → JPEG 순으로 품질을 낮춰 9.5MB 이하로 압축하고,
   그래도 크면 해상도를 단계적으로 축소합니다.
5. 압축된 이미지는 **파일 형태**로 클립보드에 들어가며, 디스코드에서 <kbd>Ctrl</kbd>+<kbd>V</kbd> 하면
   파일로 업로드됩니다. (압축 완료 시 트레이 알림이 뜹니다)

> 픽픽이 폴더에 저장하는 원본 파일은 건드리지 않습니다. 클립보드만 교체합니다.

## 내려받기 & 실행 (권장)

[**Releases**](../../releases) 페이지에서 최신 `ClipShrink.exe`를 받아 실행하면 끝입니다.

- 트레이에 상주합니다. 아이콘 우클릭 → 감시 중지/시작, 최근 처리 내역,
  업로드 한도(10/50/500MB) 변경, 언어 변경, 폴더 열기, 자동 실행 켜기/끄기, 종료.
- **자동 시작은 기본 꺼짐(opt-in)** 입니다. 원하면 트레이 메뉴 →
  *"Windows 시작 시 자동 실행"* 을 직접 켜세요.
- 이미 실행 중이면 중복 실행되지 않습니다.

> ⚠️ 코드 서명이 없는 실행 파일이라 Windows SmartScreen이나 일부 백신이 경고/오탐할 수 있습니다.
> SmartScreen에서 *"추가 정보 → 실행"* 을 누르거나, 아래 "스크립트로 실행"으로 소스에서 직접 실행하세요.

## 스크립트로 실행 (개발용)

```sh
pip install -r requirements.txt
pythonw clipshrink.py
```

Windows + **Python 3.10 이상**이 필요합니다.

## EXE 직접 빌드

```sh
build.bat
```

결과물은 `dist\ClipShrink.exe`. (Python 3.10+ 필요, 스크립트가 PyInstaller를 설치합니다.)

## 설정 변경

`clipshrink.py` 상단의 설정 값을 수정하면 됩니다:

| 항목 | 기본값 | 설명 |
|---|---|---|
| `LIMIT_MB` | 10 | 기본 업로드 한도(MB) — 트레이 **업로드 한도** 메뉴에서 10/50/500 선택 가능 |
| `SAFETY` | 0.95 | 안전 마진 (9.5MB 목표) |
| `WEBP_QUALITIES` | 90~50 | WebP 품질 단계 |
| `MIN_SCALE` | 0.4 | 해상도 축소 하한 |

## 참고

- 압축 파일은 `%TEMP%\ClipShrink`에 저장되며 1일 지난 파일은 자동 삭제됩니다.
- 10MB가 넘는 이미지 **파일**을 복사한 경우(<kbd>Ctrl</kbd>+<kbd>C</kbd>)에도 동일하게 압축됩니다.
- **다국어:** English·한국어·日本語·中文(简体) 지원. Windows 언어를 자동 감지하며,
  트레이 **언어** 메뉴에서 언제든 바꿀 수 있습니다.

## 개발

```sh
pip install -r requirements-dev.txt
pytest
```

## 라이선스

[MIT](LICENSE).

> ClipShrink는 Discord와 무관한 비공식 도구이며, **Discord Inc.가 제휴/후원/승인한 프로젝트가
> 아닙니다.** "Discord"는 Discord Inc.의 상표입니다.
