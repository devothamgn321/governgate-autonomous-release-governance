"""Step 2 - What could break?

Finds every project in the GitLab group that depends on the changed library,
then finds the exact lines where each one calls a changed function.

Evidence, not guesses:
- dependency: the library name appears in requirements.txt or pyproject.toml
- call sites: parsed with AST, so comments and strings never count as calls
- static break: a call passes fewer arguments than the new required set

Discovery coverage is reported (projects scanned, projects that could not be
read), so a report never claims more than was actually checked.
"""

import ast
import re

MAX_FILES_PER_PROJECT = 200


def normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def declares_dependency(text, library_name):
    """True if a requirements/pyproject text names the library."""
    if not text:
        return False
    wanted = normalize(library_name)
    for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9._-]*", text):
        if normalize(token) == wanted:
            return True
    return False


def find_call_sites(source, file_path, import_name, symbols):
    """Return calls to `symbols` that come from `import_name`, with argument counts."""
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise ValueError("Consumer Python source could not be parsed") from error

    # Names bound to the library's functions in this file, e.g. `from core_auth_sdk import verify_token`.
    local_names = {}
    module_aliases = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == import_name:
            for alias in node.names:
                if alias.name in symbols:
                    local_names[alias.asname or alias.name] = alias.name
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == import_name:
                    module_aliases.add(alias.asname or alias.name)

    sites = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        symbol = None
        if isinstance(node.func, ast.Name) and node.func.id in local_names:
            symbol = local_names[node.func.id]
        elif (isinstance(node.func, ast.Attribute) and node.func.attr in symbols
              and isinstance(node.func.value, ast.Name) and node.func.value.id in module_aliases):
            symbol = node.func.attr
        if symbol:
            sites.append({
                "file": file_path,
                "line": node.lineno,
                "symbol": symbol,
                "positional_args": len(node.args),
                "keyword_args": [k.arg for k in node.keywords if k.arg],
                "code": ast.unparse(node),
            })
    return sites


def call_breaks_statically(site, change, new_required):
    """True if this call cannot satisfy the new signature's required parameters."""
    if change["change_type"] == "FUNCTION_REMOVED":
        return True
    if change["change_type"] in ("REQUIRED_PARAMETER_ADDED", "PARAMETER_BECAME_REQUIRED"):
        missing = new_required[site["positional_args"]:]
        missing = [p for p in missing if p not in site["keyword_args"]]
        return len(missing) > 0
    return False


def discover_consumers(client, group_id, upstream_project_id, library_name, import_name, changes, new_required_by_symbol):
    """Scan the group and classify each project."""
    changed_symbols = {c["symbol"] for c in changes if c["change_type"] != "FUNCTION_ADDED"}
    breaking_by_symbol = {}
    for c in changes:
        if c["breaking"]:
            breaking_by_symbol.setdefault(c["symbol"], []).append(c)

    result = {"scanned": [], "unreadable": [], "consumers": []}
    for project in client.list_group_projects(group_id):
        if project["id"] == upstream_project_id:
            continue
        name = project["path_with_namespace"]
        ref = project.get("default_branch") or "main"
        try:
            requirements = client.get_file(project["id"], "requirements.txt", ref)
            pyproject = client.get_file(project["id"], "pyproject.toml", ref)
        except Exception as error:  # noqa: BLE001 - record and keep going; coverage is reported
            result["unreadable"].append({"project": name, "reason": str(error)[:200]})
            continue
        result["scanned"].append(name)
        if not (declares_dependency(requirements, library_name) or declares_dependency(pyproject, library_name)):
            continue

        sites = []
        files = [f for f in client.list_tree(project["id"], ref) if f["type"] == "blob" and f["path"].endswith(".py")]
        if len(files) > MAX_FILES_PER_PROJECT:
            raise ValueError("Consumer scan exceeds coverage limit")
        for entry in files:
            source = client.get_file(project["id"], entry["path"], ref)
            if source and import_name in source:
                sites.extend(find_call_sites(source, entry["path"], import_name, changed_symbols))

        production_sites = [s for s in sites if not s["file"].startswith("tests/")]
        static_breaks = []
        for site in production_sites:
            for change in breaking_by_symbol.get(site["symbol"], []):
                if call_breaks_statically(site, change, new_required_by_symbol.get(site["symbol"], [])):
                    static_breaks.append({"site": site, "change_type": change["change_type"]})

        result["consumers"].append({
            "project": name,
            "project_id": project["id"],
            "ref": ref,
            "call_sites": production_sites,
            "uses_changed_symbol": len(production_sites) > 0,
            "static_breaks": static_breaks,
            "needs_verification": len(production_sites) > 0,
        })
    return result
