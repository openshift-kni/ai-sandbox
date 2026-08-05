# Core Reference Guide

This file provides additional content for the Core use case: container
image, directory layout, PG naming, and CR catalog discovery. The
EXPLAIN → MERGE → VALIDATE workflow and PolicyGenerator format are
common to all use cases.

## Container Image

```
registry.redhat.io/openshift4/openshift-telco-core-rds-rhel9:{version}
```

Extract `/home/telco-core/` from the image with whichever container
tool is available (`oc`, `podman`, `docker`, `skopeo`). With podman:
```bash
podman pull registry.redhat.io/openshift4/openshift-telco-core-rds-rhel9:{version}
id=$(podman create registry.redhat.io/openshift4/openshift-telco-core-rds-rhel9:{version})
podman cp $id:/home/telco-core/ {output_dir}
podman rm $id
```
With oc: `oc image extract <image> --path /home/telco-core/:{output_dir}`.
Docker mirrors the podman commands; skopeo requires unpacking the
image layers after `skopeo copy`.

## Directory Layout

```
telco-core/configuration/
├── core-baseline.yaml          # PG: required content (fixed)
├── core-overlay.yaml           # PG: customizable + optional
├── core-upgrade.yaml           # PG: upgrade orchestration
├── core-upgrade-finish.yaml    # PG: release workers post-upgrade
├── core-upgrade-precache.yaml  # PG: pre-cache images
├── kustomization.yaml
├── template-values/            # ConfigMaps for hub-side templating
└── reference-crs/              # Deployable CRs
    ├── required/               # Must be present for conformant cluster
    └── optional/               # Partner chooses which to include
```

Notes:
- Source CRs are found in the `reference-crs/` directory, split into
  `required/` and `optional/` subdirectories
- PG files follow the baseline/overlay pattern shown above

## Discovering the CR Catalog

Do not rely on a hardcoded operator or CR list — it changes between
versions. Derive the catalog from the extracted reference for each
version being compared:

- Enumerate `reference-crs/required/` and `reference-crs/optional/`
  for the shipped CRs and their required/optional status.
- Derive the operator set from the Subscription CRs (`spec.name`
  gives the operator).

CR matching rules are common across use cases — see
`cr-matching-heuristics.md`.
