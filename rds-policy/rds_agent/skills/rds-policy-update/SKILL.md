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
  Read `references/policygenerator-semantics.md` first -- it has the
  extraction command for fetching reference CRs from the ZTP container.
- **MERGE** -- combine reference updates with partner customizations.
  Read `references/cr-matching-heuristics.md`,
  `references/merge-conflict-resolution.md`, and
  `references/hub-template-handling.md` before starting.
- **VALIDATE** -- dry-run merged policies against hub.
  Read `references/validate-phases.md` before starting.

Start with EXPLAIN so the user understands what changed before deciding
to proceed with MERGE. Only ask for policy source when the user is ready
to merge.

## After EXPLAIN

Save the EXPLAIN output to a file (e.g. `/tmp/rds-explain-{old}-to-{new}.md`)
so MERGE can reference it without relying on conversation context.

Build a merge checklist from the EXPLAIN results with the **actual CRs
and changes** — not generic categories. For example:

- [ ] Subscription/sriov-network-operator — channel 4.18 → 4.20
- [ ] TunedPerformancePatch — renamed, priority changed
- [ ] ImageContentSourcePolicy → ImageDigestMirrorSet — GVK replacement
- [ ] ClusterLogForwarder/instance — new required CR, place in policy
- [ ] ReduceMonitoringFootprint — new fields added, check for conflicts

Save this checklist to the EXPLAIN output file. During MERGE, work
through it one by one, checking off each item as it's resolved. Present
the updated checklist to the user after MERGE completes.

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

- Source CR paths reorganize between versions (flat -> subdirectories),
  but symlinks at the root level preserve backward compatibility. Old
  flat paths (e.g. `source-crs/SriovNetwork.yaml`) still resolve. Do
  NOT update manifest path references -- they work as-is.

- Wave ordering: 1-2 (install) -> 10 (configure) -> 100 (site).
  Don't move CRs across boundaries.

- Policy CRD accepts unknown fields inside `objectDefinition` --
  dry-run only catches Policy wrapper errors, not embedded CR errors.

- MERGE only touches what the partner already has. Do NOT add optional
  or commented-out reference CRs into the partner's policies. Only add
  CRs that are new and required in the target version. Optional CRs
  are only added if the user explicitly requests them (via the "new
  functionality" input). Process the partner's CRs one by one against
  the reference changes -- not the other way around.

## Output Workflow

MERGE writes changes into a **clone of the partner's repo**, not to a
separate temp directory. This gives the user a proper git diff they can
review and push.

### Steps

1. **Clone** the partner's policy repo (URL or local path) into a temp
   working directory (e.g. `/tmp/rds-merge-{target}/`).
   - For internal GitLab with self-signed certs, use
     `GIT_SSL_NO_VERIFY=1` on the clone.
   - Ask the user for permission before cloning.
2. **Create** a new version directory alongside the existing one
   (e.g. `version_4.20/` next to `version_4.18.5/`).
   - Copy the partner's current version directory as the starting point.
   - Apply all merge changes to the new directory.
3. **Update source-crs/** for the target version. Either:
   - Extract from ZTP container: `oc image extract
     quay.io/openshift-kni/ztp-site-generator:{version}
     --path /home/ztp/source-crs/:source-crs/ --confirm`
   - Or copy from local reference if available (e.g. `ref-4.20/source-crs/`).
4. **Show the diff** using `git diff` (or `git diff --stat` for summary)
   so the user can review all changes in context.
5. The user pushes when ready -- never push on their behalf without
   explicit permission.

### Artifact Checklist

Always output a complete artifact set -- do not ask whether to include
parts of it:
- Updated PolicyGenerator YAML files
- The source-crs/ directory with base CRs for the target version
- Any additional source-crs the partner added
- Hub template ConfigMaps (as needed)

Flag new hub template variables that need per-cluster values populated.