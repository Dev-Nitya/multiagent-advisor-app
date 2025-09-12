import json
import pytest

from utils.jsonExtractor import extract_json_from_raw


def test_extract_json_from_code_block():
    raw = "Some text\n```json\n{\"market_verdict\": \"viable\", \"confidence_score\": 0.9}\n```\nMore text"
    out = extract_json_from_raw(raw)
    assert isinstance(out, dict)
    assert out["market_verdict"] == "viable"
    assert float(out["confidence_score"]) == pytest.approx(0.9)


def test_extract_json_from_plain_json():
    raw = '{"market_verdict": "uncertain", "confidence_score": 0.1}'
    out = extract_json_from_raw(raw)
    assert isinstance(out, dict)
    assert out["market_verdict"] == "uncertain"


def test_extract_json_none_on_non_json():
    raw = "This is plain text with no json."
    out = extract_json_from_raw(raw)
    assert out is None