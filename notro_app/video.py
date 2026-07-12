# -*- coding: utf-8 -*-
"""비디오 압축: ffmpeg 출력 파싱 · 인코딩 계획(순수 함수) · 실행.

순수 계산(파싱·계획)과 부수효과(subprocess)를 분리한다 — compress.py와 같은 관례.
ffprobe는 쓰지 않는다: 내려받는 imageio-ffmpeg wheel에는 ffmpeg만 들어 있고,
ffprobe 하나 때문에 100MB+ 빌드를 받을 이유가 없어 `ffmpeg -i`의 stderr를 파싱한다.
"""

from __future__ import annotations

import os
import re
import subprocess
import threading
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
_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")


def parse_ffmpeg_info(stderr: str) -> VideoMeta | None:
    """`ffmpeg -i <file>`이 stderr로 뱉는 정보에서 메타데이터를 뽑는다.
    비디오 스트림이나 길이를 못 찾으면 None(비디오가 아니거나 손상)."""
    d = _DUR_RE.search(stderr)
    if not d:
        return None
    duration = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3))
    if duration <= 0:
        return None

    def _line(m: re.Match[str]) -> str:
        # 비디오 스트림 줄만 잘라낸다 (다른 줄의 숫자와 섞이지 않게)
        line_end = stderr.find("\n", m.start())
        return stderr[m.start():line_end if line_end != -1 else len(stderr)]

    # mp4/mov는 실제 영상보다 먼저 mjpeg 표지 이미지("(attached pic)")를 비디오
    # 스트림으로 올리는 경우가 흔하다. 정지 이미지일 뿐이므로 후보에서 제외한다.
    streams = [m for m in _VIDEO_RE.finditer(stderr) if "(attached pic)" not in _line(m)]
    if not streams:
        return None

    # 실제 영상은 fps를 보고하지만 표지 이미지는 그렇지 않으므로, fps가 있는 스트림을
    # 우선한다 (없으면 남은 후보 중 첫 번째).
    v = next((m for m in streams if _FPS_RE.search(_line(m))), streams[0])
    width, height = int(v.group(1)), int(v.group(2))

    # fps는 선택된 비디오 스트림 줄 안에서만 찾는다
    f = _FPS_RE.search(_line(v))
    fps = float(f.group(1)) if f else 30.0

    return VideoMeta(duration, width, height, fps, bool(_AUDIO_RE.search(stderr)))


AUDIO_KBPS = 96          # AAC 고정
MIN_VIDEO_KBPS = 300     # 이 아래로는 내려가지 않는다 (360p 하한)

# 해상도 사다리: (높이, 30fps 기준 최소 비디오 kbps)
# 주의: 높이 내림차순으로 정렬되어 있어야 한다 — plan_encode의 루프가 "처음으로
# 맞는(=가장 큰) rung"에서 곧바로 return하므로, 순서가 깨지면 예산이 감당할 수 있는
# 더 높은 해상도가 있어도 낮은 해상도가 먼저 선택되는 등 화질 선택이 조용히 잘못된다.
_LADDER = ((1080, 2500), (720, 1000), (480, 500), (360, MIN_VIDEO_KBPS))


@dataclass
class EncodePlan:
    height: int
    fps: int
    video_kbps: int
    audio_kbps: int
    warn: bool        # 원본보다 작아졌고 480p 이하 → 화질 저하 경고


def plan_encode(meta: VideoMeta, limit_bytes: int) -> EncodePlan | None:
    """목표 용량에 맞는 인코딩 계획. 하한(360p/300kbps) 밑이면 None = '못 줄임'.

    60fps는 같은 체감 화질에 약 1.5배 비트레이트를 먹는다 — 여유가 없으면 30fps로 낮춘다.
    원본보다 해상도를 키우지 않는다. 원본이 사다리의 가장 작은 rung(360p)보다도 작으면
    (예: 240p) 모든 rung이 업스케일 금지 규칙에 걸려 스킵되므로, 예산이 하한을 넘길 때는
    원본 해상도 그대로 계획한다 — None은 "예산이 하한 미달"일 때만 쓴다.
    """
    if meta.duration <= 0:
        return None
    audio = AUDIO_KBPS if meta.has_audio else 0
    total_kbps = limit_bytes * 8 / meta.duration / 1000
    video_kbps = int(total_kbps - audio)
    if video_kbps < MIN_VIDEO_KBPS:
        return None

    def _plan(height: int, need: int) -> EncodePlan:
        # build_args의 `-vf scale=-2:{height}`는 "-2"로 가로만 짝수로 맞추고 세로는
        # 그대로 통과시킨다. 사다리 rung(1080/720/480/360)은 이미 짝수라 영향 없지만,
        # 아래 네이티브 해상도 폴백은 원본의 홀수 높이(예: 크롭된 화면 녹화)를 그대로
        # 넘길 수 있어 libx264가 거부한다 — 항상 짝수로 내림(업스케일 금지 유지).
        height -= height % 2
        fps = int(round(meta.fps))
        if meta.fps > 30 and video_kbps < need * 1.5:
            fps = 30              # 60fps를 감당할 여유가 없다
        # warn은 "진짜 축소"에만 켜야 한다. height는 위에서 이미 짝수로 내렸으니
        # 원본(meta.height)도 짝수로 내려 같은 기준으로 비교한다 — 그렇지 않으면
        # 네이티브 폴백에서 홀수 높이를 1px 보정한 것만으로(예: 321 -> 320) 실제
        # 축소가 아닌데도 320 < 321이 참이 되어 warn=True로 잘못 켜진다.
        even_source_height = meta.height - meta.height % 2
        warn = height < even_source_height and height <= 480
        return EncodePlan(height, fps, video_kbps, audio, warn)

    for height, need in _LADDER:
        if height > meta.height:      # 원본보다 키우지 않는다
            continue
        if video_kbps >= need:
            return _plan(height, need)

    # 여기 도달했다는 건 원본이 360p보다도 작다는 뜻이다: meta.height >= 360이었다면
    # 사다리의 마지막 rung(360, MIN_VIDEO_KBPS)은 절대 스킵되지 않고, 그 need는 위에서
    # 이미 통과했으므로 루프 안에서 반드시 return됐을 것이다. 예산은 이미 하한을
    # 넘겼으니 "못 줄임"이 아니라 원본 해상도 그대로 인코딩한다(업스케일이 아니므로
    # warn=False). fps 판단 기준은 정의된 rung이 없으므로 사다리 최하한 기준을 쓴다.
    return _plan(meta.height, MIN_VIDEO_KBPS)


def retry_plan(plan: EncodePlan) -> EncodePlan | None:
    """1-pass 오차로 결과물이 여전히 용량 한도를 넘을 때, 비트레이트를 20% 낮춰 한
    번 더 인코딩할 계획을 만든다. 하한(MIN_VIDEO_KBPS)은 "이 밑으로는 절대 내려가지
    않는다"는 이 앱의 화질 보장 그 자체이므로, 낮춘 비트레이트가 하한 밑으로
    떨어지면 재시도 계획 대신 None을 돌려준다.

    주의: EncodePlan.video_kbps는 선택된 rung에서 "쓸 수 있는 전체 예산"이지
    rung의 최소치가 아니다. 그래서 plan_encode가 300~374kbps 사이(>= MIN_VIDEO_KBPS를
    통과해 360p로 계획됨)로 계획한 클립은, 아무 클램프 없이 ×0.8만 적용하면
    244~299kbps로 떨어져 하한을 조용히 어긴다. 호출자는 None을 "재시도해도 하한을
    지키며 못 줄인다"로 해석해 정직하게 실패 처리해야 한다(하한을 어기며 억지로
    인코딩하면 안 된다).
    """
    reduced = int(plan.video_kbps * 0.8)
    if reduced < MIN_VIDEO_KBPS:
        return None
    return EncodePlan(plan.height, plan.fps, reduced, plan.audio_kbps, plan.warn)


def parse_progress(line: str) -> float | None:
    """ffmpeg 진행 로그의 `time=00:00:12.34` → 12.34초. 없으면 None."""
    m = _TIME_RE.search(line)
    if not m:
        return None
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def build_args(ffmpeg: str, src: str, plan: EncodePlan, dest: str) -> list[str]:
    """ffmpeg 인자 조립 (순수 함수 — 테스트 가능).

    출력은 항상 mp4(H.264+AAC): Discord 인라인 재생·미리보기 호환이 가장 좋다.
    scale=-2:{h}로 가로를 짝수로 맞추고, +faststart로 미리보기를 살린다.
    """
    v = plan.video_kbps
    args = [
        ffmpeg, "-hide_banner", "-y", "-i", src,
        "-c:v", "libx264", "-preset", "veryfast",
        "-b:v", f"{v}k", "-maxrate", f"{int(v * 1.2)}k", "-bufsize", f"{v * 2}k",
        "-vf", f"scale=-2:{plan.height}",
        "-r", str(plan.fps),
    ]
    if plan.audio_kbps:
        args += ["-c:a", "aac", "-b:a", f"{plan.audio_kbps}k"]
    else:
        args += ["-an"]
    args += ["-movflags", "+faststart", dest]
    return args


CREATE_NO_WINDOW = 0x08000000   # 콘솔 창이 뜨지 않게

_ACTIVE = set()            # 실행 중인 ffmpeg 프로세스
_ACTIVE_LOCK = threading.Lock()


def terminate_all() -> None:
    """앱 종료 시 호출 — 인코딩 중이던 ffmpeg가 고아 프로세스로 남지 않게 한다."""
    with _ACTIVE_LOCK:
        procs = list(_ACTIVE)
        _ACTIVE.clear()
    for p in procs:
        try:
            if p.poll() is None:
                p.terminate()
        except Exception:
            pass


def probe(ffmpeg: str, path: str) -> VideoMeta | None:
    """`ffmpeg -i`로 메타데이터를 읽는다. 출력 파일이 없어 종료 코드는 항상 1이지만,
    필요한 정보는 stderr에 이미 다 나와 있다."""
    try:
        p = subprocess.run(
            [ffmpeg, "-hide_banner", "-i", path],
            capture_output=True, text=True, errors="replace",
            creationflags=CREATE_NO_WINDOW, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_ffmpeg_info(p.stderr or "")


def encode(ffmpeg: str, src: str, plan: EncodePlan, dest: str,
           on_progress=None, should_cancel=None) -> bool:
    """한 번의 인코딩만 책임진다 (재시도 판단은 호출자 몫).
    on_progress(seconds_done) 콜백, should_cancel() -> True면 즉시 중단."""
    try:
        proc = subprocess.Popen(
            build_args(ffmpeg, src, plan, dest),
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True, errors="replace", creationflags=CREATE_NO_WINDOW,
        )
    except OSError:
        return False
    with _ACTIVE_LOCK:
        _ACTIVE.add(proc)
    try:
        for line in proc.stderr:
            if should_cancel and should_cancel():
                proc.terminate()
                return False
            t = parse_progress(line)
            if t is not None and on_progress:
                on_progress(t)
        return proc.wait() == 0 and os.path.exists(dest)
    finally:
        if proc.poll() is None:
            proc.terminate()
        with _ACTIVE_LOCK:
            _ACTIVE.discard(proc)
