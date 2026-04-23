"""Workflow ordering assertions.

Promptfoo Python assertion return format (GradingResult):
    {"pass_": bool, "score": float 0-1, "reason": str}
    Snake_case keys auto-convert to camelCase.
"""


def explain_before_merge(output, _context):
    """Agent must explain what changed before asking for the partner policy source.

    Checks that EXPLAIN terms (tuned, ptp, icsp, idms, etc.) appear in
    the output before any merge-input questions (provide your policy,
    policy source, git repo url, etc.). Fails if the agent asks for the
    policy location before explaining the reference changes.
    """
    text = (output or "").lower()

    explain_terms = [
        "tuned",
        "ptp",
        "icsp",
        "idms",
        "nmstate",
        "storagelv",
        "disconnected",
        "policygenerator",
    ]
    merge_input_terms = [
        "provide your polic",
        "provide the polic",
        "where are your polic",
        "policy source",
        "policy repo",
        "git repo url",
        "local directory path",
    ]

    first_explain_pos = _first_occurrence(text, explain_terms)
    first_merge_pos = _first_occurrence(text, merge_input_terms)

    if first_explain_pos is None:
        return {"pass_": False, "score": 0, "reason": "No EXPLAIN content found"}

    if first_merge_pos is None:
        return {
            "pass_": True,
            "score": 1,
            "reason": "EXPLAIN content found, no merge question (acceptable)",
        }

    if first_explain_pos >= first_merge_pos:
        return {
            "pass_": False,
            "score": 0,
            "reason": "Merge questions appeared before EXPLAIN",
        }

    return {
        "pass_": True,
        "score": 1,
        "reason": "EXPLAIN appears before merge questions",
    }


def _first_occurrence(text, terms):
    """Return the earliest character position where any term appears, or None."""
    positions = []
    for term in terms:
        pos = text.find(term)
        if pos != -1:
            positions.append(pos)
    return min(positions) if positions else None
