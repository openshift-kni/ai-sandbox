# PolicyGenerator Semantics

Common PolicyGenerator concepts shared across RAN and Core NF types.
For NF-specific details (container image, directory layout, PG naming,
partner versioning), see `ran-reference-guide.md` or
`core-reference-guide.md`.

## PolicyGenerator vs Policy CR

- **PolicyGenerator YAML** is the user-maintained source format. Defines
  policies declaratively: manifest references, patches, placement, remediation.
  This is the input/output format from disk or git.
- **Policy CR** is the runtime representation on the ACM hub. PolicyGenerator
  does not appear on the hub -- only generated Policy CRs exist there.

## PolicyGenerator YAML Structure

```yaml
apiVersion: policy.open-cluster-management.io/v1
kind: PolicyGenerator
metadata:
  name: acm-common-ranGen
policyDefaults:
  namespace: ztp-common
  placement:
    labelSelector:
      matchExpressions:
        - key: common
          operator: In
          values: ["true"]
  remediationAction: inform
policies:
  - name: common-config-policy
    manifests:
      - path: source-crs/SriovSubscription.yaml
        patches:
          - metadata:
              name: sriov-network-operator-subscription
            spec:
              channel: "4.18"
      - path: source-crs/PtpSubscription.yaml
```

Key elements:
- `policyDefaults` -- shared defaults (namespace, placement, remediation)
- `policies[]` -- list of policies, each with name and manifests
- `manifests[]` -- references to source CR files with optional patches
- `patches[]` -- kustomize-like overlays. This is where user customizations live.

## complianceType Semantics

Each manifest or patch can specify a `complianceType`:

- **`musthave`** (default) -- specified fields must exist with given values.
  Other fields on the cluster resource are ignored.
- **`mustonlyhave`** -- resource must match exactly. Extra fields cause
  NonCompliant.
- **`mustnothave`** -- resource must NOT exist on cluster. Used for
  cleanup/removal.

When reference removes a CR from a policy, it does NOT remove it from
clusters. A separate policy with `complianceType: mustnothave` is needed.

## Wave Ordering

Policies apply in wave order via the
`policy.open-cluster-management.io/triggerBinding` annotation:

- **Wave 1** -- subscriptions and operator installs
- **Wave 2** -- operator configs depending on wave 1
- **Wave 10** -- group-level configs (profile-specific)
- **Wave 100** -- site-specific configs

Preserve wave assignments from the reference unless user explicitly changes them.

## Patches as Kustomize-like Overlays

- Merge into the base CR from `path:`
- Fields in the patch override the base
- Fields not in the patch are kept from the base
- Array merge depends on merge key (usually `name` for named items)

A patch field represents an intentional override of the base CR value.

## Architecture-Specific CRs

Some source CRs may have architecture-specific variants (e.g. under
`x86_64/` and `aarch64/` subdirectories). When diffing or merging,
check whether CRs that previously had a single file now have per-arch
variants. If so, ask the partner which architecture they target to
select the correct path.
