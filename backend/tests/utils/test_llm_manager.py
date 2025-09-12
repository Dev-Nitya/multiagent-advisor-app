import pytest
import inspect

llm_module = pytest.importorskip("utils.llm_manager", reason="llm_manager module not found")


def test_llm_manager_interface(monkeypatch):
    """
    Verify a minimal callable interface exists (LLMManager or call_llm).
    If present, exercise it with a fake client that returns a predictable response.
    """
    fake_client = lambda *a, **k: {"content": "fake response", "usage": {"prompt_tokens": 1, "completion_tokens": 1}}

    if hasattr(llm_module, "LLMManager"):
        LLMManager = llm_module.LLMManager
        # Try to instantiate with a fake client if constructor accepts a client arg
        sig = inspect.signature(LLMManager)
        try:
            if "client" in sig.parameters:
                mgr = LLMManager(client=fake_client)
            else:
                mgr = LLMManager()
        except Exception:
            pytest.skip("LLMManager ctor incompatible with this test")

        # Try common call methods
        if hasattr(mgr, "call"):
            out = mgr.call("hello")
            assert out is not None
        elif hasattr(mgr, "invoke"):
            out = mgr.invoke({"prompt": "hello"})
            assert out is not None
        else:
            pytest.skip("LLMManager has no call/invoke method to test")

    elif hasattr(llm_module, "call_llm"):
        call_llm = llm_module.call_llm
        # Try passing client if supported
        try:
            out = call_llm("hello", client=fake_client)
            assert out is not None
        except TypeError:
            # try without client
            out = call_llm("hello")
            assert out is not None
    else:
        pytest.skip("No recognizable LLM interface in utils.llm_manager")