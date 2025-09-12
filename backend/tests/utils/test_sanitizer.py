import pytest
import re

sanitizer = pytest.importorskip("utils.sanitizer", reason="sanitizer module not found")


def _strip_tags(s: str) -> str:
    # helper used to assert tags removed
    return re.sub(r"<[^>]+>", "", s).strip()


def test_sanitizer_removes_script_and_trims():
    """
    Ensure sanitizer removes obvious script tags and trims whitespace.
    The exact output may vary by implementation; assert that script tags are removed
    and that the main text remains.
    """
    sample = "<script>alert(1)</script>\n  Hello <b>World</b>   "
    if hasattr(sanitizer, "sanitize"):
        out = sanitizer.sanitize(sample)
    elif hasattr(sanitizer, "clean"):
        out = sanitizer.clean(sample)
    else:
        pytest.skip("No sanitize/clean function in utils.sanitizer")

    assert isinstance(out, str)
    # script tag removed
    assert "<script" not in out.lower()
    # basic text preserved
    assert "Hello" in out
    # whitespace trimmed
    assert out == out.strip()