"""Workflow assertions — AskUserQuestion extraction and logging.

Promptfoo Python assertion return format (GradingResult):
    {"pass_": bool, "score": float 0-1, "reason": str}
    Snake_case keys auto-convert to camelCase.

log_user_questions extracts and logs — always passes. Review the
component_results in the promptfoo UI to see what was asked.
no_topology_question is a hard gate (CNF-23930).
"""

import json
import re


def _extract_questions(context):
    provider_response = context.get("providerResponse") or {}
    metadata = provider_response.get("metadata") or context.get("metadata") or {}
    tool_calls = metadata.get("toolCalls") or []

    questions = []
    for call in tool_calls:
        if call.get("name") != "AskUserQuestion":
            continue
        raw = call.get("input", "")
        try:
            args = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, AttributeError):
            continue
        for q in args.get("questions", []):
            text = q.get("question", "")
            options = [o.get("label", "") for o in q.get("options", [])]
            questions.append(
                {
                    "text": text,
                    "options": options,
                    "answer": options[0] if options else "(no options)",
                }
            )
    return questions


# Pool-layout wording: "topology", "pool structure", "three pools",
# "reference pools". Bare "pool" is too broad (e.g. "connection pool").
_LAYOUT_TERMS = re.compile(
    r"\btopolog(?:y|ies)\b"
    r"|\b(?:pool|mcp|machineconfigpool) (?:structure|layout|count|names?|naming)\b"
    r"|\b(?:\d+|two|three|four)[- ](?:worker[- ])?(?:pools?|mcps?|machineconfigpools?)\b"
    r"|\breference(?:'s)? (?:example )?(?:pools|mcps|machineconfigpools)\b"
)
# Mapping a partner pool onto a reference pool *configuration* is expected
# (per-pool CR matching), so naming a reference pool there is not a layout
# choice.
_POOL_MAPPING = re.compile(r"\b(?:map\w*|match\w*|correspond\w*|align\w*|equivalent)\b")


def _is_topology_question(q, reference_pools):
    text = " ".join([q["text"] or "", *q["options"]]).lower()
    if _LAYOUT_TERMS.search(text):
        return True
    names_reference_pool = any(
        re.search(rf"\b{re.escape(p.lower())}\b", text) for p in reference_pools
    )
    return names_reference_pool and not _POOL_MAPPING.search((q["text"] or "").lower())


def no_topology_question(_output, context):
    """Fail if the agent asked the user to choose a MachineConfigPool layout.

    Preserving the partner's pool layout is deterministic (CNF-23930), so the
    agent must NOT ask which layout to use. This is a hard pass/fail gate.
    Question text and option labels are both scanned. Mentioning only the
    partner's own pool is not flagged: per-pool config conflicts (e.g. a
    PerformanceProfile patch on that pool) legitimately name it.
    """
    config = context.get("config") or {}
    reference_pools = config.get("reference_pools", [])
    questions = _extract_questions(context)
    asked = [q for q in questions if _is_topology_question(q, reference_pools)]
    if asked:
        return {
            "pass_": False,
            "score": 0,
            "reason": f"Agent asked a topology-selection question: {asked[0]['text'][:160]}",
        }
    return {
        "pass_": True,
        "score": 1.0,
        "reason": f"No topology-selection question ({len(questions)} AskUserQuestion calls total)",
    }


def log_user_questions(_output, context):
    """Extract and log all AskUserQuestion calls with questions and answers."""
    questions = _extract_questions(context)

    if not questions:
        return {
            "pass_": True,
            "score": 1.0,
            "reason": "0 AskUserQuestion calls — agent did not ask the user anything",
        }

    return {
        "pass_": True,
        "score": 1.0,
        "reason": f"{len(questions)} AskUserQuestion calls",
        "component_results": [
            {
                "pass_": True,
                "score": 1.0,
                "reason": (
                    f"Q: {q['text'][:150]} | "
                    f"OPTIONS: {q['options'][:4]} | "
                    f"ANSWERED: {q['answer']}"
                ),
            }
            for q in questions
        ],
    }
