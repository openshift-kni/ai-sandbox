"""Shared utilities for eval assertions — file collection, PG parsing, manifest lookup."""

import json
import os
import re
from pathlib import Path

import yaml

PG_REQUIRED_KEYS = {"metadata", "policyDefaults", "policies"}
WRITTEN_SUFFIXES = (".yaml", ".yml", ".md")
# Per-run output dir from SKILL.md: /tmp/rds-merge-{target}-{timestamp}/
OUTPUT_DIR_RE = re.compile(r"/tmp/rds-merge-[\w.]+-\d{8}-\d{6}")


def fmt_check(name, passed, expected, actual):
    status = "PASS" if passed else "FAIL"
    return f"{status} {name} | EXPECTED: {expected} | ACTUAL: {actual}"


def collect_written_files(context=None):
    """Read all files the agent wrote, extracted from toolCalls metadata.

    When context is provided, combines Write/Edit tool-call paths with the
    files under this session's output dir, so files the agent wrote via Bash
    (cp, sed -i, heredocs) count too. Output-dir files identical to a fixture
    input (pristine partner/reference copies) or to an already-collected file
    are skipped. Falls back to globbing /tmp/rds-merge-*/ if context is
    unavailable or names neither.
    """
    paths = _paths_from_context(context)
    dirs = _output_dirs_from_context(context)
    if paths or dirs:
        written = {}
        for p in paths:
            f = Path(p)
            if f.exists() and f.suffix in WRITTEN_SUFFIXES:
                written[str(f)] = f.read_text()
        seen = set(written.values()) | _fixture_contents()
        for d in sorted(dirs):
            for f in sorted(Path(d).rglob("*")):
                if not f.is_file() or f.suffix not in WRITTEN_SUFFIXES:
                    continue
                content = f.read_text()
                if content not in seen:
                    seen.add(content)
                    written[str(f)] = content
        return written

    written = {}
    for d in Path("/tmp").glob("rds-merge-*"):
        if not d.is_dir():
            continue
        for ext in ("*.yaml", "*.yml", "*.md"):
            for f in d.rglob(ext):
                written[str(f)] = f.read_text()
    return written


def _paths_from_context(context):
    """Extract file paths from Write and Edit tool calls in promptfoo metadata.

    The agent may use Write for new files or Edit for incremental changes
    (e.g. cp the partner file via Bash, then Edit to apply merge changes).
    """
    paths = set()
    for call in _tool_calls(context):
        if call.get("name") not in ("Write", "Edit"):
            continue
        raw = call.get("input", "")
        try:
            args = json.loads(raw) if isinstance(raw, str) else raw
            fp = args.get("file_path", "")
            if fp:
                paths.add(fp)
        except (json.JSONDecodeError, AttributeError):
            continue
    return list(paths)


def _output_dirs_from_context(context):
    """Output dirs named in tool-call inputs or the agent's final output.

    Tool outputs are not scanned: a listing of /tmp could name stale dirs
    from earlier runs.
    """
    texts = [str(call.get("input", "")) for call in _tool_calls(context)]
    texts.append(str(((context or {}).get("providerResponse") or {}).get("output", "")))
    return {d for t in texts for d in OUTPUT_DIR_RE.findall(t)}


def _tool_calls(context):
    if not context:
        return []
    provider_response = context.get("providerResponse") or {}
    metadata = provider_response.get("metadata") or context.get("metadata") or {}
    return metadata.get("toolCalls") or []


def _fixture_contents():
    """Contents of the fixture inputs the agent copies into its output dir."""
    default = Path(__file__).resolve().parent.parent / "fixtures"
    fixtures = Path(os.environ.get("RDS_FIXTURES_DIR") or default)
    return {
        f.read_text()
        for f in fixtures.rglob("*")
        if f.is_file() and f.suffix in WRITTEN_SUFFIXES
    }


def parse_pg_docs(written, *, strict=False):
    """Parse PolicyGenerator documents from file contents.

    Returns (pg_docs, skipped) where skipped is a list of
    {"kind": str, "file": str} dicts describing non-PG docs
    and {"error": str, "file": str} dicts for parse failures.
    """
    pg_docs = []
    skipped = []
    for filepath, content in written.items():
        if filepath.endswith(".md"):
            continue
        try:
            for doc in yaml.safe_load_all(content):
                if not doc:
                    continue
                kind = doc.get("kind")
                if kind != "PolicyGenerator":
                    skipped.append({"kind": kind or "(no kind)", "file": filepath})
                    continue
                if strict:
                    missing = PG_REQUIRED_KEYS - set(doc.keys())
                    if missing:
                        raise ValueError(f"PolicyGenerator missing keys: {missing}")
                pg_docs.append(doc)
        except (yaml.YAMLError, AttributeError) as exc:
            skipped.append({"error": str(exc)[:100], "file": filepath})
    return pg_docs, skipped


def collect_manifests(pg_docs):
    """Flatten all manifests from parsed PolicyGenerator docs."""
    return [
        m
        for pg in pg_docs
        for policy in pg.get("policies", [])
        for m in policy.get("manifests", [])
    ]


def find_first(all_manifests, substring):
    """Find first manifest whose path contains substring."""
    return next(
        (m for m in all_manifests if substring.lower() in m.get("path", "").lower()),
        None,
    )


def version_matches(value, version):
    """True if version appears in value, ignoring separator differences.

    version_matches("acme-config-v4-20", "4.20") → True  (4-20 vs 4.20)
    version_matches("acme-config-v420", "4.20")  → True  (420 vs 4.20)
    version_matches("acme-config-v4-18", "4.20") → False
    """
    if not value or not version:
        return False
    if version in value:
        return True
    return re.sub(r"[.\-_]", "", version) in re.sub(r"[.\-_]", "", value)


def enrich_output(output, context):
    """Promptfoo assertion transform: append .md files the agent wrote to output.

    Called by promptfoo before llm-rubric evaluation. Extracts Write/Edit
    tool calls from context.metadata.toolCalls via collect_written_files(),
    filters to .md files, and appends their contents so the rubric judge
    can score the actual analysis — not just the chat summary.
    """
    written = collect_written_files(context)
    md_files = {p: c for p, c in written.items() if p.endswith(".md")}
    if not md_files:
        return output

    sections = [output, "\n--- WRITTEN FILE CONTENTS ---"]
    for path, content in sorted(md_files.items()):
        sections.append(f"\n### {path}\n{content}")
    return "\n".join(sections)


def check_written_files(output, context, _options=None):
    """Assert that expected .md artifacts were written by the agent."""
    config = (context or {}).get("config") or {}
    expected = config.get("expected_files", [])
    if not expected:
        return {"pass_": True, "score": 1.0, "reason": "No expected files configured"}

    written = collect_written_files(context)
    filenames = {p.rsplit("/", 1)[-1] for p in written}

    missing = [f for f in expected if f not in filenames]
    if missing:
        return {
            "pass_": False,
            "score": 0.0,
            "reason": f"Missing files: {', '.join(missing)} | Written: {', '.join(sorted(filenames))}",
        }
    return {
        "pass_": True,
        "score": 1.0,
        "reason": f"All expected files written: {', '.join(expected)}",
    }
