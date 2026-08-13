"""Merge assertions — artifact correctness.

Promptfoo Python assertion return format (GradingResult):
    {"pass_": bool, "score": float 0-1, "reason": str}

Snake_case keys are auto-converted to camelCase by promptfoo:
    pass_ -> pass, component_results -> componentResults.

All CR-specific values (names, jmespath paths, expected values) come from
the config block in promptfooconfig.yaml — this code is a generic engine.

Communication checks (conflict flagging, overlay lifecycle, checklist
quality) are handled by llm-rubric in promptfooconfig.yaml.
"""

import jmespath
import yaml

from common import (
    collect_manifests,
    collect_written_files,
    find_first,
    fmt_check,
    parse_pg_docs,
)


def _run_check(check, all_manifests, manifest_paths):
    """Run a single config-driven check. Returns (name, passed, expected, actual)."""
    name = check["name"]
    cr = check["cr"]
    check_type = check.get("type")

    if check_type == "exists":
        found = find_first(all_manifests, cr) is not None
        return (
            name,
            found,
            f"manifest containing '{cr}'",
            f"{'found' if found else 'not found'} in {len(all_manifests)} manifests",
        )

    if check_type == "not_exists":
        found = any(cr.lower() in p.lower() for p in manifest_paths)
        return (
            name,
            not found,
            f"no manifest containing '{cr}'",
            f"{'found (bad)' if found else 'absent (good)'}",
        )

    if check_type == "profile_content":
        return _check_profile_content(check, all_manifests)

    # Field check: cr + path, with optional contains/empty modifiers.
    # Search ALL matching manifests (not just the first) because a CR
    # may appear in multiple policies (e.g. PTP in primary + secondary).
    matches = [m for m in all_manifests if cr.lower() in m.get("path", "").lower()]
    m = matches[0] if matches else None
    path = check["path"]
    result = jmespath.search(path, m) if m else None

    if check.get("empty"):
        return (
            name,
            not bool(result),
            f"empty {path}",
            f"result={bool(result)}",
        )

    if "contains" in check:
        value = check["contains"]
        for candidate in matches:
            candidate_result = jmespath.search(path, candidate)
            if value in str(candidate_result or ""):
                return (name, True, f"'{value}' in {path}", "found")
        return (
            name,
            False,
            f"'{value}' in {path}",
            "not found",
        )

    return (
        name,
        m is not None and bool(result),
        f"non-empty {path}",
        f"manifest={'found' if m else 'missing'}, result={bool(result)}",
    )


def _check_profile_content(check, all_manifests):
    """Check that expected content exists in the correct named profile."""
    name = check["name"]
    cr = check["cr"]
    m = find_first(all_manifests, cr)
    if m is None:
        return (name, False, f"manifest '{cr}'", "not found")

    profiles = jmespath.search(check["profiles_path"], m) or []
    target_profile = check["profile_name_contains"]
    expected_content = check["data_contains"]
    expected_section = check.get("section_contains", "")

    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        pname = profile.get("name", "")
        data = profile.get("data", "")
        if expected_content not in data:
            continue
        in_target = target_profile in pname
        in_section = expected_section in data if expected_section else True
        if in_target and in_section:
            return (
                name,
                True,
                f"'{expected_content}' in profile '{target_profile}'",
                f"found in profile '{pname}'",
            )

    return (
        name,
        False,
        f"'{expected_content}' in profile '{target_profile}'",
        f"not found in {len(profiles)} profiles",
    )


def check_no_unrequested_crs(_output, context):
    """Agent must not inject optional reference CRs the partner doesn't use."""
    config = context.get("config") or {}
    forbidden = config.get("forbidden_crs", [])
    written = collect_written_files(context)
    pg_docs, _ = parse_pg_docs(written)
    manifests = collect_manifests(pg_docs)
    paths = [m.get("path", "") for m in manifests]
    injected = [cr for cr in forbidden if any(cr.lower() in p.lower() for p in paths)]
    if injected:
        return {
            "pass_": False,
            "score": 0,
            "reason": f"Unrequested CRs injected: {', '.join(injected)}",
        }
    return {
        "pass_": True,
        "score": 1.0,
        "reason": "No unrequested reference CRs found in output",
    }


def check_hub_template_namespace(_output, context):
    """Hub template namespace references must track the target version."""
    config = context.get("config") or {}
    source_ns = config.get("source_namespace_pattern", "v4-18")
    written = collect_written_files(context)
    hits = []
    for fp, content in written.items():
        if not fp.endswith((".yaml", ".yml")):
            continue
        for i, line in enumerate(content.splitlines(), 1):
            if "hub" in line and source_ns in line:
                hits.append(f"{fp}:{i}")
    if hits:
        return {
            "pass_": False,
            "score": 0,
            "reason": f"Stale hub template namespace ({source_ns}): {', '.join(hits[:5])}",
        }
    return {
        "pass_": True,
        "score": 1.0,
        "reason": "Hub template namespaces updated",
    }


def check_kustomization_updated(_output, context):
    """Parent kustomization.yaml should reference new version files."""
    config = context.get("config") or {}
    target_version = config.get("target_version", "4.20")
    written = collect_written_files(context)
    kustomization = None
    for fp, content in written.items():
        if "kustomization" in fp.lower():
            kustomization = content
            break
    if not kustomization:
        return {
            "pass_": False,
            "score": 0,
            "reason": "No kustomization.yaml written",
        }
    tv = target_version.replace(".", "-")
    if tv in kustomization or target_version in kustomization:
        return {
            "pass_": True,
            "score": 1.0,
            "reason": "Kustomization references target version",
        }
    return {
        "pass_": False,
        "score": 0,
        "reason": f"Kustomization missing target version {target_version}",
    }


def check_quote_preservation(_output, context):
    """YAML quote styles must be preserved through the merge."""
    config = context.get("config") or {}
    expected = config.get("expected_patterns", [])
    written = collect_written_files(context)
    content = "\n".join(c for p, c in written.items() if p.endswith((".yaml", ".yml")))
    missing = [p for p in expected if p not in content]
    if missing:
        return {
            "pass_": False,
            "score": 0,
            "reason": f"Quote patterns lost: {missing}",
        }
    return {
        "pass_": True,
        "score": 1.0,
        "reason": "All quote patterns preserved",
    }


def check_absent_patterns(_output, context):
    """Patterns that must NOT appear in the output PolicyGenerator files.

    Used to verify the agent didn't adopt reference-only values into the
    partner's policies — e.g. the reference's example topology pool
    references (mcp-worker-1/2/3) when the partner has their own pool.
    Scans PolicyGenerator docs only, NOT the copied source-crs/ library:
    replacing source-crs pulls in every reference CR (including pools the
    partner doesn't use), so scanning it would false-positive. What
    matters is whether those references leaked into the partner's PGs.
    """
    config = context.get("config") or {}
    forbidden = config.get("forbidden_patterns", [])
    written = collect_written_files(context)
    pg_text = []
    for fp, content in written.items():
        if not fp.endswith((".yaml", ".yml")):
            continue
        try:
            docs = list(yaml.safe_load_all(content))
        except yaml.YAMLError:
            continue
        if any(isinstance(d, dict) and d.get("kind") == "PolicyGenerator" for d in docs):
            pg_text.append(content)
    blob = "\n".join(pg_text)
    present = [p for p in forbidden if p in blob]
    if present:
        return {
            "pass_": False,
            "score": 0,
            "reason": f"Forbidden patterns present in output PolicyGenerator(s): {', '.join(present)}",
        }
    return {
        "pass_": True,
        "score": 1.0,
        "reason": "No forbidden patterns found in output PolicyGenerator(s)",
    }


def check_file_content(_output, context):
    """Verify the merge produced correct YAML artifacts using config-driven checks.

    Version bump checks (name, namespace, labels) are handled by
    check_multi_pg_structure which validates ALL PG docs, not just the first.
    """
    config = context["config"]

    written = collect_written_files(context)

    if not written:
        return {
            "pass_": False,
            "score": 0,
            "reason": "EXPECTED: written files | ACTUAL: no files found",
        }

    pg_docs, skipped = parse_pg_docs(written, strict=True)

    if not pg_docs:
        return {
            "pass_": False,
            "score": 0,
            "reason": f"EXPECTED: PolicyGenerator docs | ACTUAL: 0 PG docs, {len(skipped)} non-PG skipped: {[s.get('kind', s.get('error', '?')) for s in skipped]}",
        }

    all_manifests = collect_manifests(pg_docs)
    manifest_paths = [m.get("path", "") for m in all_manifests]

    checks = [_run_check(c, all_manifests, manifest_paths) for c in config["checks"]]

    total = len(checks)
    num_passed = sum(1 for _, passed, _, _ in checks if passed)

    return {
        "pass_": num_passed == total,
        "score": num_passed / total,
        "reason": f"{num_passed}/{total} artifact checks passed ({len(skipped)} non-PG: {[s.get('kind', s.get('error', '?')) for s in skipped]})",
        "component_results": [
            {
                "pass_": bool(passed),
                "score": 1.0 if passed else 0.0,
                "reason": fmt_check(name, passed, expected, actual),
            }
            for name, passed, expected, actual in checks
        ],
    }
