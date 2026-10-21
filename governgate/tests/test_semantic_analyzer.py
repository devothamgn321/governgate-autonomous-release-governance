from governgate.semantic_analyzer import compare_sources


def types(changes):
    return {(c["symbol"], c["change_type"]) for c in changes}


def test_required_parameter_added_is_breaking():
    changes = compare_sources("def f(a):\n    return a\n", "def f(a, b):\n    return a\n", "m.py")
    assert ("f", "REQUIRED_PARAMETER_ADDED") in types(changes)
    assert changes[0]["breaking"] and changes[0]["parameters"] == ["b"]
    assert changes[0]["new_required"] == ["a", "b"]


def test_optional_parameter_added_is_not_breaking():
    changes = compare_sources("def f(a):\n    return a\n", "def f(a, b=1):\n    return a\n", "m.py")
    assert types(changes) == {("f", "OPTIONAL_PARAMETER_ADDED")}
    assert not changes[0]["breaking"]


def test_function_removed_is_breaking():
    changes = compare_sources("def f():\n    pass\ndef g():\n    pass\n", "def g():\n    pass\n", "m.py")
    assert ("f", "FUNCTION_REMOVED") in types(changes)


def test_parameter_removed_is_breaking():
    changes = compare_sources("def f(a, b=1):\n    pass\n", "def f(a):\n    pass\n", "m.py")
    assert ("f", "PARAMETER_REMOVED") in types(changes)


def test_parameter_became_required():
    changes = compare_sources("def f(a, b=1):\n    pass\n", "def f(a, b):\n    pass\n", "m.py")
    assert ("f", "PARAMETER_BECAME_REQUIRED") in types(changes)


def test_body_change_detected_but_not_breaking():
    changes = compare_sources("def f(a):\n    return a\n", "def f(a):\n    return a + 1\n", "m.py")
    assert types(changes) == {("f", "BODY_CHANGED")}
    assert not changes[0]["breaking"]


def test_private_and_unchanged_functions_ignored():
    src = "def _helper(x):\n    pass\ndef f(a):\n    return a\n"
    assert compare_sources(src, src.replace("_helper(x)", "_helper(x, y)"), "m.py") == []


def test_keyword_only_required_parameter():
    changes = compare_sources("def f(a):\n    pass\n", "def f(a, *, mode):\n    pass\n", "m.py")
    assert ("f", "REQUIRED_PARAMETER_ADDED") in types(changes)


def test_real_sdk_change(tmp_path):
    from fake_gitlab import FIXTURES
    old = (FIXTURES / "sdk_v1/src/core_auth_sdk/tokens.py").read_text()
    new = (FIXTURES / "sdk_candidate/src/core_auth_sdk/tokens.py").read_text()
    changes = compare_sources(old, new, "tokens.py")
    assert ("verify_token", "REQUIRED_PARAMETER_ADDED") in types(changes)
    assert all(c["symbol"] != "issue_token" for c in changes)


def test_parameter_reorder_is_breaking():
    changes = compare_sources("def f(a,b): return a-b", "def f(b,a): return a-b", "m.py")
    assert changes[0]["change_type"] == "SIGNATURE_CHANGED"
    assert changes[0]["breaking"]


def test_parameter_kind_and_default_changes_are_detected():
    for old, new in [("a,b", "a,*,b"), ("a=1", "a=2"), ("a,*rest", "a")]:
        changes = compare_sources(f"def f({old}): pass", f"def f({new}): pass", "m.py")
        assert any(c["change_type"] == "SIGNATURE_CHANGED" and c["breaking"] for c in changes)
