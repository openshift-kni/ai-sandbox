# CR Matching Heuristics

Match by **GVK + resource identity** (metadata.name, metadata.namespace).
Never match by policy name, file name, or file structure.

## Confidence Levels

**Exact:** Same GVK + same name. Merge automatically.

**Fuzzy:** Same GVK, different name, similar spec structure. Always requires
user confirmation.

How to assess similarity:
1. Compare spec field paths (not values -- values differ due to customization)
2. Look for shared structural patterns (same nested objects, same array structures)
3. If there's only one CR of that Kind in both sets, it's likely a match

**No match:** Custom content, leave untouched.

## 1-to-N Matching

One reference CR may map to multiple partner CRs (e.g. partner has 3
SriovNetworkNodePolicy variants for different node types). A reference change
may need to be replicated across all matches. Present all candidates to the user.

## Per-GVK Matching Fields

### SriovNetworkNodePolicy
- Primary: `spec.deviceType`, `spec.resourceName`
- Secondary: `spec.pfNames`, `spec.numVfs`
- Note: reference uses template variables ($deviceType, $pfNames, etc.).
  Partner values replace these. 1-to-N matching is common.

### PtpConfig
- Primary: `spec.profile[].ptp4lOpts`, `spec.profile[].phc2sysOpts`
- Secondary: `spec.profile[].interface`
- Hardest matching case. Reference has ordinary clock, boundary clock,
  grandmaster, dual-follower variants. Partners rename them all and may
  use a subset. Match by PTP profile type, not name.

### PerformanceProfile
- Primary: `spec.cpu.isolated`, `spec.cpu.reserved`
- Secondary: `spec.hugepages`, `spec.realTimeKernel`
- Usually 1-to-1 but partner may have per-hardware-type variants.

### Subscription
- Primary: `spec.name` (operator name)
- Usually exact match since operator names are standardized.
- Watch for `spec.channel` version bumps.

### Tuned
- Primary: `spec.profile[].name`, `spec.recommend[].priority`
- Reference renames happen between versions (e.g. performance-patch ->
  ran-du-performance). Match by profile content, not name.

### MachineConfig
- Primary: `metadata.name` prefix pattern, `spec.config.storage.files[].path`
- Match by what files/units the MachineConfig manages.

## GVK Replacements

Between versions, a CR's GVK may change entirely (e.g. 4.18->4.20:
`ImageContentSourcePolicy` replaced by `ImageDigestMirrorSet`). Treat as
removal + addition, but present as a replacement. Carry over partner
customizations where fields map.

Known replacements:
- `ImageContentSourcePolicy` (operator.openshift.io/v1alpha1) ->
  `ImageDigestMirrorSet` (config.openshift.io/v1)

## Escalation

- Fuzzy match with high similarity: recommend accepting, still ask
- Fuzzy match with low similarity: flag as uncertain
- Multiple candidates: ask user to select
- No match for a modified reference CR: ask if they want to add it