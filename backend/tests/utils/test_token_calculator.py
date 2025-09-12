import pytest

tc = pytest.importorskip("utils.token_calculator", reason="token_calculator module not found")


def test_token_count_is_integer_and_deterministic():
    """
    Verify token counting / estimation returns a non-negative integer and is deterministic
    for the same input.
    """
    text = "Hello world! This is a small test."
    if hasattr(tc, "count_tokens"):
        f = tc.count_tokens
    elif hasattr(tc, "estimate_tokens"):
        f = tc.estimate_tokens
    else:
        pytest.skip("No token count function found in utils.token_calculator")

    a = f(text)
    b = f(text)
    assert isinstance(a, int)
    assert a >= 0
    assert a == b

    # short vs long text
    a_short = f("hi")
    a_long = f(text * 10)
    assert a_long >= a_short