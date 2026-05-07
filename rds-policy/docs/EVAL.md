# RDS Policy Agent — Evaluation Plan

## What We're Testing

Three capabilities, in order of risk:

1. **MERGE correctness** (highest risk) — wrong merges break deployments.
   Does the agent preserve partner customizations? Handle conflicts?
   Avoid adding optional CRs? Respect pinned versions?

2. **EXPLAIN accuracy** — does the agent correctly identify all reference
   changes? Miss anything? Misclassify path-only changes as content changes?

3. **Triggering & workflow** — does the skill activate on the right prompts?
   Does it ask for inputs instead of exploring? Does it run EXPLAIN before
   MERGE?

## How We're Testing

Using [promptfoo](https://promptfoo.dev) with the
`anthropic:claude-agent-sdk` provider. Following the
[agentskills.io eval framework](https://agentskills.io/skill-creation/evaluating-skills)
for test design principles.

Test config: `evals/promptfooconfig.yaml`. Run with `make eval` from `evals/`.

### Test Fixtures

Each test case is paired with specific "from" and "to" reference files
so results are reproducible and don't depend on live container extraction.

- **Synthetic reference CRs**: minimal reference sets for the source and
  target versions, covering the specific changes each test exercises.
  - `evals/files/ref-from/` — source version reference
  - `evals/files/ref-to/` — target version reference

- **Synthetic partner policies**: minimal PolicyGenerator YAML sets
  exercising specific merge behaviors. NOT real partner configs — all
  test content is entirely synthetic. Fixtures should look like realistic
  partner policies without labeling which behaviors are under test — the
  agent should discover the right behavior on its own.
  - `evals/files/partner-basic/` — few CRs, standard customizations
  - `evals/files/partner-pinned/` — intentionally pinned versions
  - `evals/files/partner-restructured/` — different policy organization

## Merge Behaviors Under Test

The key is testing **types of merge behaviors**, not specific CRs. Each
test fixture should exercise one or more of these scenarios:

### User content overwrites reference updates

The underlying rule: ensure the changes in the reference are implemented
in the new policy set, but if the user has explicit patches which overwrite
those changes, suggest the aligned result but ask for confirmation.

- **New field in reference, no user overlap** — trivial case. New content
  comes from base source-crs with nothing to reconcile.
- **New field in reference, overlaps user overlay (aligned)** — user patch
  matches the new reference value. Note as redundant, optionally suggest
  cleanup.
- **New field in reference, overlaps user overlay (different)** — propose
  aligned result but ask for confirmation.

Examples using channel fields (same pattern applies to any field):

- 4.18 and 4.20 reference both use "stable", PG has no patch to the
  channel → resulting policy simply uses value from reference (no
  confirmation needed)
- 4.18 and 4.20 reference both use "stable", PG has patch with "stable"
  → resulting policy keeps the user patch (no confirmation needed).
  Alternatively note the patch as "redundant" and ask if the user wants
  to clean it up (remove the patch)
- 4.18 is "stable" and 4.20 is "stable-v2", no user patch → result uses
  reference CR and gets "stable-v2"
- 4.18 is "stable" and 4.20 is "stable-v2", user patch with "stable" →
  agent proposes removing patch to align with reference but asks for
  confirmation of action to take

### Structural changes

- **User restructures policies** — same CRs but in different PolicyGenerator
  files, different number of policies per file. Result should follow the
  user's structure, but if reference moved a CR to a different wave/policy,
  that needs to be noted and confirmed.
- **User adds new CRs** — custom content carries through unchanged.
- **User replicates a reference CR** — same CR in PolicyGenerator multiple
  times. Should work unless there's a patch conflict.
- **PTP one-of selection** — user picks one PTP variant with changes in
  the reference. Should work so long as they pick up the new reference CR
  (assuming no renaming of source-cr/reference-cr filenames).

### Removal / optional content

- **User removes optional CRs** — carries through, but any changes in
  the reference to those CRs should be noted as "not included" in the
  final status.
- **User removes required CRs** — same but with stronger warning.
- **Reference adds mustnothave on a policy** — if user has overlays in
  that policy, warn the user.

### Policy metadata

- **Binding rule updates** — new PolicyGenerators must have updated
  placement bindings based on a version number or similar. The reference
  has this pattern so it must work even if the user renamed
  PolicyGenerators or added additional ones.

### Output validation

- Output must be well-formed PolicyGenerator YAML and valid base CRs —
  not just correct content but correct structure.

## Test Cases

### Test 1: EXPLAIN — basic reference diff

**What it tests**: Can the agent identify changes between reference
versions without asking for partner policies?

**Prompt**: `"what changed between RDS 4.18 and 4.20?"`

**Expected output**: Structured report covering added, removed, modified
CRs with per-CR detail. Should NOT ask for partner policies.

**Key things to check** (assertions added after first run):
- Identifies ICSP → IDMS GVK replacement
- Identifies TunedPerformancePatch rename + priority change
- Does NOT list path reorganization as content changes
- Does NOT ask for partner policy source

### Test 2: MERGE — basic partner policies

**What it tests**: Given partner policies with standard customizations,
does the agent produce correct, well-formed merged output?

**Prompt**: `"upgrade my policies from 4.18 to 4.20, policies are in
evals/files/partner-basic"`

**Input files**: `evals/files/partner-basic/` — two PolicyGenerator YAMLs:
- `my-common.yaml` — CatalogSource with v4.18 tag, DisconnectedICSP
  (needs GVK migration to IDMS), operator subscriptions
- `my-group-sno.yaml` — PTP with renamed CR (`acme-ptp-grandmaster`
  instead of reference `du-ptp-slave`), SRIOV with custom selector,
  PerformanceProfile with custom CPU pinning (`2-51,54-103`),
  TunedPerformancePatch with 4.18 profile name/priority

Partner uses `acme-*` naming throughout (not matching reference names).

**Key things to check**:
- Output is well-formed PolicyGenerator YAML
- Partner naming (`acme-*`) preserved throughout
- CatalogSource image tag bumped v4.18 → v4.20
- DisconnectedICSP → DisconnectedIDMS GVK migration handled
- PTP renamed CR (`acme-ptp-grandmaster`) matched via fuzzy matching
- PerformanceProfile custom CPU values preserved
- TunedPerformancePatch rename + priority change applied
- No optional/commented-out reference CRs added
- Binding rules updated for new version
- Output includes source-crs directory
- Merge checklist present and all items resolved

### Test 3: MERGE — pinned versions and channel handling

**What it tests**: Does the agent handle version-pinned values and
channel changes correctly per the channel handling rules?

**Prompt**: `"upgrade my policies from 4.18 to 4.20, policies are in
evals/files/partner-pinned"`

**Input files**: `evals/files/partner-pinned/my-common.yaml` — with:
- CatalogSource `redhat-operators` image tag pinned to v4.17 (not v4.18)
- Second CatalogSource `certified-operators` also pinned to v4.17
- SRIOV Subscription channel pinned to "stable" (not version-specific)
- DisconnectedICSP (same GVK migration scenario)

**Key things to check**:
- Both CatalogSources flagged for review (pinned to v4.17, not v4.18)
- SRIOV "stable" channel handled per channel rules (not blindly overwritten)
- Agent explains reasoning for flagged items
- DisconnectedICSP → IDMS migration still handled correctly
- Output is well-formed PolicyGenerator YAML

## Fixture → Assertion Mapping

Shows which assertions run against which test fixtures, and what merge
behaviors each assertion exercises. All CR-specific values are config-driven
in `promptfooconfig.yaml` — Python assertions are a generic engine.

| Test | Fixture | Deterministic | Semantic (llm-rubric) | Behaviors Tested |
|------|---------|--------------|----------------------|-----------------|
| EXPLAIN | ref only | `skill-used`, `llm-rubric` ×3 | explain-tuned, explain-gvk, workflow ordering | Reference diff accuracy, EXPLAIN-before-merge ordering |
| COMPREHENSIVE MERGE | `partner-comprehensive/` (2 PGs) | `check_file_content` (9 config-driven checks), `check_completeness`, `check_multi_pg_structure`, `check_cr_replication`, `check_parent_kustomization`, `no_unsafe_apply`, `log_user_questions` | merge-communication, conflict-flagging, overlay-lifecycle, wave-change, mustnothave-warning, list-merge-awareness, redundant-overlay, coverage-scan | GVK migration, patch preservation, version bumping, list restructure, partner-only CR, PTP scheduling, priority conflict, channel conflict, CR removal, wave change, mustnothave, redundant overlay, coverage scan, checklist, multi-PG, CR replication, kustomization, safety, AskUserQuestion log |
| REQUIRED-CR | `partner-required-cr/` (1 PG) | `skill-used` | required-cr-severity | Required vs optional missing CR severity |

## Coverage

### Triggering
- [ ] Triggers on upgrade request
- [ ] Triggers on diff/explain request
- [ ] Triggers on casual phrasing
- [ ] Does NOT trigger on unrelated prompts

### EXPLAIN
- [ ] Identifies key changes (GVK replacements, renames, new CRs)
- [ ] Does not ask for partner policies
- [ ] Handles path reorganization as non-breaking

### MERGE
- [ ] New field, no user overlap
- [ ] New field, overlaps user overlay (aligned)
- [ ] New field, overlaps user overlay (different)
- [ ] User restructures policies
- [ ] User adds new CRs
- [ ] User replicates a reference CR
- [ ] PTP one-of selection
- [ ] User removes optional CRs
- [ ] User removes required CRs
- [ ] Reference adds mustnothave + user has overlay
- [ ] Binding rule updates
- [ ] Output validation (well-formed PolicyGenerator YAML)

### Workflow
- [ ] EXPLAIN runs before asking for merge inputs

### Safety
- [ ] No kubectl apply without dry-run

### VALIDATE
- [ ] Dry-run against hub

### End-to-end
- [ ] Full flow: EXPLAIN → MERGE → VALIDATE

## Iteration Process

See [Evaluating skill output quality](https://agentskills.io/skill-creation/evaluating-skills)
for the full iteration loop (grading, assertions, benchmarking, human review).
