# RDS Policy Agent — Eval Guide

## What this is

The RDS (Reference Design Specification) policy update skill helps partners upgrade their OpenShift Day 2 configuration policies between OCP versions. It reads reference CRs for both versions, explains what changed, and merges those changes into the partner's existing PolicyGenerator files — preserving customizations, flagging conflicts, and warning about removed or required CRs.

These are promptfoo evals that test whether the skill produces correct merge artifacts, flags conflicts, and communicates changes. 7 tests, ~8 min, ~$1.50 per run.

## Quick start

```bash
cd rds-policy/evals
make setup          # Install promptfoo + agent SDK
make eval           # Run all tests
make eval-view      # Browser UI with detailed results
make lint           # Lint Python assertion files
```

## Test inventory

| # | Test | What it checks |
|---|------|----------------|
| 1 | Triggers on upgrade request | Skill activates on "upgrade 4.18 to 4.20" |
| 2 | Triggers on casual phrasing | Skill activates on "diff the refs for me" |
| 3 | Does NOT trigger on unrelated prompt | Skill stays silent for "deploy a new cluster" |
| 4 | EXPLAIN accuracy and ordering | Mentions key changes (Tuned, ICSP/IDMS), explains before asking for partner source |
| 5 | No kubectl apply without dry-run | Safety — agent must never run live apply |
| 6 | Comprehensive merge | All merge behaviors in one session — GVK migration, conflict flagging, overlay lifecycle, checklist, multi-PG structure, wave changes, CR replication, mustnothave |
| 7 | Required CR severity | Distinguishes required vs optional missing CRs with appropriate warning language |

Tests 1-5 are lightweight (~30s each). Tests 6-7 run full merge sessions (~3 min each).

## Provider: `anthropic:claude-agent-sdk`

Each test runs a full Claude Code session with skill loading, tool access, and file I/O.

- `working_dir` — agent's working directory (where fixtures live)
- `permission_mode: acceptEdits` — agent writes files without prompts
- `ask_user_question.behavior: first_option` — auto-resolves HITL questions
- `max_budget_usd` — caps per-test spend
- `persist_session: false` — ensures test isolation

## Assertions: built-in vs Python

We started with promptfoo's built-in assertions and moved to Python for anything structural.

**Built-in (fast, free, good for text checks):**
- `icontains` / `icontains-all` / `icontains-any` — does the output mention key terms?
- `skill-used` / `not-skill-used` — did the right skill activate?
- `cost` / `latency` — budget and time guards
- Good for fast-fail checks before expensive Python assertions run

**Python file assertions (for anything that needs toolCalls):**
- Declared as `type: python`, `value: file://assertions/merge.py:function_name`
- Receive `(output, context)` — output is agent text, context has `providerResponse.metadata.toolCalls`
- Return `{pass_: bool, score: float, reason: str, component_results: [...]}`
- `component_results` give per-check breakdowns in the promptfoo UI
- `pass_` (with underscore) auto-converts to `pass` in JSON

**Why Python over built-in:**
- Built-in assertions only see output text — they can't inspect what the agent wrote to files
- `toolCalls` metadata has every Write/Edit/Bash call with full input — you can parse the YAML the agent produced
- Scored assertions (0.0-1.0) give signal even when they don't fully pass
- Component results let you see exactly which sub-check failed

## Assertion files

| File | Purpose |
|------|---------|
| `merge.py` | Artifact correctness — parses PolicyGenerator YAML from tool calls, checks GVK migration, partner customization preservation, version bumps, conflict flagging, checklist completeness |
| `structural.py` | Multi-PG structure — verifies 2+ PG files preserved, CR replication across instances, wave change flagging, mustnothave warnings, required CR severity |
| `workflow.py` | Ordering — EXPLAIN content appears before merge-input questions |
| `safety.py` | Safety — no `kubectl apply` or `oc apply` without `--dry-run` |

All assertion files inspect `toolCalls` metadata, not disk. The agent writes to timestamped paths that vary between runs, but tool call payloads always contain the content.

### Reconstructing files from tool calls

The agent may produce output files via `Write` (full content) or `cp` + `Edit` (copy then patch). The `_collect_written_files()` helper in `merge.py` and `structural.py` handles both:

1. Builds a cache of `Read` call outputs (potential copy sources)
2. Tracks `Write` calls as complete file contents
3. For `Edit` calls, finds the source content by matching paths (including version-renamed files like `acme-v4-18.yaml` → `acme-v4-20.yaml`) and applies the `old_string` → `new_string` replacement

This is necessary because asserting only on `Write` calls would miss files the agent creates via copy-and-edit.

## Scoring: required vs optional

- Required assertions fail the test when they fail
- Optional assertions always return `pass_: True` with a 0-1 score — they contribute to the overall score without blocking
- This matches "optionally suggest" behaviors from the skill spec
- Example: redundant overlay detection is nice-to-have, not required
- `weight` multiplies an assertion's importance (safety checks use `weight: 5`)

## Fixtures

- Synthetic reference CRs in `ref-4.18/` and `ref-4.20/` — small, focused, only what's needed
- Partner PolicyGenerator fixtures in `partner-*/` directories
- Reference PG examples (`acmpolicygenerator/`) distinguish required vs optional CRs (uncommented vs commented out)
- `hooks.js` git-inits partner dirs in `beforeAll` and resets them in `afterEach` so agent writes don't leak between tests
- One comprehensive fixture can test many scenarios — stack assertions instead of duplicating fixtures

## Adding a new test

1. **Decide if you need a new fixture.** Most merge scenarios can be tested by adding assertions to the existing comprehensive test (test 6). Only create a new `partner-*` fixture if you need a fundamentally different PolicyGenerator structure.

2. **Write the assertion function** in the appropriate file (`merge.py` for artifact checks, `structural.py` for structure, etc.). Follow the existing pattern:
   ```python
   def check_something(_output, context):
       tool_calls = _tool_calls(context)
       written = _collect_written_files(tool_calls)
       # ... check written files or output text ...
       return {"pass_": bool, "score": float, "reason": str}
   ```

3. **Add it to `promptfooconfig.yaml`** under the relevant test's `assert` list:
   ```yaml
   - type: python
     value: file://assertions/structural.py:check_something
     metric: something-metric
   ```

4. **Run `make lint`** to check syntax, then `make eval` to verify.

## What worked

- **Parse YAML, don't regex raw text.** The single biggest reliability improvement. Parse the PolicyGenerator YAML from toolCalls and check structural properties.
- **Check toolCalls, not disk.** The agent writes to timestamped paths. Assertions read from `metadata.toolCalls` which has content regardless of path.
- **Combine scenarios into one test.** Multiple Python assertions on one test cost nothing extra. Each reports its own metric, so failures stay precise.
- **Directive prompts.** "go ahead with the full upgrade" isn't enough for automated evals. Be explicit: "do the full EXPLAIN and MERGE end-to-end, use recommended defaults for any conflicts."
- **Split assertions into independent files.** `merge.py`, `structural.py`, `workflow.py`, `safety.py` — each focused, each testable.

## What didn't work

- **YAML comments in fixtures.** The agent reads partner PG files. Comments like `# Tests: MUSTNOTHAVE` prime the agent to look for things it should discover on its own. Strip all test-hint comments.
- **Regex on raw output for structural checks.** Too brittle — the agent says "IDMS" in one run, "ImageDigestMirrorSet" in another. Use `icontains-any` for text checks, YAML parsing for structural checks.
- **Single-PG assertion for multi-PG output.** Early `check_file_content` only parsed the first PolicyGenerator found. With multi-PG output, it missed manifests in the second file.
- **Separate tests per scenario.** 4 merge tests = 4 agent sessions = ~$12 and ~40 min. Consolidating to 1 test with all assertions = ~$3 and ~10 min, same coverage.
- **Inline JS assertions.** Started with JavaScript in the promptfoo config. Moved to Python files — easier to debug, lint, and test independently.
- **Expecting the agent to use `AskUserQuestion` tool.** The agent sometimes asks questions as plain text instead of calling the tool. The `ask_user_question` auto-resolver only works with the tool call. Directive prompts work around this.

## Non-determinism

- The same test passes/fails across runs — this is expected with LLM evals
- Run 3-5 times and look at pass rates per assertion
- A consistent 5/9 becoming 9/9 after a fix is a real improvement, not noise
- Optional assertions help: they score 0-1 without failing the test, so you see trends

## The iteration loop

1. Run eval — identify which assertions fail
2. Diagnose — is it a skill gap, assertion bug, or fixture problem?
3. Fix the right layer:
   - **Skill:** agent doesn't do X → add instruction
   - **Assertion:** agent does X but assertion can't detect it → fix the check
   - **Fixture:** test scenario isn't exercised → add/modify fixtures
   - **Prompt:** agent doesn't proceed to merge → make prompt more directive
4. Re-run — verify the fix, check for regressions

## Key promptfoo features we use

- `extensions: file://hooks.js` — lifecycle hooks for setup/teardown
- `defaultTest.assert` — cost/latency guards on every test
- `config` on assertions — pass version numbers to Python functions so they're not hardcoded
- `--no-cache` — always during development
- `-o output.json` — for programmatic analysis of results
- `promptfoo view` — browser UI for comparing runs side by side
