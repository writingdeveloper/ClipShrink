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
