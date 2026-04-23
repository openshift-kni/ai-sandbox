"""Merge assertions — artifact correctness, conflict communication, checklist.

Promptfoo Python assertion return format (GradingResult):
    {"pass_": bool, "score": float 0-1, "reason": str}

Snake_case keys are auto-converted to camelCase by promptfoo:
    pass_ -> pass, component_results -> componentResults.

Assertions that need version info read source_version and
target_version from context["config"].
"""

import glob
import os
import re
import subprocess

import yaml

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def check_file_content(_output, context):
    """Verify the merge produced correct YAML artifacts.

    Parses the PolicyGenerator YAML the agent wrote and checks:
    - GVK migration: DisconnectedIDMS path (not ICSP)
    - Partner customizations: registry mirror, kernel tuning survive merge
    - Version bumps: metadata.name, namespace, placement label
    - Profile rename: ran-du-performance
    - Custom CR: AcmeMonitoring carried through
    - PTP variant: PtpConfigSlave updated with scheduling fields
    """
    config = context.get("config") or {}
    target_ver = config.get("target_version", "4.20")

    written = _collect_written_files(context)

    if not written:
        return {"pass_": False, "score": 0, "reason": "No files written during merge"}

    # Parse ALL PolicyGenerator YAMLs from written files (handles multi-PG)
    pg_docs = []
    for content in written.values():
        try:
            for doc in yaml.safe_load_all(content):
                if doc and doc.get("kind") == "PolicyGenerator":
                    pg_docs.append(doc)
        except yaml.YAMLError, AttributeError:
            continue

    if not pg_docs:
        return {
            "pass_": False,
            "score": 0,
            "reason": "No PolicyGenerator YAML found in written files",
        }

    # Use first PG for metadata/version checks
    policy_gen = pg_docs[0]
    metadata_name = policy_gen.get("metadata", {}).get("name", "")
    defaults = policy_gen.get("policyDefaults", {})
    namespace = defaults.get("namespace", "")
    cluster_version = (
        defaults.get("placement", {})
        .get("labelSelector", {})
        .get("cluster-version", "")
    )

    # Collect manifests from ALL PGs into a flat list
    all_manifests = [
        m
        for pg in pg_docs
        for policy in pg.get("policies", [])
        for m in policy.get("manifests", [])
    ]
    by_path = {}
    for m in all_manifests:
        path = m.get("path", "").lower()
        by_path[path] = m

    def find(substring):
        for m in all_manifests:
            if substring in m.get("path", "").lower():
                return m
        return None

    def find_with(substring, patch_term):
        for m in all_manifests:
            if substring in m.get("path", "").lower():
                if patch_term in str(m.get("patches", [])):
                    return m
        return find(substring)

    def patches_str(m):
        return str(m.get("patches", [])) if m else ""

    idms = find("disconnectedidms")
    icsp = find("disconnectedicsp")
    tuned = find("tunedperformancepatch")
    ptp = find_with("ptpconfigslave", "ptpSchedulingPolicy")
    monitoring = find("acmemonitoring")

    checks = [
        (
            "gvk_path",
            idms is not None and icsp is None,
            "Manifest path must reference DisconnectedIDMS, not ICSP",
        ),
        (
            "mirror_preserved",
            idms is not None and "registry.acme.example.com" in patches_str(idms),
            "DisconnectedIDMS patches must include partner registry mirror",
        ),
        (
            "timer_migration",
            tuned is not None and "kernel.timer_migration" in patches_str(tuned),
            "TunedPerformancePatch patches must preserve kernel.timer_migration=0",
        ),
        (
            "version_bump_name",
            target_ver in metadata_name
            or target_ver.replace(".", "")
            in metadata_name.replace(".", "").replace("-", ""),
            f"metadata.name '{metadata_name}' must contain {target_ver}",
        ),
        (
            "version_bump_ns",
            target_ver in namespace
            or target_ver.replace(".", "")
            in namespace.replace(".", "").replace("-", ""),
            f"policyDefaults.namespace '{namespace}' must contain {target_ver}",
        ),
        (
            "version_bump_label",
            target_ver in cluster_version,
            f"placement label cluster-version '{cluster_version}' must contain {target_ver}",
        ),
        (
            "profile_rename",
            tuned is not None and "ran-du-performance" in patches_str(tuned),
            "TunedPerformancePatch must reference profile ran-du-performance",
        ),
        (
            "custom_cr_path",
            monitoring is not None,
            "Manifests must include partner-only AcmeMonitoring CR",
        ),
        (
            "ptp_one_of",
            ptp is not None
            and (
                "ptpSchedulingPolicy" in patches_str(ptp)
                or "SCHED_FIFO" in patches_str(ptp)
                or "ptpSchedulingPriority" in patches_str(ptp)
            ),
            "PtpConfigSlave must be updated with scheduling fields",
        ),
    ]

    total = len(checks)
    num_passed = sum(1 for _, passed, _ in checks if passed)

    return {
        "pass_": num_passed == total,
        "score": num_passed / total,
        "reason": f"{num_passed}/{total} artifact checks passed",
        "component_results": [
            {
                "pass_": bool(passed),
                "score": 1.0 if passed else 0.0,
                "reason": f"{name}: {why}",
            }
            for name, passed, why in checks
        ],
    }


def check_conflict_flagging(output, _context):
    """Agent must tell the user about the priority conflict, not silently resolve it.

    The reference changes Tuned priority from 19 to 18, but the partner
    explicitly patches 19. The agent should flag this for human review.

    Scored by how clearly the conflict is communicated:
      1.0 — mentions "priority" with both values (19 and 18)
      0.8 — mentions "priority" with review/conflict language
      0.5 — mentions "priority" but doesn't flag the conflict
      0.0 — doesn't mention priority at all
    """
    text = (output or "").lower()

    mentions_priority = "priority" in text
    mentions_both_values = "19" in text and "18" in text
    mentions_review = re.search(r"flag|review|conflict|confirm|decision|ask", text)

    if mentions_priority and mentions_both_values:
        return {
            "pass_": True,
            "score": 1,
            "reason": "Priority conflict (19->18) flagged with both values",
        }

    if mentions_priority and mentions_review:
        return {
            "pass_": True,
            "score": 0.8,
            "reason": "Priority mentioned with review flag",
        }

    if mentions_priority:
        return {
            "pass_": True,
            "score": 0.5,
            "reason": "Priority mentioned but conflict not clearly flagged",
        }

    return {
        "pass_": False,
        "score": 0,
        "reason": "Priority conflict (19->18) not flagged in output",
    }


def check_overlay_lifecycle(output, context):
    """Agent must warn the user about overlay conflicts and CR lifecycle changes.

    Required (fails the test if missing):
      - Channel conflict: partner pins source version channel, ref moves to target
      - CR removal: NMState exists in partner but was removed in target refs

    Optional (lowers score but still passes):
      - Redundant overlay: installPlanApproval matches both refs
      - Coverage gap: SriovFecClusterConfig in refs but partner doesn't use
      - Duplicate CR: AcmePtpConfig is a fork of reference PtpConfigSlave
    """
    config = context.get("config") or {}
    source_ver = config.get("source_version", "4.18")
    target_ver = config.get("target_version", "4.20")
    text = (output or "").lower()

    required = [
        (
            "channel_conflict",
            re.search(r"channel", text)
            and re.search(r"stable|subscri", text)
            and re.search(
                r"conflict|pinned|flag|review|confirm|update|mismatch|intentional", text
            ),
            f"Must flag Subscription channel conflict ({source_ver} -> {target_ver})",
        ),
        (
            "cr_removal",
            re.search(r"nmstate", text)
            and re.search(
                r"remov|deprecat|absent|no longer|dropped|not.*found|not.*exist|missing",
                text,
            ),
            f"Must warn NMState is removed in {target_ver} but partner uses it",
        ),
    ]

    optional = [
        (
            "redundant_overlay",
            re.search(r"installplanapproval|installplan", text)
            and re.search(
                r"redundan|unnecessar|same.*value|already|match.*ref|no.?op|identical",
                text,
            ),
            "Optional: note installPlanApproval patch is redundant",
        ),
        (
            "coverage_scan",
            re.search(r"sriovfec|fecclusterconfig", text)
            and re.search(r"not.*(includ|use)|n/a|missing|absent|not.*partner|-", text),
            "Optional: note SriovFecClusterConfig not used by partner",
        ),
        (
            "duplicate_cr",
            re.search(r"acmeptpconfig|acme.*ptp", text)
            and re.search(
                r"duplic|fork|copy|variant|similar|same.*gvk|already.*ref|use.*reference",
                text,
            ),
            "Optional: detect AcmePtpConfig as a fork of reference PtpConfigSlave",
        ),
    ]

    all_checks = required + optional
    req_failed = [name for name, passed, _ in required if not passed]
    num_passed = sum(1 for _, passed, _ in all_checks if passed)
    total = len(all_checks)

    return {
        "pass_": len(req_failed) == 0,
        "score": num_passed / total,
        "reason": f"{num_passed}/{total} overlay/lifecycle checks passed",
        "component_results": [
            {
                "pass_": bool(passed),
                "score": 1.0 if passed else 0.0,
                "reason": f"{name}: {why}",
            }
            for name, passed, why in all_checks
        ],
    }


def check_completeness(_output, context):
    """Agent must produce a checklist file that covers every merge task.

    Inspects Write tool calls for checklist files. The checklist is a
    working document created during EXPLAIN and updated during MERGE.

    Required items: ICSP->IDMS pair, profile rename, NMState removal
    flag, channel change, AcmeMonitoring as partner CR, version bumps.
    Optional: SriovFec marked N/A.
    """
    written = _collect_written_files(context)

    checklist_contents = []
    for path, content in written.items():
        if re.search(r"checklist|completed", path, re.IGNORECASE):
            checklist_contents.append(content)

    checklist = "\n".join(checklist_contents).lower()

    if not checklist:
        return {"pass_": False, "score": 0, "reason": "No checklist file written"}

    required = [
        (
            "gvk_pair",
            "disconnectedicsp" in checklist and "disconnectedidms" in checklist,
            "Must list ICSP -> IDMS GVK migration",
        ),
        (
            "tuned_rename",
            "performance-patch" in checklist and "ran-du-performance" in checklist,
            "Must list profile rename performance-patch -> ran-du-performance",
        ),
        (
            "nmstate_removal",
            "nmstate" in checklist
            and re.search(r"remov|absent|flag|review|deprecat", checklist),
            "Must flag NMState as removed/deprecated",
        ),
        (
            "channel_change",
            "channel" in checklist and re.search(r"stable|subscri", checklist),
            "Must list Subscription channel change",
        ),
        (
            "custom_cr",
            re.search(r"acmemonitoring|acme.*monitoring", checklist),
            "Must list AcmeMonitoring in checklist",
        ),
        (
            "version_bump",
            re.search(r"metadata\.name|metadata.*name", checklist)
            and "namespace" in checklist
            and re.search(r"label|placement", checklist),
            "Must include version bumping section (name, namespace, labels)",
        ),
    ]

    optional = [
        (
            "sriov_na",
            "sriovfec" in checklist
            and re.search(r"n/a|not.*use|partner.*not|doesn.*use", checklist),
            "Optional: note SriovFec as N/A (partner does not use)",
        ),
    ]

    all_checks = required + optional
    req_failed = [name for name, passed, _ in required if not passed]
    num_passed = sum(1 for _, passed, _ in all_checks if passed)
    total = len(all_checks)

    return {
        "pass_": len(req_failed) == 0,
        "score": num_passed / total,
        "reason": f"{num_passed}/{total} checklist items found",
        "component_results": [
            {
                "pass_": bool(passed),
                "score": 1.0 if passed else 0.0,
                "reason": f"{name}: {why}",
            }
            for name, passed, why in all_checks
        ],
    }


def check_list_merge(output, _context):
    """Agent must acknowledge the Tuned 1-to-4 profile list restructure.

    The reference changes TunedPerformancePatch from 1 profile to 4
    (ran-du-performance + architecture-specific sub-profiles). The agent
    should communicate this structural change to the user.

    Optional check — lowers score but does not fail the test.
    """
    text = (output or "").lower()

    aware = bool(
        re.search(r"architecture.*(specific|common|profile)", text)
        or re.search(r"profile.*(restructur|split|reorganiz|refactor)", text)
        or re.search(r"(x86|aarch64).*profile", text)
        or re.search(r"multiple.*profile|profile.*multiple", text)
        or re.search(r"ran-du.*common", text)
        or re.search(r"sub.?profile", text)
    )

    if aware:
        return {
            "pass_": True,
            "score": 1,
            "reason": "Agent acknowledged Tuned profile restructure",
        }

    return {
        "pass_": True,
        "score": 0,
        "reason": "Agent did not mention Tuned 1-to-4 profile restructure (optional)",
    }


def _collect_written_files(context):
    """Collect files the agent produced, method-agnostic.

    First tries toolCalls (Write/Edit). If that finds no PolicyGenerator
    YAML, falls back to reading new/modified files from disk via git.
    This handles agents that write via Bash (cp, sed, cat >) instead of
    the Write/Edit tools.
    """
    tool_calls = _tool_calls(context)
    written = _collect_from_tool_calls(tool_calls)
    if _has_policy_generator(written):
        return written

    disk_files = _collect_from_disk(context)
    if disk_files:
        written.update(disk_files)
    return written


def _collect_from_tool_calls(tool_calls):
    """Reconstruct file contents from Write and Edit tool calls."""
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


def _collect_from_disk(context):
    """Read new/modified files from partner directories on disk."""
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
            changed = result.stdout.strip().splitlines()
            untracked = new_result.stdout.strip().splitlines()
            for rel_path in changed + untracked:
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
    """Find partner-* directories in fixtures."""
    if not os.path.isdir(FIXTURES_DIR):
        return []
    return [
        os.path.join(FIXTURES_DIR, d)
        for d in os.listdir(FIXTURES_DIR)
        if d.startswith("partner-") and os.path.isdir(os.path.join(FIXTURES_DIR, d))
    ]


def _has_policy_generator(written):
    """Check if any written file contains a PolicyGenerator document."""
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
