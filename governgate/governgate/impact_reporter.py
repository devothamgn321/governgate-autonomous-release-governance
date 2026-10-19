"""Step 8 - The merge request report.

One Markdown comment that a reviewer can act on in under a minute:
verdict first, then the evidence behind it, with links to every pipeline.
"""

ICON = {
    "READY_FOR_APPROVAL": "✅",
    "BLOCKED": "⛔",
    "INCOMPLETE_EVIDENCE": "⚠️",
    "REQUIRES_MANUAL_REVIEW": "🟠",
    "SUPERSEDED": "↻",
}


def _short(sha):
    return sha[:8] if sha else "?"


def _run_cell(run):
    if not run:
        return "—"
    label = (run.get("job_status") or run.get("status") or "?") + " · " + (run.get("summary") or "no summary")
    if run.get("pipeline_url"):
        return "[" + label + "](" + run["pipeline_url"] + ")"
    return label


def render(record):
    verdict = record["verdict"]
    lines = [
        "## " + ICON.get(verdict, "") + " GovernGate: " + verdict,
        "",
        "**Merge request:** !" + str(record["mr_iid"]) + " · base `" + _short(record["analysis"]["base_sha"])
        + "` → head `" + _short(record["analysis"]["head_sha"]) + "`",
        "",
    ]
    for reason in record["verdict_reasons"]:
        lines.append("- " + reason)

    lines += ["", "### What changed", "", "| Function | Before | After | Change | Breaking |", "| --- | --- | --- | --- | --- |"]
    for c in record["analysis"]["changes"]:
        lines.append("| `" + c["symbol"] + "` | `" + str(c["before"]) + "` | `" + str(c["after"]) + "` | "
                     + c["change_type"] + " | " + ("yes" if c["breaking"] else "no") + " |")

    discovery = record["discovery"]
    lines += ["", "### Who depends on it", "",
              "Scanned " + str(len(discovery["scanned"])) + " projects; " + str(len(discovery["unreadable"])) + " could not be read.", "",
              "| Project | Calls a changed function | Call sites | Static break |", "| --- | --- | --- | --- |"]
    for consumer in discovery["consumers"]:
        sites = ", ".join("`" + s["file"] + ":" + str(s["line"]) + "`" for s in consumer["call_sites"]) or "—"
        lines.append("| " + consumer["project"] + " | " + ("yes" if consumer["uses_changed_symbol"] else "no") + " | "
                     + sites + " | " + ("yes" if consumer["static_breaks"] else "no") + " |")

    if record["verifications"]:
        lines += ["", "### Differential test runs (same consumer commit)", "",
                  "| Consumer | Baseline SDK | Candidate SDK | Outcome |", "| --- | --- | --- | --- |"]
        for v in record["verifications"]:
            lines.append("| " + v["project"] + " | " + _run_cell(v["baseline"]) + " | " + _run_cell(v["candidate"])
                         + " | **" + v["outcome"] + "** |")

    for rc in record.get("root_causes", []):
        lines += ["", "### Root cause: " + rc["project"], "", rc["explanation"]["root_cause"]]
        if rc["explanation"].get("observed_error"):
            lines.append("")
            lines.append("Observed: `" + rc["explanation"]["observed_error"][:200] + "`")
        if rc["explanation"].get("recommended_action"):
            lines.append("")
            lines.append("**Recommended:** " + rc["explanation"]["recommended_action"])

    remediation = record.get("remediation")
    if remediation:
        lines += ["", "### Proposed fix", ""]
        if remediation.get("merge_request_url"):
            lines.append("Remediation MR: " + remediation["merge_request_url"] + " (it runs the full test and security suite before anyone can merge it).")
        else:
            lines.append("Status: " + remediation["status"] + (" — " + "; ".join(remediation.get("check_failures", [])) if remediation.get("check_failures") else ""))

    models = [c for c in record.get("model_calls", []) if c.get("status") == "ok"]
    lines += ["", "---", "<sub>GovernGate " + record["governgate_version"] + " · evidence sha256 `" + record.get("ledger_sha256", "?")[:16]
              + "…` · AI calls: " + str(len(models)) + (" (" + ", ".join(sorted({m["model"] for m in models})) + ")" if models else "")
              + ". AI explains; only test results decide. A human approves the merge.</sub>"]
    return "\n".join(lines)
