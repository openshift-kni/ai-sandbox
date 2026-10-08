# PolicyGenerator Validation Hook

A Claude Code PostToolUse hook that validates PolicyGenerator YAML after every
Write/Edit. Runs `kustomize build --enable-alpha-plugins` to catch structural
errors before the user reviews the output.

## Why

The skill generates PolicyGenerator YAML during MERGE. Without validation, the
LLM can produce output with missing source-cr paths, stale references, or
invalid field combinations — errors that only surface when someone runs
`kustomize build` manually. The hook makes this automatic: errors feed back to
the LLM via exit code 2, and it self-corrects in the same turn.

## How it works

```
Skill writes PolicyGenerator YAML
  → hook fires (PostToolUse on Write/Edit of *.yaml)
  → checks for `kind: PolicyGenerator` in the file
  → runs `kustomize build --enable-alpha-plugins` on the directory
  → exit 0  (silent — success produces no output)
  → exit 2 + error on stderr (fed back to LLM for self-correction)
```

The hook only fires on `.yaml` files containing `kind: PolicyGenerator`. All
other files are a silent no-op. Early-exit guards (missing tools, non-PG files)
are also silent.

## Example: feedback loop in action

During a MERGE run, the skill edits a PolicyGenerator file incrementally.
The hook catches that `ClusterMonitoringConfig.yaml` no longer exists in the
4.20 source-crs:

```
⏺ Edit(acme-sno-4.20.yaml)                    # skill swaps ICSP → IDMS path
  ⎿  PostToolUse:Edit hook returned blocking error
     VALIDATE FAILED — kustomize build errors:
     could not read the manifest path source-crs/ClusterMonitoringConfig.yaml
     in policy acme-sno-config-policy
```

The LLM reads the error and adapts — instead of continuing with incremental
edits (each of which would fail), it writes the complete merged file in one
pass with all path changes applied. The successful write is silent (no hook
output), and the LLM continues with the next step.

## What the validation catches (and doesn't)

`kustomize build` + the PolicyGenerator plugin binary perform these checks
implicitly:

**kustomize** catches:

| Check | Example error |
|-------|---------------|
| Malformed YAML syntax | `MalformedYAMLError: yaml: line 21: did not find expected '-' indicator` |
| Stale kustomization.yaml refs | `could not read the manifest path` (old filename) |

**PolicyGenerator plugin** catches:

| Check | Example error |
|-------|---------------|
| Missing source-cr path | `could not read the manifest path source-crs/DoesNotExist.yaml` |
| Unknown PG fields | `field bogusField found but not defined in type PolicyGenerator` |
| Invalid field combos | `field consolidateManifests found but not defined` (wrong level) |

**Neither catches:**

| Check | What happens |
|-------|--------------|
| Duplicate YAML keys | Silently takes last value |
| Invalid complianceType value | Passes silently |
| Invalid remediationAction | Passes silently |
| Bad fields inside source-cr patches | PG passes through any content |
| Wrong apiVersion in source-crs | PG passes through any content |

**Bottom line:** the hook catches YAML syntax errors (kustomize) and
PolicyGenerator structural errors (plugin). It does not validate
embedded CR content or enum field values — those require
`oc apply --dry-run=server` against a real cluster.

## Prerequisites

- `kustomize` (v4.5+)
- PolicyGenerator plugin binary at:
  `~/.config/kustomize/plugin/policy.open-cluster-management.io/v1/policygenerator/PolicyGenerator`

The hook silently degrades to a no-op if either tool is missing.

## Files

| File | Purpose |
|------|---------|
| `agentic-plugins/rh-telco/hooks/validate-policygen.sh` | The hook script |
| `agentic-plugins/rh-telco/hooks/hooks.json` | Wires up the PostToolUse hook |

## Linting

The hook script is checked by `shellcheck` as part of `make lint` from the
repo root.
