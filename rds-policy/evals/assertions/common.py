"""Shared utilities for eval assertions — file collection, PG parsing, manifest lookup."""

import json
import re
from pathlib import Path

import yaml

PG_REQUIRED_KEYS = {"metadata", "policyDefaults", "policies"}


def collect_written_files(context=None):
    """Read all files the agent wrote, extracted from toolCalls metadata.

    When context is provided, uses Write tool calls to find exact file paths
    the agent wrote in this session. Falls back to globbing /tmp/rds-merge-*/
    if context is unavailable or has no Write calls.
    """
    paths = _paths_from_context(context)
    if paths:
        written = {}
        for p in paths:
            f = Path(p)
            if f.exists() and f.suffix in (".yaml", ".yml", ".md"):
                written[str(f)] = f.read_text()
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
    """Extract file paths from Write tool calls in promptfoo providerResponse metadata."""
    if not context:
        return []
    provider_response = context.get("providerResponse") or {}
    metadata = provider_response.get("metadata") or context.get("metadata") or {}
    tool_calls = metadata.get("toolCalls") or []
    paths = []
    for call in tool_calls:
        if call.get("name") != "Write":
            continue
        raw = call.get("input", "")
        try:
            args = json.loads(raw) if isinstance(raw, str) else raw
            fp = args.get("file_path", "")
            if fp:
                paths.append(fp)
        except (json.JSONDecodeError, AttributeError):
            continue
    return paths


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
        (m for m in all_manifests if substring in m.get("path", "").lower()),
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
