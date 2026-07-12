# -*- coding: utf-8 -*-
from notro_app.video import VideoMeta, parse_ffmpeg_info

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
