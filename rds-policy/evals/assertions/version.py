"""Version assertions — semver sweep and version-bearing field checks.

Promptfoo Python assertion return format (GradingResult):
    {"pass_": bool, "score": float 0-1, "reason": str}
    Snake_case keys auto-convert to camelCase.
"""

import re

from common import collect_written_files, parse_pg_docs

# Markers the skill uses for a value it kept for the partner to decide:
# `[~] ⚠ REVIEW` for version pins, `[!]` for conflicts.
REVIEW_MARKER = re.compile(r"⚠|\[~\]|\[!\]|\breview\b", re.IGNORECASE)
# A markdown item starts with a bullet, a numbered entry, a table row or a
# heading. Following non-blank lines are its continuation.
ITEM_START = re.compile(r"\s*(?:[-*+]\s|\d+[.)]\s|\||#)")


def _markdown_items(text):
    """Split markdown into items, each a bullet or paragraph with its continuation lines."""
    items, current = [], []
    for line in text.splitlines():
        if not line.strip() or ITEM_START.match(line):
            if current:
                items.append(" ".join(current))
            current = [line.strip()] if line.strip() else []
        else:
            current.append(line.strip())
    if current:
        items.append(" ".join(current))
    return items


def _flag_items(output, written):
    """Items in checklist.md and the final output that carry a review marker."""
    texts = [output or ""]
    texts += [c for p, c in written.items() if p.rsplit("/", 1)[-1] == "checklist.md"]
    return [i for t in texts for i in _markdown_items(t) if REVIEW_MARKER.search(i)]


def _is_flagged(token, flag_items):
    """True if an item with a review marker names this exact version value."""
    pat = re.compile(rf"(?<![0-9.]){re.escape(token)}(?![0-9A-Za-z]|[._-][0-9A-Za-z])")
    return any(pat.search(item) for item in flag_items)


def check_semver_sweep(output, context):
    """No source version string should remain unflagged in the output PolicyGenerator files.

    Scans all written PG YAML files for the source OCP version (e.g. "4.18").
    Matches both dotted (4.18) and hyphenated (4-18) forms. The skill keeps
    version-pinned values (e.g. an IBU seedImageRef or a z-stream
    target-ocp-version) and flags them for review instead of guessing a
    target value, so a remaining value passes when checklist.md or the final
    output flags it: an item with a review marker (⚠, REVIEW, [~] or [!])
    that names the exact value (e.g. 4.18.13). Any other remaining
    occurrence is a missed version bump.
    """
    config = context.get("config") or {}
    source_version = config.get("source_version", "4.18")

    written = collect_written_files(context)
    if not written:
        return {
            "pass_": False,
            "score": 0,
            "reason": "No written files found",
        }

    pg_docs, _ = parse_pg_docs(written)
    if not pg_docs:
        return {
            "pass_": False,
            "score": 0,
            "reason": "No PolicyGenerator docs found in written files",
        }

    parts = source_version.split(".")
    if len(parts) < 2:
        return {
            "pass_": False,
            "score": 0,
            "reason": f"Invalid source_version '{source_version}' (expected major.minor)",
        }
    major, minor = parts[0], parts[1]
    patterns = [
        re.compile(rf"{major}\.{minor}(?!\d)"),
        re.compile(rf"{major}-{minor}(?!\d)"),
        re.compile(rf"{major}_{minor}(?!\d)"),
    ]
    # The whole value around a match: "4.18.13", "stable-4.18", "acme-v4-18"
    value_pattern = re.compile(rf"[\w.-]*{major}[._-]{minor}(?!\d)[\w.-]*")
    flag_items = _flag_items(output, written)

    flagged, unflagged = [], []
    for filepath, content in written.items():
        if filepath.endswith(".md"):
            continue
        for line_num, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            value_part = re.split(r"\s+#\s", line, maxsplit=1)[0]
            if not any(pat.search(value_part) for pat in patterns):
                continue
            hit = f"{filepath}:{line_num}: {stripped[:100]}"
            tokens = {
                m.group().strip("._-") for m in value_pattern.finditer(value_part)
            }
            if tokens and all(_is_flagged(t, flag_items) for t in tokens):
                flagged.append(hit)
            else:
                unflagged.append(hit)

    component_results = [
        {"pass_": False, "score": 0, "reason": f"unflagged: {h}"}
        for h in unflagged[:10]
    ] + [
        {"pass_": True, "score": 1.0, "reason": f"flagged for review: {h}"}
        for h in flagged[:10]
    ]

    if unflagged:
        return {
            "pass_": False,
            "score": max(0, 1 - len(unflagged) / 10),
            "reason": (
                f"Source version {source_version} found in {len(unflagged)} lines "
                f"not flagged for review ({len(flagged)} flagged)"
            ),
            "component_results": component_results,
        }

    if flagged:
        return {
            "pass_": True,
            "score": 1.0,
            "reason": (
                f"Source version {source_version} remains in {len(flagged)} lines, "
                "all flagged for review in checklist.md or the final output"
            ),
            "component_results": component_results,
        }

    return {
        "pass_": True,
        "score": 1.0,
        "reason": f"No source version {source_version} found in output files",
    }
