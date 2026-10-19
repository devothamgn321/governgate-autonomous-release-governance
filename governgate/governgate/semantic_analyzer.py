"""Step 1 - What changed?

Compares the public functions of a Python module before and after a change,
using the standard-library AST. Deterministic: no AI involved here.
Nemotron is only asked afterwards to explain body-level behaviour changes.
"""

import ast

REQUIRED_PARAMETER_ADDED = "REQUIRED_PARAMETER_ADDED"
OPTIONAL_PARAMETER_ADDED = "OPTIONAL_PARAMETER_ADDED"
PARAMETER_REMOVED = "PARAMETER_REMOVED"
PARAMETER_BECAME_REQUIRED = "PARAMETER_BECAME_REQUIRED"
FUNCTION_REMOVED = "FUNCTION_REMOVED"
FUNCTION_ADDED = "FUNCTION_ADDED"
BODY_CHANGED = "BODY_CHANGED"

# Change types that can break an existing caller.
BREAKING = {REQUIRED_PARAMETER_ADDED, PARAMETER_REMOVED, PARAMETER_BECAME_REQUIRED, FUNCTION_REMOVED}


def _signature(node):
    """Return (params, required) for a function node: ordered names and the required ones."""
    args = node.args
    positional = args.posonlyargs + args.args
    names = [a.arg for a in positional] + [a.arg for a in args.kwonlyargs]
    first_default = len(positional) - len(args.defaults)
    required = []
    for index in range(len(positional)):
        if index < first_default:
            required.append(positional[index].arg)
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        if default is None:
            required.append(arg.arg)
    return names, required


def _render(name, node):
    return name + "(" + ast.unparse(node.args) + ")"


def public_functions(source):
    """Map of public top-level function name -> (node, signature text, body dump)."""
    tree = ast.parse(source)
    result = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            body_dump = ast.dump(ast.Module(body=node.body, type_ignores=[]))
            result[node.name] = (node, _render(node.name, node), body_dump)
    return result


def compare_sources(old_source, new_source, module_path):
    """Return a list of change dicts for one module."""
    old = public_functions(old_source) if old_source else {}
    new = public_functions(new_source) if new_source else {}
    changes = []

    for name in sorted(set(old) | set(new)):
        if name in old and name not in new:
            changes.append(_change(module_path, name, FUNCTION_REMOVED, old[name][1], None))
            continue
        if name in new and name not in old:
            changes.append(_change(module_path, name, FUNCTION_ADDED, None, new[name][1]))
            continue

        old_node, old_sig, old_body = old[name]
        new_node, new_sig, new_body = new[name]
        old_params, old_required = _signature(old_node)
        new_params, new_required = _signature(new_node)

        added = [p for p in new_params if p not in old_params]
        removed = [p for p in old_params if p not in new_params]
        newly_required = [p for p in new_required if p in old_params and p not in old_required]

        if removed:
            changes.append(_change(module_path, name, PARAMETER_REMOVED, old_sig, new_sig, removed))
        if [p for p in added if p in new_required]:
            changes.append(_change(module_path, name, REQUIRED_PARAMETER_ADDED, old_sig, new_sig,
                                   [p for p in added if p in new_required]))
        if [p for p in added if p not in new_required]:
            changes.append(_change(module_path, name, OPTIONAL_PARAMETER_ADDED, old_sig, new_sig,
                                   [p for p in added if p not in new_required]))
        if newly_required:
            changes.append(_change(module_path, name, PARAMETER_BECAME_REQUIRED, old_sig, new_sig, newly_required))
        if old_body != new_body and old_sig == new_sig:
            changes.append(_change(module_path, name, BODY_CHANGED, old_sig, new_sig))

    # Record the new required parameters, so call sites can be checked against them.
    for change in changes:
        if change["symbol"] in new:
            change["new_required"] = _signature(new[change["symbol"]][0])[1]
        else:
            change["new_required"] = []
    return changes


def _change(module_path, name, change_type, before, after, params=None):
    return {
        "module": module_path,
        "symbol": name,
        "change_type": change_type,
        "before": before,
        "after": after,
        "parameters": params or [],
        "breaking": change_type in BREAKING,
    }


def analyze_merge_request(client, project_id, mr):
    """Compare every changed .py file under src/ between target and MR head."""
    base_sha = mr["diff_refs"]["base_sha"]
    head_sha = mr["diff_refs"]["head_sha"]
    changes = []
    for diff in client.list_mr_diffs(project_id, mr["iid"]):
        path = diff.get("new_path") or diff.get("old_path")
        if not path.endswith(".py") or "/tests/" in "/" + path or path.startswith("tests/"):
            continue
        old_source = None if diff.get("new_file") else client.get_file(project_id, diff["old_path"], base_sha)
        new_source = None if diff.get("deleted_file") else client.get_file(project_id, diff["new_path"], head_sha)
        changes.extend(compare_sources(old_source, new_source, path))
    return {"base_sha": base_sha, "head_sha": head_sha, "changes": changes}
