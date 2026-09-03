# RDS Policy Agent Skill Evals

3 tests covering EXPLAIN accuracy, end-to-end MERGE, and required CR severity.

## Test matrix

| ID | Name        | What it covers |
|----|-------------|----------------|
| T1 | EXPLAIN     | exhaustive ref diff coverage (all 9 differences), workflow ordering |
| T2 | MERGE       | full end-to-end: GVK migration, CR replication, conflict flagging, wave change, mustnothave, redundant overlay, coverage scan, checklist quality, multi-PG structure, version bumps, safety, AskUserQuestion logging |
| T3 | REQUIRED-CR | missing required vs optional CR severity |

Skill triggering is implicitly tested by all 3 (each checks `skill-used`).

## Assertion strategy

Two complementary assertion types run against the same agent session:

- **Deterministic (python)** — Check exact file contents, tool calls, and
  structure via `metadata.toolCalls`. Fast, precise, no LLM cost. Used for
  artifact correctness.

- **Semantic (llm-rubric)** — LLM judge scores the agent's communication
  quality against a rubric. Non-deterministic. Used for conflict flagging,
  coverage reporting, and checklist quality.

The agent writes analysis to files (`explain.md`, `checklist.md`) but its
chat response may be just a file listing. Rubric assertions that need
to see file contents use `transform: file://assertions/common.py:enrich_output`
which appends written `.md` files to the output before the judge scores it.

## Environment

All tests use a self-contained workdir (`fixtures/`) with synthetic refs
and partner fixtures. `hooks.js` copies the skill into `fixtures/.claude/`
before tests and cleans up after.

Results are stored in `~/.promptfoo/promptfoo.db` (not committed).
Run `make eval-view` to browse results in the browser.

To run the eval inside a confined OpenShell sandbox, see [OPENSHELL.md](OPENSHELL.md).
