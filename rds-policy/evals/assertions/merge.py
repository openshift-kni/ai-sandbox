"""Merge assertions — artifact correctness and checklist verification.

Promptfoo Python assertion return format (GradingResult):
    {"pass_": bool, "score": float 0-1, "reason": str}

Snake_case keys are auto-converted to camelCase by promptfoo:
    pass_ -> pass, component_results -> componentResults.

All CR-specific values (names, jmespath paths, expected values) come from
the config block in promptfooconfig.yaml — this code is a generic engine.

Communication checks (conflict flagging, overlay lifecycle, list merge
awareness) are handled by llm-rubric in promptfooconfig.yaml.
"""

import re

import jmespath

from common import (
    collect_manifests,
    collect_written_files,
    find_first,
    parse_pg_docs,
    version_matches,
)


def _fmt(name, passed, expected, actual):
    status = "PASS" if passed else "FAIL"
    return f"{status} {name} | EXPECTED: {expected} | ACTUAL: {actual}"


def _run_check(check, all_manifests, manifest_paths):
    """Run a single config-driven check. Returns (name, passed, expected, actual)."""
    name = check["name"]
    check_type = check["type"]
    cr = check.get("cr", "")

    if check_type == "present":
        found = find_first(all_manifests, cr) is not None
        return (
            name,
            found,
            f"manifest containing '{cr}'",
            f"{'found' if found else 'not found'} in {len(all_manifests)} manifests",
        )

    if check_type == "absent":
        found = any(cr in p.lower() for p in manifest_paths)
        return (
            name,
            not found,
            f"no manifest containing '{cr}'",
            f"{'found (bad)' if found else 'absent (good)'}",
        )

    if check_type == "path_not_empty":
        m = find_first(all_manifests, cr)
        result = jmespath.search(check["path"], m) if m else None
        return (
            name,
            m is not None and bool(result),
            f"non-empty {check['path']}",
            f"manifest={'found' if m else 'missing'}, result={bool(result)}",
        )

    if check_type == "path_empty":
        m = find_first(all_manifests, cr)
        result = jmespath.search(check["path"], m) if m else None
        return (
            name,
            m is None or not bool(result),
            f"empty {check['path']}",
            f"manifest={'found' if m else 'missing'}, result={bool(result)}",
        )

    if check_type == "path_contains":
        m = find_first(all_manifests, cr)
        value = check["value"]
        result = jmespath.search(check["path"], m) if m else None
        found = value in str(result or "")
        return (
            name,
            found,
            f"'{value}' in {check['path']}",
            f"{'found' if found else 'not found'}",
        )

    if check_type == "profile_content":
        return _check_profile_content(check, all_manifests)

    raise ValueError(f"Unknown check type: {check_type}")


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


def check_file_content(_output, context):
    """Verify the merge produced correct YAML artifacts using config-driven checks."""
    config = context["config"]
    target_ver = config["target_version"]

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

    pg = pg_docs[0]
    metadata_name = pg.get("metadata", {}).get("name", "")
    defaults = pg.get("policyDefaults", {})
    namespace = defaults.get("namespace", "")
    placement_version_label = (
        defaults.get("placement", {})
        .get("labelSelector", {})
        .get("cluster-version", "")
    )

    all_manifests = collect_manifests(pg_docs)
    manifest_paths = [m.get("path", "") for m in all_manifests]

    checks = [_run_check(c, all_manifests, manifest_paths) for c in config["checks"]]

    checks += [
        (
            "version_bump_name",
            version_matches(metadata_name, target_ver),
            f"metadata.name contains {target_ver}",
            f"metadata.name='{metadata_name}'",
        ),
        (
            "version_bump_ns",
            version_matches(namespace, target_ver),
            f"namespace contains {target_ver}",
            f"namespace='{namespace}'",
        ),
        (
            "version_bump_label",
            target_ver in placement_version_label,
            f"cluster-version label contains {target_ver}",
            f"cluster-version='{placement_version_label}'",
        ),
    ]

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
                "reason": _fmt(name, passed, expected, actual),
            }
            for name, passed, expected, actual in checks
        ],
    }


def _check_terms(term_checks, checklist):
    """Run a list of term checks against checklist text. Returns list of result tuples."""
    results = []
    for tc in term_checks:
        name = tc["name"]
        terms = tc["terms"]
        all_found = all(t in checklist for t in terms)
        detail = ", ".join(
            f"{t}={'found' if t in checklist else 'missing'}" for t in terms
        )

        if "context_pattern" in tc:
            ctx = bool(re.search(tc["context_pattern"], checklist))
            all_found = all_found and ctx
            detail += f", context_pattern={ctx}"

        results.append((name, all_found, f"all of {terms} in checklist", detail))
    return results


def check_completeness(_output, context):
    """Agent must produce a checklist file that covers every merge task."""
    config = context["config"]
    cl = config["checklist"]

    written = collect_written_files(context)

    checklist_contents = []
    checklist_paths = []
    for path, content in written.items():
        if re.search(r"checklist|completed", path, re.IGNORECASE):
            checklist_contents.append(content)
            checklist_paths.append(path)

    checklist = "\n".join(checklist_contents).lower()

    if not checklist:
        files_written = list(written.keys())
        return {
            "pass_": False,
            "score": 0,
            "reason": f"EXPECTED: checklist file | ACTUAL: no checklist found in {len(files_written)} written files: {files_written[:5]}",
        }

    required = _check_terms(cl["required_terms"], checklist)

    status_markers = re.findall(r"\[([xX!~\-])\]", checklist)
    unchecked = re.findall(r"\[ \]", checklist)

    required += [
        (
            "status_markers",
            len(status_markers) >= 3,
            ">=3 status markers [x]/[!]/[-]/[~]",
            f"found {len(status_markers)} markers",
        ),
        (
            "all_resolved",
            len(unchecked) == 0,
            "no unchecked [ ] items",
            f"found {len(unchecked)} unchecked items",
        ),
    ]

    optional = _check_terms(cl.get("optional_terms", []), checklist)

    all_checks = required + optional
    req_failed = [name for name, passed, _, _ in required if not passed]
    num_passed = sum(1 for _, passed, _, _ in all_checks if passed)
    total = len(all_checks)

    return {
        "pass_": len(req_failed) == 0,
        "score": num_passed / total,
        "reason": f"{num_passed}/{total} checklist items found (files: {checklist_paths})",
        "component_results": [
            {
                "pass_": bool(passed),
                "score": 1.0 if passed else 0.0,
                "reason": _fmt(name, passed, expected, actual),
            }
            for name, passed, expected, actual in all_checks
        ],
    }
