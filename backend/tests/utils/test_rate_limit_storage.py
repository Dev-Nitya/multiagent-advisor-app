import pytest

rl_module = pytest.importorskip("utils.rate_limit_storage", reason="rate_limit_storage module not found")


def test_rate_limit_store_basic_operations():
    """
    Test an in-memory rate limit store interface:
    - increment / get / reset semantics
    Accepts either a class InMemoryRateLimitStore or module-level functions.
    """
    if hasattr(rl_module, "InMemoryRateLimitStore"):
        Store = rl_module.InMemoryRateLimitStore
        store = Store()
        store.increment("test-key", 1)
        assert store.get("test-key") >= 1
        store.reset("test-key")
        assert store.get("test-key") == 0
    else:
        # function-based API
        if not (hasattr(rl_module, "increment") and hasattr(rl_module, "get") and hasattr(rl_module, "reset")):
            pytest.skip("No supported rate limit API found")
        rl_module.reset("k1")
        rl_module.increment("k1", 2)
        assert rl_module.get("k1") >= 2
        rl_module.reset("k1")
        assert rl_module.get("k1") == 0