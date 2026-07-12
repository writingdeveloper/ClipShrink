# -*- coding: utf-8 -*-
from notro_app.video import VideoMeta, parse_ffmpeg_info, EncodePlan, plan_encode

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
