"""Structural assertions — multi-PG preservation, CR replication, file checks.

Promptfoo Python assertion return format (GradingResult):
    {"pass_": bool, "score": float 0-1, "reason": str}
    Snake_case keys auto-convert to camelCase.

All CR-specific values come from config in promptfooconfig.yaml.

Communication checks (wave change flagging, mustnothave warning,
required CR severity) are handled by llm-rubric in promptfooconfig.yaml.
"""

from pathlib import Path

import jmespath

from common import (
    collect_written_files,
    parse_pg_docs,
    version_matches,
)


def _fmt(name, passed, expected, actual):
    status = "PASS" if passed else "FAIL"
    return f"{status} {name} | EXPECTED: {expected} | ACTUAL: {actual}"


def check_multi_pg_structure(_output, context):
    """Agent must preserve multi-PG file structure and apply version bumps to all."""
    config = context["config"]
    target_ver = config["target_version"]

    written = collect_written_files(context)
    pg_docs, _skipped = parse_pg_docs(written)

    checks = [
        (
            "multi_pg_preserved",
            len(pg_docs) >= 2,
            ">=2 PolicyGenerator files",
            f"found {len(pg_docs)} PG docs in {len(written)} written files",
        ),
    ]

    for i, pg in enumerate(pg_docs):
        pg_name = pg.get("metadata", {}).get("name", f"pg-{i}")
        ns = pg.get("policyDefaults", {}).get("namespace", "")
        label = (
            pg.get("policyDefaults", {})
            .get("placement", {})
            .get("labelSelector", {})
            .get("cluster-version", "")
        )

        checks.append(
            (
                f"name_bump_{pg_name}",
                version_matches(pg_name, target_ver),
                f"metadata.name contains {target_ver}",
                f"metadata.name='{pg_name}'",
            )
        )
        checks.append(
            (
                f"ns_bump_{pg_name}",
                version_matches(ns, target_ver),
                f"namespace contains {target_ver}",
                f"namespace='{ns}'",
            )
        )
        checks.append(
            (
                f"label_bump_{pg_name}",
                target_ver in label,
                f"cluster-version label contains {target_ver}",
                f"cluster-version='{label}'",
            )
        )

    total = len(checks)
    num_passed = sum(1 for _, passed, _, _ in checks if passed)

    return {
        "pass_": num_passed == total,
        "score": num_passed / total,
        "reason": f"{num_passed}/{total} multi-PG structure checks passed",
        "component_results": [
            {
                "pass_": bool(passed),
                "score": 1.0 if passed else 0.0,
                "reason": _fmt(name, passed, expected, actual),
            }
            for name, passed, expected, actual in checks
        ],
    }


def check_cr_replication(_output, context):
    """CR instances must all appear with reference updates applied."""
    config = context["config"]
    ptp = config["ptp"]
    ptp_cr = ptp["cr"]
    expected_count = ptp["expected_count"]
    sched_paths = ptp["sched_paths"]
    iface_path = ptp["interface_path"]
    expected_interfaces = ptp["expected_interfaces"]

    written = collect_written_files(context)
    pg_docs, _skipped = parse_pg_docs(written)

    instances = []
    for pg in pg_docs:
        for policy in pg.get("policies", []):
            for m in policy.get("manifests", []):
                if ptp_cr in m.get("path", "").lower():
                    instances.append(m)

    details = []
    for i, m in enumerate(instances):
        has_sched = any(bool(jmespath.search(sp, m)) for sp in sched_paths)
        ifaces = jmespath.search(iface_path, m) or []
        details.append({"index": i, "has_sched": has_sched, "interfaces": ifaces})

    all_updated = all(d["has_sched"] for d in details) if details else False
    all_ifaces = [iface for d in details for iface in d["interfaces"]]
    all_ifaces_found = (
        all(ei in all_ifaces for ei in expected_interfaces)
        if len(instances) >= expected_count
        else False
    )

    checks = [
        (
            "instance_count",
            len(instances) >= expected_count,
            f">={expected_count} {ptp_cr} instances",
            f"found {len(instances)}",
        ),
        (
            "all_updated",
            all_updated,
            "all instances have scheduling fields",
            f"{[d['has_sched'] for d in details]}",
        ),
        (
            "all_interfaces",
            all_ifaces_found,
            f"all of {expected_interfaces} present",
            f"found: {all_ifaces}",
        ),
    ]

    total = len(checks)
    num_passed = sum(1 for _, passed, _, _ in checks if passed)

    return {
        "pass_": num_passed == total,
        "score": num_passed / total,
        "reason": f"{num_passed}/{total} CR replication checks passed",
        "component_results": [
            {
                "pass_": bool(passed),
                "score": 1.0 if passed else 0.0,
                "reason": _fmt(name, passed, expected, actual),
            }
            for name, passed, expected, actual in checks
        ],
    }


def check_parent_kustomization(_output, context):
    """Agent must update parent kustomization.yaml if one exists in the partner fixture."""
    config = context["config"]
    target_ver = config["target_version"]

    written = collect_written_files(context)

    kustomization_found = False
    kustomization_content = ""
    contains_version = False

    for path, content in written.items():
        if "kustomization" in path.lower():
            kustomization_found = True
            kustomization_content = content[:200]
            if version_matches(content, target_ver):
                contains_version = True

    if kustomization_found and contains_version:
        return {
            "pass_": True,
            "score": 1.0,
            "reason": _fmt(
                "parent_kustomization",
                True,
                f"kustomization.yaml with {target_ver}",
                f"found and contains {target_ver}",
            ),
        }

    if kustomization_found:
        return {
            "pass_": False,
            "score": 0.5,
            "reason": _fmt(
                "parent_kustomization",
                False,
                f"kustomization.yaml with {target_ver}",
                f"found but missing {target_ver}: {kustomization_content}",
            ),
        }

    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    has_input_kustomization = any(fixtures_dir.rglob("kustomization*"))
    if not has_input_kustomization:
        return {
            "pass_": True,
            "score": 1.0,
            "reason": _fmt(
                "parent_kustomization",
                True,
                "kustomization.yaml if fixture has one",
                "no kustomization in fixture",
            ),
        }

    return {
        "pass_": False,
        "score": 0.0,
        "reason": _fmt(
            "parent_kustomization",
            False,
            "kustomization.yaml written with target version",
            f"fixture has kustomization but agent did not write one ({len(written)} files written)",
        ),
    }
