# -*- coding: utf-8 -*-
"""비디오 압축: ffmpeg 출력 파싱 · 인코딩 계획(순수 함수) · 실행.

순수 계산(파싱·계획)과 부수효과(subprocess)를 분리한다 — compress.py와 같은 관례.
ffprobe는 쓰지 않는다: 내려받는 imageio-ffmpeg wheel에는 ffmpeg만 들어 있고,
ffprobe 하나 때문에 100MB+ 빌드를 받을 이유가 없어 `ffmpeg -i`의 stderr를 파싱한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class VideoMeta:
    duration: float   # 초
    width: int
    height: int
    fps: float
    has_audio: bool


_DUR_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_VIDEO_RE = re.compile(r"Video:[^\n]*?\b(\d{2,5})x(\d{2,5})\b")
_FPS_RE = re.compile(r"([\d.]+)\s*fps")
_AUDIO_RE = re.compile(r"Stream #\d+:\d+[^\n]*: Audio:")


def parse_ffmpeg_info(stderr: str) -> VideoMeta | None:
    """`ffmpeg -i <file>`이 stderr로 뱉는 정보에서 메타데이터를 뽑는다.
    비디오 스트림이나 길이를 못 찾으면 None(비디오가 아니거나 손상)."""
    d = _DUR_RE.search(stderr)
    if not d:
        return None
    duration = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3))
    if duration <= 0:
        return None

    v = _VIDEO_RE.search(stderr)
    if not v:
        return None
    width, height = int(v.group(1)), int(v.group(2))

    # fps는 비디오 스트림 줄 안에서만 찾는다 (다른 줄의 숫자와 섞이지 않게)
    line_end = stderr.find("\n", v.start())
    line = stderr[v.start():line_end if line_end != -1 else len(stderr)]
    f = _FPS_RE.search(line)
    fps = float(f.group(1)) if f else 30.0

    return VideoMeta(duration, width, height, fps, bool(_AUDIO_RE.search(stderr)))
