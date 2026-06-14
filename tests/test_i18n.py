"""Tests for ClipShrink's i18n layer."""

import clipshrink


def test_all_languages_have_same_keys():
    keys = set(clipshrink.STRINGS["en"])
    for lang, table in clipshrink.STRINGS.items():
        assert set(table) == keys, f"{lang} keys differ: {set(table) ^ keys}"


def test_supported_langs_match_strings_table():
    assert set(clipshrink.SUPPORTED_LANGS) == set(clipshrink.STRINGS)


def test_tr_returns_localized_string():
    clipshrink.current_lang = "ko"
    assert clipshrink.tr("quit") == "종료"
    clipshrink.current_lang = "ja"
    assert clipshrink.tr("quit") == "終了"


def test_tr_formats_named_fields():
    clipshrink.current_lang = "en"
    msg = clipshrink.tr("notify_compress_done", orig=2.0, new=1.0, pct=50, fmt="WEBP")
    assert "WEBP" in msg and "50" in msg


def test_tr_unknown_key_returns_key():
    clipshrink.current_lang = "en"
    assert clipshrink.tr("__missing__") == "__missing__"


def test_set_language_explicit_and_invalid():
    clipshrink.set_language("ja")
    assert clipshrink.current_lang == "ja"
    clipshrink.set_language("nope")
    assert clipshrink.current_lang == "en"


def test_set_language_auto_resolves_to_supported():
    clipshrink.set_language("auto")
    assert clipshrink.current_lang in clipshrink.SUPPORTED_LANGS
