# Core Reference Guide

This file covers how Core differs from RAN. The workflow (EXPLAIN →
MERGE → VALIDATE), PolicyGenerator format, matching heuristics, and
merge rules are the same — only the container image, directory layout,
PG naming, and CR catalog differ.

## Container Image

```
registry.redhat.io/openshift4/openshift-telco-core-rds-rhel9:{version}
```

Extract with:
```bash
podman pull registry.redhat.io/openshift4/openshift-telco-core-rds-rhel9:{version}
id=$(podman create registry.redhat.io/openshift4/openshift-telco-core-rds-rhel9:{version})
podman cp $id:/home/telco-core/ {output_dir}
podman rm $id
```

Compare with RAN which uses `ztp-site-generate-rhel8` and extracts
from `/home/ztp/`.

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

Key differences from RAN:
- CRs live in `reference-crs/` (not `source-crs/`)
- Split into `required/` and `optional/` subdirectories (not flat)
- PG files use baseline/overlay pattern (not `acm-*-ranGen.yaml`)

## Core-Specific Operators

Present in Core, absent from RAN:
- MetalLB (BGP, BFD, address pools)
- ODF external (Ceph storage)
- NROP (NUMA Resources Operator + secondary scheduler)
- Multi-MCP (custom MachineConfigPools: worker-1, worker-2, etc.)
- Cert-manager (optional)
- MultiNetworkPolicy

Absent from Core, present in RAN:
- PTP, SRIOV-FEC, IBU/LCA, OADP, LSO/LVM
- Real-time kernel, workload partitioning, aggressive cluster tuning

## CR Matching Notes

Same GVK+identity matching as RAN. Core-specific considerations:
- **PerformanceProfile**: Core may have multiple (one per MCP). Match
  by `spec.nodeSelector`, not name. Uses `realTimeKernel: false`.
- **Tuned**: per-MCP. Match by `machineConfigPoolSelector`, not name.
- **MetalLB CRs**: BGPPeer is 1-to-N (match by `peerASN` + `peerAddress`).
- **ODF Secret** (`rook-ceph-external-cluster-details`): always
  partner-specific, never auto-update.
