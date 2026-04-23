"""Structural assertions — multi-PG preservation, wave changes, CR replication.

Promptfoo Python assertion return format (GradingResult):
    {"pass_": bool, "score": float 0-1, "reason": str}
    Snake_case keys auto-convert to camelCase.
"""

import glob
import os
import re
import subprocess

import yaml

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def check_multi_pg_structure(_output, context):
    """Agent must preserve multi-PG file structure and apply version bumps to all.

    Checks:
    - 2+ PolicyGenerator files written (not merged into one)
    - metadata.name bumped in ALL PGs
    - policyDefaults.namespace bumped in ALL PGs
    - placement label cluster-version bumped in ALL PGs
    """
    config = context.get("config") or {}
    target_ver = config.get("target_version", "4.20")

    written = _collect_written_files(context)
    pg_docs = []

    for content in written.values():
        try:
            for doc in yaml.safe_load_all(content):
                if doc and doc.get("kind") == "PolicyGenerator":
                    pg_docs.append(doc)
        except yaml.YAMLError, AttributeError:
            continue

    checks = [
        (
            "multi_pg_preserved",
            len(pg_docs) >= 2,
            f"Expected 2+ PolicyGenerator files, found {len(pg_docs)}",
        ),
    ]

    for i, pg in enumerate(pg_docs):
        name = pg.get("metadata", {}).get("name", f"pg-{i}")
        ns = pg.get("policyDefaults", {}).get("namespace", "")
        label_selector = (
            pg.get("policyDefaults", {}).get("placement", {}).get("labelSelector", {})
        )
        label = label_selector.get("cluster-version", "")

        def ver_match(val):
            return target_ver in val or target_ver.replace(".", "") in val.replace(
                ".", ""
            ).replace("-", "")

        checks.append(
            (
                f"name_bump_{name}",
                ver_match(name),
                f"metadata.name '{name}' must contain {target_ver}",
            )
        )
        checks.append(
            (
                f"ns_bump_{name}",
                ver_match(ns),
                f"namespace '{ns}' in {name} must contain {target_ver}",
            )
        )
        checks.append(
            (
                f"label_bump_{name}",
                target_ver in label,
                f"cluster-version label '{label}' in {name} must contain {target_ver}",
            )
        )

    total = len(checks)
    num_passed = sum(1 for _, passed, _ in checks if passed)

    return {
        "pass_": num_passed == total,
        "score": num_passed / total,
        "reason": f"{num_passed}/{total} multi-PG structure checks passed",
        "component_results": [
            {
                "pass_": bool(passed),
                "score": 1.0 if passed else 0.0,
                "reason": f"{name}: {why}",
            }
            for name, passed, why in checks
        ],
    }


def check_wave_change_flagged(output, _context):
    """Agent must flag that StorageLV moved from wave 2 to wave 10 in ref-4.20.

    Scored:
      1.0 — mentions StorageLV/LVMCluster AND wave/ordering change
      0.5 — mentions StorageLV but not the wave change
      0.0 — no mention
    """
    text = (output or "").lower()

    mentions_storage = bool(re.search(r"storagelv|lvmcluster|storage.lv", text))
    mentions_wave = bool(
        re.search(r"wave.*chang|wave.*mov|wave.*2.*10|deploy.*wave|reorder", text)
    )

    if mentions_storage and mentions_wave:
        return {
            "pass_": True,
            "score": 1,
            "reason": "StorageLV wave change (2->10) flagged",
        }

    if mentions_storage:
        return {
            "pass_": True,
            "score": 0.5,
            "reason": "StorageLV mentioned but wave change not flagged",
        }

    return {
        "pass_": False,
        "score": 0,
        "reason": "StorageLV wave change (2->10) not flagged",
    }


def check_cr_replication(_output, context):
    """Both PtpConfigSlave instances must appear in output with ref-4.20 updates.

    Checks:
    - 2 PtpConfigSlave manifest entries in written PG
    - Both updated with scheduling fields (ptpSchedulingPolicy/Priority)
    - Both preserve their respective interface patches (ens7f0, ens8f0)
    """
    written = _collect_written_files(context)

    ptp_instances = []
    for content in written.values():
        try:
            for doc in yaml.safe_load_all(content):
                if not doc or doc.get("kind") != "PolicyGenerator":
                    continue
                for policy in doc.get("policies", []):
                    for m in policy.get("manifests", []):
                        if "ptpconfigslave" in m.get("path", "").lower():
                            ptp_instances.append(m)
        except yaml.YAMLError, AttributeError:
            continue

    def patches_str(m):
        return str(m.get("patches", []))

    found_two = len(ptp_instances) >= 2

    both_updated = (
        all(
            "ptpSchedulingPolicy" in patches_str(m)
            or "SCHED_FIFO" in patches_str(m)
            or "ptpSchedulingPriority" in patches_str(m)
            for m in ptp_instances
        )
        if ptp_instances
        else False
    )

    interfaces = [patches_str(m) for m in ptp_instances]
    both_interfaces = (
        (
            any("ens7f0" in i for i in interfaces)
            and any("ens8f0" in i for i in interfaces)
        )
        if len(interfaces) >= 2
        else False
    )

    checks = [
        (
            "two_instances",
            found_two,
            f"Expected 2 PtpConfigSlave instances, found {len(ptp_instances)}",
        ),
        (
            "both_updated",
            both_updated,
            "Both instances must have scheduling fields from ref-4.20",
        ),
        (
            "both_interfaces",
            both_interfaces,
            "Both instances must preserve their respective interface patches",
        ),
    ]

    total = len(checks)
    num_passed = sum(1 for _, passed, _ in checks if passed)

    return {
        "pass_": num_passed == total,
        "score": num_passed / total,
        "reason": f"{num_passed}/{total} CR replication checks passed",
        "component_results": [
            {
                "pass_": bool(passed),
                "score": 1.0 if passed else 0.0,
                "reason": f"{name}: {why}",
            }
            for name, passed, why in checks
        ],
    }


def check_mustnothave_warning(output, _context):
    """Agent must warn about partner overlays on a CR marked mustnothave in ref.

    ConsoleOperatorDisable has partner patches (logLevel: Debug) but ref-4.20
    PG example marks it complianceType: mustnothave. Agent should flag the
    conflict between the partner's customizations and the removal directive.

    Scored:
      1.0 — mentions Console + mustnothave/removal + overlay/patch conflict
      0.7 — mentions Console + mustnothave/removal
      0.3 — mentions Console but not the mustnothave issue
      0.0 — no mention
    """
    text = (output or "").lower()

    mentions_console = bool(re.search(r"console|consoleoperatordisable", text))
    mentions_removal = bool(
        re.search(
            r"mustnothave|must.?not.?have|remov|no longer|deprecat|cleanup|deleted",
            text,
        )
    )
    mentions_conflict = bool(
        re.search(r"overlay|patch|customiz|conflict|warn|logLevel|log.?level", text)
    )

    if mentions_console and mentions_removal and mentions_conflict:
        return {
            "pass_": True,
            "score": 1,
            "reason": "ConsoleOperatorDisable mustnothave + overlay conflict flagged",
        }

    if mentions_console and mentions_removal:
        reason = "Console mustnothave flagged, overlay conflict not explicit"
        return {"pass_": True, "score": 0.7, "reason": reason}

    if mentions_console:
        return {
            "pass_": True,
            "score": 0.3,
            "reason": "Console mentioned but mustnothave not flagged",
        }

    return {
        "pass_": False,
        "score": 0,
        "reason": "ConsoleOperatorDisable mustnothave warning not found",
    }


def check_renamed_pg_binding(_output, context):
    """Agent must update placement labels even when PG name has no version pattern.

    The partner's PG is named 'acme-cluster-baseline' (no '4.18' in the name).
    The agent must still bump placement.labelSelector.cluster-version to the
    target version.
    """
    config = context.get("config") or {}
    target_ver = config.get("target_version", "4.20")

    written = _collect_written_files(context)
    pg_docs = []

    for content in written.values():
        try:
            for doc in yaml.safe_load_all(content):
                if doc and doc.get("kind") == "PolicyGenerator":
                    pg_docs.append(doc)
        except yaml.YAMLError, AttributeError:
            continue

    if not pg_docs:
        return {"pass_": False, "score": 0, "reason": "No PolicyGenerator written"}

    pg = pg_docs[0]
    label = (
        pg.get("policyDefaults", {})
        .get("placement", {})
        .get("labelSelector", {})
        .get("cluster-version", "")
    )

    passed = target_ver in label
    return {
        "pass_": passed,
        "score": 1.0 if passed else 0.0,
        "reason": f"cluster-version label is '{label}', expected to contain {target_ver}",
    }


def check_required_cr_severity(output, _context):
    """Agent must warn about missing required CRs with appropriate severity.

    The partner omits TunedPerformancePatch and PtpConfigSlave, which are
    uncommented (required) in the reference PG examples. The agent should
    flag at least one of these with warning-level language.
    """
    text = (output or "").lower()

    tuned_warned = bool(
        re.search(
            r"tunedperformancepatch|tuned.*performance|performance.*patch|ran-du-performance",
            text,
        )
        and re.search(
            r"warn|miss|requir|absent|not.*includ|should.*add|recommend|not.*found",
            text,
        )
    )

    ptp_warned = bool(
        re.search(r"ptpconfigslave|ptp.*slave", text)
        and re.search(
            r"warn|miss|requir|absent|not.*includ|should.*add|recommend|not.*found",
            text,
        )
    )

    required_flagged = tuned_warned or ptp_warned

    checks = [
        (
            "required_cr_flagged",
            required_flagged,
            "At least one required missing CR (Tuned or PTP) must be warned about",
        ),
    ]

    total = len(checks)
    num_passed = sum(1 for _, passed, _ in checks if passed)

    return {
        "pass_": num_passed == total,
        "score": num_passed / total,
        "reason": f"{num_passed}/{total} required CR severity checks passed",
        "component_results": [
            {
                "pass_": bool(passed),
                "score": 1.0 if passed else 0.0,
                "reason": f"{name}: {why}",
            }
            for name, passed, why in checks
        ],
    }


def _collect_written_files(context):
    """Collect files the agent produced, method-agnostic.

    Tries toolCalls first (Write/Edit), falls back to disk (git status).
    """
    tool_calls = _tool_calls(context)
    written = _collect_from_tool_calls(tool_calls)
    if _has_policy_generator(written):
        return written

    disk_files = _collect_from_disk()
    if disk_files:
        written.update(disk_files)
    return written


def _collect_from_tool_calls(tool_calls):
    read_cache = {}
    for call in tool_calls:
        if call.get("name") == "Read":
            path = call.get("input", {}).get("file_path", "")
            content = call.get("output", "")
            if path and content:
                read_cache[path] = content

    written = {}
    for call in tool_calls:
        inp = call.get("input", {})
        path = inp.get("file_path", "")
        if call.get("name") == "Write":
            written[path] = inp.get("content", "")
        elif call.get("name") == "Edit":
            if path not in written:
                for read_path, content in read_cache.items():
                    if os.path.basename(read_path) == os.path.basename(path):
                        written[path] = content
                        break
                else:
                    written.setdefault(path, "")
            old = inp.get("old_string", "")
            new = inp.get("new_string", "")
            if old and old in written.get(path, ""):
                written[path] = written[path].replace(old, new, 1)

    return written


def _collect_from_disk():
    written = {}
    for partner_dir in _find_partner_dirs():
        git_dir = os.path.join(partner_dir, ".git")
        if not os.path.isdir(git_dir):
            continue
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                cwd=partner_dir,
                capture_output=True,
                text=True,
            )
            new_result = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                cwd=partner_dir,
                capture_output=True,
                text=True,
            )
            for rel_path in (
                result.stdout.strip().splitlines()
                + new_result.stdout.strip().splitlines()
            ):
                full = os.path.join(partner_dir, rel_path)
                if os.path.isfile(full) and rel_path.endswith((".yaml", ".yml")):
                    with open(full) as f:
                        written[full] = f.read()
        except OSError, subprocess.SubprocessError:
            continue

    for tmp_dir in glob.glob("/tmp/rds-merge-*"):
        if not os.path.isdir(tmp_dir):
            continue
        for root, _, files in os.walk(tmp_dir):
            for fname in files:
                if fname.endswith((".yaml", ".yml")):
                    full = os.path.join(root, fname)
                    with open(full) as f:
                        written[full] = f.read()

    return written


def _find_partner_dirs():
    if not os.path.isdir(FIXTURES_DIR):
        return []
    return [
        os.path.join(FIXTURES_DIR, d)
        for d in os.listdir(FIXTURES_DIR)
        if d.startswith("partner-") and os.path.isdir(os.path.join(FIXTURES_DIR, d))
    ]


def _has_policy_generator(written):
    for content in written.values():
        try:
            for doc in yaml.safe_load_all(content):
                if doc and doc.get("kind") == "PolicyGenerator":
                    return True
        except yaml.YAMLError, AttributeError:
            continue
    return False


def _tool_calls(context):
    provider_response = context.get("providerResponse") or {}
    metadata = provider_response.get("metadata", {})
    return metadata.get("toolCalls", [])
