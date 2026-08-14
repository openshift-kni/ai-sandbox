# Core Reference Guide

This file provides additional content for the Core use case: container
image, directory layout, PG naming, and CR catalog discovery. The
EXPLAIN → MERGE → VALIDATE workflow and PolicyGenerator format are
common to all use cases.

## Container Image

```
registry.redhat.io/openshift4/openshift-telco-core-rds-rhel9:v{version}
```

The image emits its contents as a base64-encoded tar on stdout. Log in
to the registry first, then run the image and unpack the stream:
```bash
podman login registry.redhat.io
podman run --rm registry.redhat.io/openshift4/openshift-telco-core-rds-rhel9:v{version} | base64 -d | tar xv -C {output_dir}
```
This unpacks a `telco-core-rds/` tree into `{output_dir}` (see Directory
Layout below). Do NOT use `podman cp` or `oc image extract` -- this
image streams its content rather than laying it out on the image
filesystem.

## Directory Layout

```
telco-core-rds/configuration/
├── <PG example files>          # e.g. core-baseline.yaml, core-overlay.yaml,
│                               #   core-upgrade.yaml (names vary by version)
├── kustomization.yaml
├── template-values/            # ConfigMaps for hub-side templating
└── reference-crs/              # Deployable CRs
    ├── required/               # Must be present for conformant cluster
    └── optional/               # Partner chooses which to include
```

Notes:
- Source CRs are found in the `reference-crs/` directory, split into
  `required/` and `optional/` subdirectories
- The exact PolicyGenerator example filenames change between versions --
  do not hardcode them. Enumerate the `*.yaml` PG files present in
  `configuration/` for the version you extracted

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
