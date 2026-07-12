# -*- coding: utf-8 -*-
from notro_app.video import VideoMeta, parse_ffmpeg_info, EncodePlan, plan_encode, build_args, parse_progress
from notro_app.video_window import fmt_dur, fmt_size
import notro_app.video as video_mod

SAMPLE = """ffmpeg version 7.1 Copyright (c) 2000-2024
  Duration: 00:01:12.34, start: 0.000000, bitrate: 5842 kb/s
  Stream #0:0[0x1](und): Video: h264 (High) (avc1 / 0x31637661), yuv420p(tv, bt709), 1920x1080 [SAR 1:1 DAR 16:9], 5701 kb/s, 59.94 fps, 60 tbr, 60k tbn (default)
  Stream #0:1[0x2](und): Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 128 kb/s (default)
At least one output file must be specified
"""

SILENT = """  Duration: 00:00:30.00, start: 0.000000, bitrate: 3000 kb/s
  Stream #0:0: Video: h264 (High), yuv420p, 1280x720 [SAR 1:1 DAR 16:9], 2900 kb/s, 30 fps, 30 tbr, 15360 tbn
"""

# mp4/mov는 mjpeg 표지 이미지("(attached pic)")를 실제 영상보다 먼저 나열하는 경우가 흔하다.
COVER_ART = """ffmpeg version 7.1 Copyright (c) 2000-2024
  Duration: 00:01:12.34, start: 0.000000, bitrate: 5842 kb/s
  Stream #0:0[0x1]: Video: mjpeg (Baseline), yuvj420p(pc), 320x240 [SAR 1:1 DAR 4:3], 90k tbr, 90k tbn (attached pic)
  Stream #0:1[0x2](und): Video: h264 (High) (avc1 / 0x31637661), yuv420p, 1920x1080 [SAR 1:1 DAR 16:9], 5701 kb/s, 59.94 fps, 60 tbr
At least one output file must be specified
"""


def test_parses_duration_resolution_fps_audio():
    m = parse_ffmpeg_info(SAMPLE)
    assert m == VideoMeta(duration=72.34, width=1920, height=1080, fps=59.94, has_audio=True)


def test_parses_silent_video():
    m = parse_ffmpeg_info(SILENT)
    assert m.has_audio is False
    assert (m.width, m.height, m.fps) == (1280, 720, 30.0)


def test_returns_none_when_not_a_video():
    assert parse_ffmpeg_info("some random text") is None
    assert parse_ffmpeg_info("  Duration: 00:00:05.00\n  Stream #0:0: Audio: aac") is None


def test_skips_cover_art_stream_and_picks_real_video():
    # 표지 이미지(mjpeg, 320x240, attached pic)가 아니라 실제 영상(h264, 1920x1080)을 골라야 한다
    m = parse_ffmpeg_info(COVER_ART)
    assert (m.width, m.height, m.fps) == (1920, 1080, 59.94)


# plan_encode 테스트
MB = 1024 * 1024
LIMIT = int(10 * MB * 0.95)   # config.LIMIT_BYTES와 동일 (SAFETY 0.95)


def _meta(dur, w=1920, h=1080, fps=60.0, audio=True):
    return VideoMeta(duration=dur, width=w, height=h, fps=fps, has_audio=audio)


def test_short_clip_keeps_1080p():
    p = plan_encode(_meta(20), LIMIT)          # 20초 → 비디오 여유 충분
    assert p.height == 1080
    assert p.video_kbps >= 2500


def test_one_minute_clip_drops_to_720p30():
    p = plan_encode(_meta(60), LIMIT)          # 60초 → 약 1230kbps
    assert p.height == 720
    assert p.fps == 30                         # 60fps를 감당할 여유(1000*1.5)가 없다
    assert p.warn is False                     # 경고는 480p 이하로 떨어질 때만


def test_long_clip_drops_to_480p():
    p = plan_encode(_meta(120), LIMIT)         # 2분 → 약 568kbps
    assert p.height == 480
    assert p.warn is True


def test_too_long_returns_none():
    assert plan_encode(_meta(600), LIMIT) is None   # 10분 → 하한 미달


def test_never_upscales_beyond_source():
    p = plan_encode(_meta(20, w=640, h=360, fps=30.0), LIMIT)
    assert p.height == 360                     # 원본이 360p면 그대로
    assert p.warn is False                     # 축소가 아니므로 경고 없음


def test_silent_video_has_no_audio_budget():
    p = plan_encode(_meta(60, audio=False), LIMIT)
    assert p.audio_kbps == 0


def test_zero_duration_returns_none():
    assert plan_encode(_meta(0), LIMIT) is None


# --- 리뷰 발견사항 회귀 테스트 -------------------------------------------

def test_source_below_smallest_rung_encodes_at_native_resolution():
    # 240p는 사다리의 가장 작은 rung(360p)보다도 작다 → 업스케일 금지 규칙 때문에
    # 모든 rung이 스킵된다. 예산(약 2560kbps)은 하한(300)을 훌쩍 넘으므로
    # None("못 줄임")이 아니라 원본 해상도(240p) 그대로 계획해야 한다.
    p = plan_encode(_meta(30, w=320, h=240), LIMIT)
    assert p is not None
    assert p.height == 240                      # 원본 해상도 그대로 (업스케일 아님)
    assert p.warn is False                       # 축소가 아니므로 경고 없음
    assert p.fps == 60                           # 예산이 넉넉해 60fps 유지


def test_source_below_smallest_rung_still_none_under_floor():
    # 원본이 사다리보다 작아도(240p) 예산이 하한(300kbps) 미만이면 여전히 None이어야
    # 한다 — 네이티브 해상도 폴백이 하한 검사를 우회하면 안 된다.
    p = plan_encode(_meta(600, w=320, h=240), LIMIT)   # 10분 → 하한 미달
    assert p is None


def test_source_below_smallest_rung_with_odd_height_yields_even_plan_height():
    # 크롭된 화면 녹화 등은 높이가 홀수일 수 있다(예: 321px). 이 소스가 사다리의
    # 가장 작은 rung(360p)보다도 작으면 네이티브 해상도 폴백을 타는데, build_args의
    # `-vf scale=-2:{height}`는 "-2"로 가로만 짝수로 맞추고 세로(height)는 그대로
    # 통과시키므로 libx264가 홀수 높이를 거부한다. plan.height는 항상 짝수여야 한다.
    p = plan_encode(_meta(30, w=480, h=321), LIMIT)
    assert p is not None
    assert p.height % 2 == 0
    assert p.height == 320                       # 업스케일 금지 유지 → 320으로 내림
    # 321 -> 320은 짝수 보정(1px)일 뿐 "진짜 축소"가 아니다. 원본(321)도 짝수로
    # 내려서 비교해야 320 < 320(거짓)이 되어 warn=False가 나온다 — 그렇지 않으면
    # (320 < 321) 홀수 보정만으로 스푸리어스하게 "화질 저하" 경고가 뜬다.
    assert p.warn is False


def test_boundary_at_exactly_300_kbps_still_plans_360p():
    # video_kbps가 "정확히" 하한(300)이면 미달이 아니다 — 360p 계획이 나와야 한다.
    # duration=100, limit_bytes=4,950,000 → total_kbps=396.0, audio=96 → video_kbps=300
    p = plan_encode(_meta(100), 4_950_000)
    assert p is not None
    assert p.height == 360
    assert p.video_kbps == 300


# --- parse_progress와 build_args 테스트 -----------------------------------------------

def test_parse_progress_reads_time():
    line = "frame=  360 fps= 30 q=28.0 size=    2048KiB time=00:00:12.34 bitrate=1360.0kbits/s"
    assert parse_progress(line) == 12.34


def test_parse_progress_ignores_other_lines():
    assert parse_progress("Stream mapping:") is None


def test_build_args_uses_plan_and_outputs_mp4():
    plan = EncodePlan(height=720, fps=30, video_kbps=1200, audio_kbps=96, warn=False)
    args = build_args("ffmpeg.exe", "in.mkv", plan, "out.mp4")
    joined = " ".join(args)
    assert args[0] == "ffmpeg.exe"
    assert "-c:v libx264" in joined
    assert "-b:v 1200k" in joined
    assert "-maxrate 1440k" in joined          # 1200 * 1.2
    assert "-bufsize 2400k" in joined          # 1200 * 2
    assert "scale=-2:720" in joined
    assert "-r 30" in joined
    assert "-b:a 96k" in joined
    assert "+faststart" in joined
    assert args[-1] == "out.mp4"


def test_build_args_drops_audio_when_silent():
    plan = EncodePlan(height=480, fps=30, video_kbps=600, audio_kbps=0, warn=True)
    args = build_args("ffmpeg.exe", "in.mp4", plan, "out.mp4")
    assert "-an" in args
    assert "-c:a" not in args


# --- probe / encode (subprocess를 가짜로 주입) ------------------------------

def test_probe_parses_stderr_from_subprocess(monkeypatch):
    class FakeCompleted:
        stderr = SAMPLE

    monkeypatch.setattr(video_mod.subprocess, "run", lambda *a, **k: FakeCompleted())
    m = video_mod.probe("ffmpeg.exe", "clip.mp4")
    assert m.height == 1080 and m.has_audio is True


def test_probe_returns_none_when_ffmpeg_missing(monkeypatch):
    def boom(*a, **k):
        raise OSError("not found")

    monkeypatch.setattr(video_mod.subprocess, "run", boom)
    assert video_mod.probe("ffmpeg.exe", "clip.mp4") is None


def _fake_encode_proc(lines, returncode=0):
    """encode()가 실제로 건드리는 Popen 표면만 흉내낸다: stderr 이터러블 +
    wait/poll/terminate. 진짜 subprocess처럼 wait()나 terminate() 이후에는
    poll()이 더는 None을 돌려주지 않는다(그래야 encode()의 finally에서
    이미 끝난 프로세스에 terminate()를 또 걸지 않는지도 자연스럽게 맞물린다)."""

    class _FakeProc:
        def __init__(self):
            self.stderr = lines
            self.terminated = False
            self._waited = False

        def wait(self):
            self._waited = True
            return returncode

        def poll(self):
            return returncode if (self._waited or self.terminated) else None

        def terminate(self):
            self.terminated = True

    return _FakeProc()


def test_encode_reports_progress_via_callback(monkeypatch, tmp_path):
    lines = [
        "frame=  1 fps=0.0 q=0.0 size=N/A time=00:00:01.00 bitrate=N/A\n",
        "frame= 75 fps=30 q=28.0 size=100KiB time=00:00:02.50 bitrate=300kbits/s\n",
        "Stream mapping:\n",              # time=이 없는 줄은 무시되어야 한다
    ]
    fake = _fake_encode_proc(lines, returncode=0)
    monkeypatch.setattr(video_mod.subprocess, "Popen", lambda *a, **k: fake)
    dest = tmp_path / "out.mp4"
    dest.write_bytes(b"x")                # ffmpeg가 결과물을 만들어 놓은 상태를 흉내낸다

    seen = []
    plan = EncodePlan(height=480, fps=30, video_kbps=500, audio_kbps=96, warn=True)
    ok = video_mod.encode("ffmpeg.exe", "in.mp4", plan, str(dest), on_progress=seen.append)

    assert ok is True
    assert seen == [1.0, 2.5]
    assert fake not in video_mod._ACTIVE          # 성공 경로에서도 등록 해제된다


def test_encode_cancel_terminates_process_and_returns_false(monkeypatch, tmp_path):
    lines = [
        "frame=  1 time=00:00:01.00 bitrate=N/A\n",
        "frame=  2 time=00:00:02.00 bitrate=N/A\n",
        "frame=  3 time=00:00:03.00 bitrate=N/A\n",
    ]
    fake = _fake_encode_proc(lines, returncode=0)
    monkeypatch.setattr(video_mod.subprocess, "Popen", lambda *a, **k: fake)
    dest = tmp_path / "out.mp4"
    dest.write_bytes(b"x")                # 취소 판단과 무관해야 함을 보이려고 파일도 만들어 둔다

    calls = {"n": 0}

    def should_cancel():
        calls["n"] += 1
        return calls["n"] >= 2            # 두 번째 줄 처리 직전에 취소 신호를 보낸다

    seen = []
    plan = EncodePlan(height=480, fps=30, video_kbps=500, audio_kbps=96, warn=True)
    ok = video_mod.encode("ffmpeg.exe", "in.mp4", plan, str(dest),
                          on_progress=seen.append, should_cancel=should_cancel)

    assert ok is False                    # 취소되면 절대 True를 돌려주지 않는다
    assert fake.terminated is True        # 프로세스가 실제로 종료 요청을 받았다
    assert seen == [1.0]                  # 취소 신호 이후 줄(2, 3번째)은 처리되지 않는다
    assert fake not in video_mod._ACTIVE  # 취소 경로에서도 등록 해제된다


def test_encode_false_when_dest_missing_even_if_exit_zero(monkeypatch, tmp_path):
    fake = _fake_encode_proc([], returncode=0)
    monkeypatch.setattr(video_mod.subprocess, "Popen", lambda *a, **k: fake)
    dest = tmp_path / "missing.mp4"       # ffmpeg가 결과 파일을 만들지 못한 상태

    plan = EncodePlan(height=480, fps=30, video_kbps=500, audio_kbps=96, warn=True)
    ok = video_mod.encode("ffmpeg.exe", "in.mp4", plan, str(dest))

    assert ok is False                    # 종료 코드가 0이어도 파일이 없으면 실패
    assert fake not in video_mod._ACTIVE  # 실패 경로에서도 등록 해제된다


def test_encode_false_when_ffmpeg_exits_nonzero(monkeypatch, tmp_path):
    fake = _fake_encode_proc([], returncode=1)
    monkeypatch.setattr(video_mod.subprocess, "Popen", lambda *a, **k: fake)
    dest = tmp_path / "out.mp4"
    dest.write_bytes(b"x")                # 파일이 있어도 종료 코드가 실패면 실패

    plan = EncodePlan(height=480, fps=30, video_kbps=500, audio_kbps=96, warn=True)
    ok = video_mod.encode("ffmpeg.exe", "in.mp4", plan, str(dest))

    assert ok is False
    assert fake not in video_mod._ACTIVE  # 실패 경로에서도 등록 해제된다


# --- terminate_all (앱 종료 시 고아 ffmpeg 프로세스 방지) --------------------

def test_terminate_all_kills_tracked_processes():
    class FakeProc:
        def __init__(self):
            self.killed = False

        def poll(self):
            return None            # 아직 살아 있다

        def terminate(self):
            self.killed = True

    p = FakeProc()
    video_mod._ACTIVE.add(p)
    try:
        video_mod.terminate_all()
        assert p.killed is True
        assert p not in video_mod._ACTIVE
    finally:
        video_mod._ACTIVE.discard(p)


# --- video_window 포매터 (순수 함수) ----------------------------------------

def test_fmt_size():
    assert fmt_size(9_961_472) == "9.5MB"
    assert fmt_size(512) == "0.0MB"


def test_fmt_dur():
    assert fmt_dur(72.34) == "1:12"
    assert fmt_dur(5) == "0:05"
    assert fmt_dur(3661) == "61:01"
