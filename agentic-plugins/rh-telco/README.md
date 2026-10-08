# rh-telco

Agentic plugin for OpenShift telco reference configurations. Registered in
Compass through [`../catalog-info.yaml`](../catalog-info.yaml).

## Contents

| Path | Purpose |
|------|---------|
| `skills/rds-policy-update/` | Day 2 policy updates between OCP versions (RAN and Core) |
| `hooks/` | Optional PostToolUse hook that runs `kustomize build` on written PolicyGenerator files |
| `Containerfile`, `Makefile` | Content-only OCI image of the skill (`make build`) |
| `rh-telco-plugin.yaml`, `catalog-info.yaml`, `skills/*/catalog-info.yaml` | Compass manifests |

The hook needs `kustomize` and the PolicyGenerator plugin; without them it is
a no-op. Design docs and promptfoo evals for the skill stay in
[`../../rds-policy/`](../../rds-policy/).
