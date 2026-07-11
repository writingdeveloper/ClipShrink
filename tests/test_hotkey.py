"""hotkey 모듈의 순수 부분 테스트 (스레드/Win32 등록은 수동 검증)."""

from notro_app import hotkey


def test_choices_have_label_mod_vk():
    for key, (mods, vk, label) in hotkey.HOTKEY_CHOICES.items():
        assert mods and vk and label
        assert key == key.lower()


def test_default_combo_is_ctrl_shift_e():
    assert "ctrl+shift+e" in hotkey.HOTKEY_CHOICES
    mods, vk, label = hotkey.HOTKEY_CHOICES["ctrl+shift+e"]
    assert mods == hotkey.MOD_CONTROL | hotkey.MOD_SHIFT
    assert vk == 0x45  # 'E'
    assert label == "Ctrl+Shift+E"


def test_label_for_off_and_unknown():
    assert hotkey.label_for(hotkey.HOTKEY_OFF)
    assert hotkey.label_for("nope") == hotkey.label_for(hotkey.HOTKEY_OFF)
