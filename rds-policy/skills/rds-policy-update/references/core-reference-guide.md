# Core Reference Guide

This file provides additional content for the Core use case: container
image, directory layout, PG naming, CR catalog, and CR matching details
(see CR Matching Notes below). The EXPLAIN → MERGE → VALIDATE workflow
and PolicyGenerator format are common to all use cases.

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
