# Merge Conflict Resolution

## Customization Preservation

All partner customizations preserved by default. No classification as
intentional vs stale (stale workaround detection is future scope).

## Non-overlapping Changes

Reference changes fields the partner hasn't customized -- apply automatically.

Example: reference bumps `spec.channel: "4.18"` to `"4.20"`, partner hasn't
patched channel -- update automatically.

## True Conflicts

Both sides changed the same field. Flag for human review with:
- Field path
- Reference old value and new value
- Partner's current value
- Why the reference changed (from EXPLAIN output)
- User chooses: accept reference, keep partner, or provide different value

Example: reference changes `spec.deviceType: netdevice` to `vfio-pci`,
partner has `netdevice` as explicit patch -- conflict, user decides.

## CR Removal

Removing a CR from a policy does NOT remove it from clusters. Need
`complianceType: mustnothave` for actual removal. If reference includes
a removal policy, include it in the merge.

If partner has customizations on a CR being removed, flag for user --
they may still need it.

## New CRs from Reference

Add to closest-fit existing partner policy based on:
1. Same wave grouping
2. Similar content (e.g. logging CRs go with existing logging policy)
3. If no clear fit, ask the user which policy to add it to

Preserve partner naming conventions for the policy.

## New Functionality from User

When the user requests new features (e.g. "add logging health check"),
treat as an additional merge step after reference updates. The user's
description guides what to add; reference CRs for the target version
provide the implementation.