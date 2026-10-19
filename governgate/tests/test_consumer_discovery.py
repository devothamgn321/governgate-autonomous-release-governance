from governgate.consumer_discovery import call_breaks_statically, declares_dependency, find_call_sites


def test_dependency_name_normalized():
    assert declares_dependency("core-auth-sdk==1.0.0\npytest\n", "core_auth_sdk")
    assert declares_dependency('dependencies = ["Core.Auth-SDK>=1"]', "core-auth-sdk")
    assert not declares_dependency("core-auth-sdk-extras==1\n", "core-auth-sdk")
    assert not declares_dependency(None, "core-auth-sdk")


def test_from_import_call_found():
    src = "from core_auth_sdk import verify_token\n\ndef pay(t, s):\n    return verify_token(t, s)\n"
    sites = find_call_sites(src, "billing/payments.py", "core_auth_sdk", {"verify_token"})
    assert len(sites) == 1 and sites[0]["line"] == 4 and sites[0]["positional_args"] == 2


def test_alias_and_module_import_found():
    src = ("import core_auth_sdk as auth\nfrom core_auth_sdk import verify_token as vt\n"
           "auth.verify_token(a, b)\nvt(a, b, algorithm='HS256')\n")
    sites = find_call_sites(src, "x.py", "core_auth_sdk", {"verify_token"})
    assert len(sites) == 2
    assert sites[1]["keyword_args"] == ["algorithm"] or sites[0]["keyword_args"] == ["algorithm"]


def test_comments_strings_and_other_libraries_ignored():
    src = ("from other_lib import verify_token\n# verify_token(a)\nx = 'verify_token(a)'\nverify_token(a)\n")
    assert find_call_sites(src, "x.py", "core_auth_sdk", {"verify_token"}) == []


def test_static_break_detection():
    change = {"change_type": "REQUIRED_PARAMETER_ADDED"}
    required = ["token", "secret", "algorithm"]
    old_call = {"positional_args": 2, "keyword_args": []}
    new_call = {"positional_args": 2, "keyword_args": ["algorithm"]}
    assert call_breaks_statically(old_call, change, required)
    assert not call_breaks_statically(new_call, change, required)
