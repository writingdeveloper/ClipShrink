"""피커의 캡처 저장 UI 구조 계약."""

from html.parser import HTMLParser
from pathlib import Path


UI_DIR = Path(__file__).parents[1] / "notro_app" / "picker" / "ui"


class ElementCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def elements():
    parser = ElementCollector()
    parser.feed((UI_DIR / "index.html").read_text(encoding="utf-8"))
    return parser.elements


def test_capture_button_precedes_other_header_actions():
    """승인된 A안의 원클릭 버튼이 추가 메뉴 뒤로 숨는 회귀를 잡는다."""
    ids = [attrs.get("id") for tag, attrs in elements() if tag == "button"]
    capture = ids.index("btn-capture")
    assert capture < ids.index("btn-add") < ids.index("btn-settings")


def test_auto_capture_uses_native_checkbox_with_description():
    """설정이 접근 불가능한 커스텀 토글로 바뀌거나 설명이 빠지는 회귀를 잡는다."""
    by_id = {attrs.get("id"): (tag, attrs) for tag, attrs in elements()
             if attrs.get("id")}
    tag, attrs = by_id["st-auto-capture"]
    assert tag == "input" and attrs.get("type") == "checkbox"
    assert by_id["st-auto-capture-note"][0] == "p"
    assert by_id["st-folders-subtitle"][0] in {"h4", "p"}


def test_capture_button_is_a_real_button():
    by_id = {attrs.get("id"): (tag, attrs) for tag, attrs in elements()
             if attrs.get("id")}
    tag, attrs = by_id["btn-capture"]
    assert tag == "button"
    assert attrs.get("type") == "button"
