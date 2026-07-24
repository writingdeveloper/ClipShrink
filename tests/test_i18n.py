"""Tests for Notro's i18n layer."""

from notro_app import i18n


def test_all_languages_have_same_keys():
    keys = set(i18n.STRINGS["en"])
    for lang, table in i18n.STRINGS.items():
        assert set(table) == keys, f"{lang} keys differ: {set(table) ^ keys}"


def test_supported_langs_match_strings_table():
    assert set(i18n.SUPPORTED_LANGS) == set(i18n.STRINGS)


def test_tr_returns_localized_string():
    i18n.current_lang = "ko"
    assert i18n.tr("quit") == "종료"
    i18n.current_lang = "ja"
    assert i18n.tr("quit") == "終了"


def test_tr_formats_named_fields():
    i18n.current_lang = "en"
    msg = i18n.tr("notify_compress_done", orig=2.0, new=1.0, pct=50, fmt="WEBP")
    assert "WEBP" in msg and "50" in msg


def test_tr_unknown_key_returns_key():
    i18n.current_lang = "en"
    assert i18n.tr("__missing__") == "__missing__"


def test_set_language_explicit_and_invalid():
    i18n.set_language("ja")
    assert i18n.current_lang == "ja"
    i18n.set_language("nope")
    assert i18n.current_lang == "en"


def test_set_language_auto_resolves_to_supported():
    i18n.set_language("auto")
    assert i18n.current_lang in i18n.SUPPORTED_LANGS


def test_video_keys_exist_in_all_languages():
    keys = ["video_confirm_title", "video_meta", "video_estimate", "video_warn_quality",
            "video_need_ffmpeg", "video_btn_compress", "video_btn_cancel", "video_btn_close",
            "video_downloading", "video_encoding", "video_done",
            "video_fail_toobig", "video_fail_download", "video_fail_encode"]
    for lang in i18n.SUPPORTED_LANGS:
        for k in keys:
            assert k in i18n.STRINGS[lang], f"{lang} missing {k}"


def test_video_placeholders_match_across_languages():
    import re
    def ph(s):
        return set(re.findall(r"\{(\w+)", s))
    for k in ("video_meta", "video_estimate", "video_need_ffmpeg",
              "video_downloading", "video_encoding", "video_done", "video_fail_toobig"):
        ref = ph(i18n.STRINGS["en"][k])
        for lang in i18n.SUPPORTED_LANGS:
            assert ph(i18n.STRINGS[lang][k]) == ref, f"{lang}/{k}"


CAPTURE_KEYS = {
    "picker_capture_add", "picker_capture_saved", "picker_capture_duplicate",
    "picker_capture_no_image", "picker_capture_read_error",
    "picker_capture_register_error", "picker_capture_collection",
    "picker_auto_capture", "picker_auto_capture_note",
    "notify_capture_save_fail", "picker_settings_title",
    "picker_folders_subtitle", "picker_drop_partial", "picker_drop_failed",
}


def test_capture_keys_exist_in_all_languages():
    """한 언어에서 캡처 UI가 키 이름 그대로 노출되는 회귀를 잡는다."""
    for lang in i18n.SUPPORTED_LANGS:
        assert CAPTURE_KEYS <= set(i18n.STRINGS[lang])
