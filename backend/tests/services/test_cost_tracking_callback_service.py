import json
import os
from pathlib import Path

import pytest

from services.cost_tracking_callback_service import CostTrackingCallback

def test_on_llm_end_writes_cost_record(tmp_path, monkeypatch):
    # Ensure local data dir is isolated
    monkeypatch.setenv("BACKEND_DATA_DIR", str(tmp_path))

    cb = CostTrackingCallback(user_id="test-user", request_id="req-1")

    # Simulate an LLM response with usage available
    response = {
        "llm_output": {
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            "model": "gpt-3.5"
        }
    }

    # Call the callback
    cb.on_llm_end(response)

    # Assert costs.jsonl file created and contains a valid JSON line
    costs_file = Path(str(tmp_path)) / "costs.jsonl"
    assert costs_file.exists()

    with costs_file.open("r", encoding="utf-8") as fh:
        lines = [line.strip() for line in fh.readlines() if line.strip()]
    assert len(lines) >= 1
    rec = json.loads(lines[-1])
    assert rec["user_id"] == "test-user"
    assert rec["request_id"] == "req-1"
    assert "amount_usd" in rec
    assert rec["amount_usd"] >= 0.0


def test_on_graph_end_falls_back_to_middleware_estimate(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKEND_DATA_DIR", str(tmp_path))

    # Write a middleware estimate file that the callback will read
    estimate = {"total_cost_usd": 0.42, "prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10}
    est_file = Path(str(tmp_path)) / "cost_estimates"
    est_file.mkdir(exist_ok=True)
    path = est_file / "req-42.json"
    path.write_text(json.dumps(estimate), encoding="utf-8")

    cb = CostTrackingCallback(user_id="u42", request_id="req-42")
    # Provide a graph_result without token_usage to force fallback
    cb.on_graph_end({"some": "result"})

    costs_file = Path(str(tmp_path)) / "costs.jsonl"
    assert costs_file.exists()
    with costs_file.open("r", encoding="utf-8") as fh:
        rec = json.loads(fh.readlines()[-1])
    assert rec["user_id"] == "u42"
    assert rec["request_id"] == "req-42"
    assert rec["amount_usd"] == pytest.approx(0.42, rel=1e-3)