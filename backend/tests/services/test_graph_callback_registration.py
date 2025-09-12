import pytest

from api.evaluate_startup import register_cost_tracking_callback, run_graph_with_cost_tracking

class FakeGraphWithMethods:
    def __init__(self):
        self._callbacks = []
        self.added = []
        self.removed = []

    def add_callback(self, cb):
        self.added.append(cb)

    def remove_callback(self, cb):
        self.removed.append(cb)


class FakeGraphWithList:
    def __init__(self):
        self.callbacks = []

def test_register_and_remove_with_add_remove(monkeypatch):
    g = FakeGraphWithMethods()
    cb, remover = register_cost_tracking_callback(g, user_id="u1", request_id="r1")
    # callback should have been attached via add_callback
    assert g.added and g.added[0] is cb

    # call remover and ensure it removes
    remover()
    # fake remove_callback should have been called with same instance
    assert g.removed and g.removed[0] is cb

def test_register_and_remove_with_callbacks_list():
    g = FakeGraphWithList()
    cb, remover = register_cost_tracking_callback(g, user_id="u2", request_id="r2")
    assert cb in g.callbacks
    remover()
    assert cb not in g.callbacks

def test_run_graph_with_cost_tracking_executes_callable_and_removes(monkeypatch):
    class Graph:
        def __init__(self):
            self.added = []
            self.removed = []
            self.callbacks = []
        def add_callback(self, cb):
            self.added.append(cb)
        def remove_callback(self, cb):
            self.removed.append(cb)

    g = Graph()
    called = {"ran": False}
    def work():
        called["ran"] = True
        return {"final_summary": {"tasks_output": [{"raw": ""}]}}
    res = run_graph_with_cost_tracking(g, user_id="uX", request_id="rX", run_callable=work)
    assert called["ran"] is True
    # Ensure callback removed
    assert len(g.removed) == 1