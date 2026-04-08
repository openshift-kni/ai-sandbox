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

## EXPLAIN Workflow

1. **Locate references** -- check for local `ref-{version}/` directories
   first. Fall back to ZTP container extraction if not available.
2. **Diff PolicyGenerator examples** (`acm-*-ranGen.yaml`) between versions.
   These are the high-level view of what changed.
3. **Diff source-crs content** -- for CRs that changed, compare the actual
   source CR files (not just paths).
4. **Detect structural changes** -- new/removed files, directory
   reorganization, new subdirectories, symlinks.
5. **Classify each change**: path-only, content change, GVK replacement,
   new CR, removed CR, deprecated CR.
6. Save results and build a merge checklist with the actual CRs found.

## After EXPLAIN

Save two files:

1. **EXPLAIN report** (`/tmp/rds-explain-{old}-to-{new}.md`) -- full
   analysis of what changed between versions.

2. **Merge checklist** (`/tmp/rds-merge-checklist-{old}-to-{new}.md`) --
   separate file, the **driver for MERGE**. Each item names the specific
   CR, what changed, and the action to take. For example:

   ```
   - [ ] TunedPerformancePatch — profile renamed X→Y, priority N→M. Update partner patches.
   - [ ] {old GVK} → {new GVK} — GVK replacement. Swap path + patch fields.
   - [ ] {CR name} — new required CR. Place in partner policy (wave N).
   - [ ] source-crs/ — replace with target version
   - [ ] Version references — bump metadata names, namespaces, placement labels
   ```

   Include a **version bumping** section at the end listing all
   version-bearing fields the merge must update:
   - PolicyGenerator `metadata.name`
   - `policyDefaults.namespace`
   - `placement.labelSelector` version labels
   - CatalogSource image tags
   - Namespace and ManagedClusterSetBinding resources

   For fields where the partner may have intentionally pinned a different
   version (e.g. a CatalogSource pinned to an older version), mark with
   `⚠ REVIEW` — do not auto-update, flag for user decision.

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

- Source CR paths may reorganize between versions. Check for backward-
  compatible symlinks at the root level -- if they exist, old manifest
  path references still resolve and do NOT need updating.

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

## MERGE Workflow

MERGE writes changes into a **clone of the partner's repo**, not to a
separate temp directory. This gives the user a proper git diff they can
review and push.

### Setup

1. **Load the merge checklist** from `/tmp/rds-merge-checklist-{old}-to-{new}.md`.
   This is the driver -- every change comes from this list.
2. **Clone** the partner's policy repo (URL or local path) into a temp
   working directory (e.g. `/tmp/rds-merge-{target}/`).
   - For internal GitLab with self-signed certs, use
     `GIT_SSL_NO_VERIFY=1` on the clone.
   - Ask the user for permission before cloning.
3. **Create** a new version directory alongside the existing one
   (e.g. `version_4.20/` next to `version_4.18.5/`).
   - Copy the partner's current version directory as the starting point.
4. **Replace source-crs/** for the target version. Either:
   - Extract from ZTP container:
     ```bash
     podman login registry.redhat.io
     podman pull registry.redhat.io/openshift4/ztp-site-generate-rhel8:{version}
     id=$(podman create registry.redhat.io/openshift4/ztp-site-generate-rhel8:{version})
     podman cp $id:/home/ztp/source-crs/ source-crs/
     podman rm $id
     ```
   - Or copy from local reference if available (e.g. `ref-{version}/source-crs/`).
5. **Verify symlinks** -- check that every `path:` the partner uses in
   their PolicyGenerator YAML still resolves in the new source-crs/.
   If a path is missing, the merge must update it.

### Processing (checklist-driven)

Walk the merge checklist item by item. For each item:

1. **Find affected partner CRs** -- scan partner PolicyGenerator YAML(s)
   for manifests that reference the same GVK. Use matching heuristics
   from `references/cr-matching-heuristics.md`.
2. **Apply the change** if it doesn't conflict with partner customizations.
3. **Flag for user review** if:
   - Partner has customized the same field the reference changed (true conflict)
   - Partner has pinned a value the checklist says to bump (e.g. older
     CatalogSource image tag)
   - The change is a GVK replacement and partner has non-trivial patches
   - You're not 100% sure the change is safe
4. **Check off the item** in the checklist.
5. If the partner doesn't use the CR at all, mark as N/A and move on.

**When uncertain: leave it alone and highlight it.** Never silently
apply a change you're not confident about. It's better to flag 5 things
that turn out to be fine than to silently break 1 thing.

### Version Bumping

After processing all checklist items, walk the version-bumping section:
- Update `metadata.name` version suffixes in PolicyGenerator YAML
- Update `policyDefaults.namespace`
- Update `placement.labelSelector` version labels
- Update Namespace and ManagedClusterSetBinding resources
- For CatalogSource image tags: update those that track the OCP version.
  If a tag doesn't match the current version (partner pinned it to
  something else), mark with `⚠ REVIEW` and ask the user.

### Parent Kustomization

After creating the new version directory, update the `kustomization.yaml`
in the parent directory to add the new version directory.

### Finish

1. **Show the diff** using `diff -u` between old and new version
   directories so the user can review all PolicyGenerator changes.
   Include the parent `kustomization.yaml` diff.
2. **Present the completed checklist** with status for each item:
   `[x]` applied, `[!]` flagged for review, `[-]` N/A.
3. The user pushes when ready -- never push on their behalf without
   explicit permission.

### Artifact Checklist

Always output a complete artifact set -- do not ask whether to include
parts of it:
- Updated PolicyGenerator YAML files
- The source-crs/ directory with base CRs for the target version
- Any additional source-crs the partner added
- Hub template ConfigMaps (as needed)

Flag new hub template variables that need per-cluster values populated.
