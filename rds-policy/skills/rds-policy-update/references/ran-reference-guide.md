# RAN Reference Guide

## Container Image

```
registry.redhat.io/openshift4/ztp-site-generate-rhel8:{version}
```

Extract `/home/ztp/` from the container. Auto-discover which container
tool is available (`oc`, `podman`, `docker`, `skopeo`).

## Directory Layout

```
/home/ztp/
├── source-crs/                           # Individual CR YAMLs (flat)
├── argocd/example/acmpolicygenerator/    # PolicyGenerator examples
│   ├── acm-common-ranGen.yaml
│   ├── acm-group-du-sno-ranGen.yaml
│   ├── acm-group-du-standard-ranGen.yaml
│   └── acm-example-sno-site.yaml
└── reference/                            # Telco-reference by operator
```

`source-crs/` structure may change between versions (flat vs operator
subdirectories). Check for backward-compatible symlinks.

## PolicyGenerator Naming

RAN uses `acm-*-ranGen.yaml` organized by scope:
- `acm-common-ranGen.yaml` -- shared (subscriptions, operators)
- `acm-group-du-sno-ranGen.yaml` -- single-node DU profile
- `acm-group-du-standard-ranGen.yaml` -- multi-node standard DU
- `acm-example-sno-site.yaml` -- site-specific per-cluster

Hierarchy: common → group (by topology) → site.

## RAN-Specific Operators

Present in RAN, absent from Core:
- PTP (20+ config variants)
- SRIOV-FEC (hardware baseband accelerators)
- IBU / Lifecycle Agent (image-based upgrade for SNO)
- OADP (backup/restore for IBU)
- LSO / LVM (local storage)
- Real-time kernel, workload partitioning, aggressive cluster tuning

## CR Matching Notes

See `cr-matching-heuristics.md` and `ran-cr-guidance/` for RAN-specific
matching rules (SRIOV, PTP, Tuned restructure, IBU lifecycle).
