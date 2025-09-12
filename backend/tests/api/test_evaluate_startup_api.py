import json
from fastapi.testclient import TestClient
import pytest

# Import the FastAPI app; adjust if app is in a different module
from main import app

client = TestClient(app)

def make_fake_graph(final_summary_raw: str):
    class FakeGraph:
        def invoke(self, payload):
            return {"final_summary": {"tasks_output": [{"raw": final_summary_raw}]}}
    return FakeGraph()

def test_evaluate_success_structured(monkeypatch):
    # JSON wrapped in a code fence
    raw = "```json\n{\"market_verdict\": \"viable\", \"financial_verdict\": \"good\", \"product_verdict\": \"ok\", \"final_recommendation\": \"go\", \"rationale\": \"test\", \"confidence_score\": 0.5}\n```"
    fake = make_fake_graph(raw)
    monkeypatch.setattr("agents.langgraph.advisor_graph.build_graph", lambda: fake)

    body = {"idea": "test idea", "user_id": "u1", "request_id": "r1"}
    resp = client.post("/evaluate", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["market_verdict"] == "viable"
    assert data["final_recommendation"] == "go"
    assert "confidence_score" in data

def test_evaluate_failure_when_no_final_summary(monkeypatch):
    class FakeGraph:
        def invoke(self, payload):
            return {}
    monkeypatch.setattr("agents.langgraph.advisor_graph.build_graph", lambda: FakeGraph())

    body = {"idea": "no summary", "user_id": "u1"}
    resp = client.post("/evaluate", json=body)
    assert resp.status_code == 500
    data = resp.json()
    assert "detail" in data