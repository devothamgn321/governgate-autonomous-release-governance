"""Step 5 - What fixes it?

Asks Nemotron for a backward-compatible version of the changed function,
then checks the proposal deterministically BEFORE anything is committed:

1. it parses as Python and defines the same function;
2. compared with the ORIGINAL signature, it introduces no breaking change;
3. it does not remove security-relevant calls the candidate had
   (for example the explicit `algorithms=[...]` pin or `_check_secret`).

Only a proposal that passes all three is committed to a new branch and
opened as a remediation merge request. That MR then runs the full pipeline:
SDK unit + security tests and GovernGate itself. An unsafe fix that slips
past these checks is still stopped by the security tests (CP10).
"""

import ast
import json

from governgate import semantic_analyzer

SYSTEM_PROMPT = (
    "You fix backward-compatibility breaks in a Python library without weakening security. "
    "Rules: keep every security check in the function; never disable signature verification; "
    "never accept an algorithm outside the library's allowed constant; prefer an optional "
    "parameter whose default is the library's existing secure constant. Reply with one JSON "
    "object with keys: strategy (one sentence), function_source (the complete replacement "
    "function definition, Python), risks (one sentence)."
)


def _function_node(source, name):
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _calls_in(node):
    names = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Name):
                names.add(child.func.id)
            elif isinstance(child.func, ast.Attribute):
                names.add(child.func.attr)
        if isinstance(child, ast.keyword) and child.arg:
            names.add("kw:" + child.arg)
    return names


def replace_function(module_source, name, new_function_source):
    """Return module source with one top-level function replaced."""
    node = _function_node(module_source, name)
    lines = module_source.splitlines(keepends=True)
    start = (node.decorator_list[0].lineno if node.decorator_list else node.lineno) - 1
    return "".join(lines[:start]) + new_function_source.rstrip() + "\n" + "".join(lines[node.end_lineno:])


def validate_proposal(original_module, candidate_module, symbol, function_source):
    """Deterministic checks. Returns (ok, reasons, patched_module)."""
    reasons = []
    try:
        new_node = _function_node(function_source, symbol)
    except SyntaxError as error:
        return False, ["proposal is not valid Python: " + str(error)], None
    if new_node is None:
        return False, ["proposal does not define " + symbol], None

    patched = replace_function(candidate_module, symbol, function_source)
    remaining = [c for c in semantic_analyzer.compare_sources(original_module, patched, "module")
                 if c["symbol"] == symbol and c["breaking"]]
    if remaining:
        reasons.append("still breaking vs original: " + ", ".join(c["change_type"] for c in remaining))

    lost = _calls_in(_function_node(candidate_module, symbol)) - _calls_in(new_node)
    security_relevant = {c for c in lost if c.startswith("kw:algorithm") or "check" in c or c in ("decode",)}
    if security_relevant:
        reasons.append("removes security-relevant calls: " + ", ".join(sorted(security_relevant)))

    proposal_text = ast.unparse(new_node).replace(" ", "")
    for pattern in FORBIDDEN_PATTERNS:
        if pattern in proposal_text:
            reasons.append("contains a forbidden pattern: " + pattern)
    return len(reasons) == 0, reasons, patched


# Text that must never appear in an accepted fix (checked with spaces removed).
FORBIDDEN_PATTERNS = ["'verify_signature':False", '"verify_signature":False', "algorithm='none'",
                      'algorithm="none"', "algorithms=['none']", 'algorithms=["none"]', "returnTrue"]


def propose_fix(nemotron, original_module, candidate_module, change):
    """Ask Nemotron for a fix and validate it. Returns a proposal dict."""
    evidence = {
        "symbol": change["symbol"],
        "original_signature": change["before"],
        "candidate_signature": change["after"],
        "change_type": change["change_type"],
        "candidate_module_source": candidate_module[:6000],
    }
    answer, record = nemotron.complete_json(SYSTEM_PROMPT, json.dumps(evidence, indent=1), reasoning=True, max_tokens=2500)
    if not answer or not answer.get("function_source"):
        return {"status": "no_proposal", "model_call": record}
    ok, reasons, patched = validate_proposal(original_module, candidate_module, change["symbol"], answer["function_source"])
    return {
        "status": "validated" if ok else "rejected_by_checks",
        "strategy": answer.get("strategy"),
        "risks": answer.get("risks"),
        "function_source": answer["function_source"],
        "check_failures": reasons,
        "patched_module": patched if ok else None,
        "model_call": record,
    }
