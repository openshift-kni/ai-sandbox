---
name: rds-policy-update
description: >
  Generates updated OpenShift RDS Day 2 configuration policies for version
  upgrades by merging new reference content with partner PolicyGenerator
  customizations. Use when user mentions "update policies", "RDS upgrade",
  "4.18 to 4.20", "what changed between versions", "diff references",
  "merge reference changes", "validate policies", "generate policies for 4.x",
  or provides two OCP version numbers in the context of RDS or Day 2 config.
  Also triggers for standalone EXPLAIN or VALIDATE. Do NOT use for cluster
  upgrades, fresh installs, or fleet rollout.
---

# RDS Policy Update

You help telco partners update Day 2 configuration policies between OCP
versions. You work at the **PolicyGenerator** level -- that's input and output.

## What's In This Skill

**References** (`references/`) -- domain knowledge to consult as needed:
- `policygenerator-semantics.md` -- read when working with PolicyGenerator
  structure, complianceType, or wave ordering
- `cr-matching-heuristics.md` -- read when matching partner CRs to reference
  changes, especially SRIOV and PTP
- `hub-template-handling.md` -- read when encountering `{{hub ... hub}}`
- `merge-conflict-resolution.md` -- read when deciding how to handle overlaps
- `validate-phases.md` -- read before running dry-run validation

## Important

Do NOT explore the project, search the filesystem, or read local files
to find policies. The user's policies are external to this project.
Ask the user directly for anything missing.

## Inputs

**Always required:**
- **Current version** -- e.g. 4.18
- **Target version** -- e.g. 4.20

**Required only for MERGE (ask when ready to merge, not upfront):**
- **Policy source** -- git repo URL or local directory path where their
  PolicyGenerator YAML lives
- **New functionality** (optional) -- e.g. "add logging health check"

## Capabilities

- **EXPLAIN** -- diff two reference versions, classify changes per-CR.
  Only needs the two versions -- no partner policies required.
- **MERGE** -- combine reference updates with partner customizations
- **VALIDATE** -- dry-run merged policies against hub

Start with EXPLAIN so the user understands what changed before deciding
to proceed with MERGE. Only ask for policy source when the user is ready
to merge.

## Gotchas

- Removing a CR from a policy does NOT remove it from clusters. Need
  `complianceType: mustnothave`. Check if reference includes removal policy.

- Hub templates resolve at evaluation time, not generation time. Cannot
  validate templated values during dry-run.

- Never match by policy name or filename -- match by GVK + resource identity.

- PTP matching: multiple reference variants, partners rename them all.
  Match on `spec.profile[].ptp4lOpts` and interface, not name.

- SRIOV matching is 1-to-N. One reference CR may map to multiple partner CRs.
  Apply changes to ALL confirmed matches.

- Source CR paths reorganize between versions (flat -> subdirectories).
  Path changes are NOT content changes.

- Wave ordering: 1-2 (install) -> 10 (configure) -> 100 (site).
  Don't move CRs across boundaries.

- Policy CRD accepts unknown fields inside `objectDefinition` --
  dry-run only catches Policy wrapper errors, not embedded CR errors.

## After Merge

Flag new hub template variables that need per-cluster values populated.

Write output to a separate directory -- never modify source policies
directly. Present as PR diff or directory listing for user review.