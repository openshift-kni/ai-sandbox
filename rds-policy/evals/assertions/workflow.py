"""Workflow assertions — AskUserQuestion extraction and logging.

Promptfoo Python assertion return format (GradingResult):
    {"pass_": bool, "score": float 0-1, "reason": str}
    Snake_case keys auto-convert to camelCase.

This assertion extracts and logs — always passes. Review the
component_results in the promptfoo UI to see what was asked.
"""

import json


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


def no_topology_question(_output, context):
    """Fail if the agent asked the user to choose a cluster topology.

    Preserving the partner's topology is deterministic (CNF-23930), so the
    agent must NOT ask which topology to use. This is a hard pass/fail gate.
    """
    keywords = (
        "topology",
        "machineconfigpool",
        "worker-1",
        "worker-2",
        "worker-3",
        "pool",
    )
    questions = _extract_questions(context)
    asked = [
        q for q in questions if any(k in (q["text"] or "").lower() for k in keywords)
    ]
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
