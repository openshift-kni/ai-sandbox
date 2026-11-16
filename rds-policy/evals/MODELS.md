# Model comparison

The same eval, run with three agent models and judged by Sonnet 5
(`claude-sonnet-5`) through the same gateway.

## Setup

- Run on 2026-11-16 with this branch's config.
- Agents: Opus 4.8, DeepSeek V4.1 Flash and GLM 5.3, all through one
  Anthropic-compatible gateway.
- `make eval-repeat`: the 4 tests, 3 passes each, 3 at a time, one model after
  another on one laptop.
- `max_budget_usd` was $25 for all three instead of $4. Claude Code prices models
  it doesn't know at default rates, so the $4 cap could stop an open model
  partway through.
- The host had no `registry.redhat.io` login.

Scores are out of 100. Each one is a test's weighted average across its checks,
and a test passes at 90% (see [Scoring](#scoring)). The runs finished before the
90% threshold and the `topology-preservation` weight went in, so the scores below
were recomputed from the saved check results. Nothing was rerun.

## Scores

Average of the 3 runs, with each run's score in brackets.

| Test | Opus 4.8 | DeepSeek V4.1 Flash | GLM 5.3 |
| --- | --- | --- | --- |
| Explain | 50% (25, 100, 25) | 50% (100, 25, 25) | 33% (25, 50, 25) |
| Merge | 99% (100, 97, 100) | 98% (100, 97, 96) | 64% (0, 98, 95) |
| Required CR severity | 100% (100, 100, 100) | 100% (100, 100, 100) | 92% (100, 100, 75) |
| Topology preservation | 95% (86, 100, 100) | 91% (100, 86, 86) | 83% (86, 67, 95) |
| Overall | 86% | 85% | 68% |
| Runs at 90% or more | 9 of 12 | 8 of 12 | 5 of 12 |

| | Opus 4.8 | DeepSeek V4.1 Flash | GLM 5.3 |
| --- | --- | --- | --- |
| Wall time, 12 runs | 17 min | 14 min | 25 min |
| Median Merge run | 7.2 min | 4.6 min | 11.2 min |
| Agent tokens | 10.7M | 12.1M | 8.7M |
| Judge tokens | 0.35M | 0.53M | 0.34M |
| Agent cost at list price | $15 | not known | not known |

Claude Code doesn't know the open models' prices, so it can't report their
cost.

## What went wrong, run by run

### Opus 4.8

- Explain: one run was perfect. The other two stopped to ask for a registry
  login.
- Merge: one run was perfect. The other two kept the NMState operator CR, which
  the 4.20 reference drops, and kept pinned 4.18 values. One of them also dropped
  the `group.ice-ptp` entry from the partner's Tuned scheduler patch and didn't
  flag the catalog tag.
- Required CR severity: all three runs were perfect.
- Topology: two runs were perfect. One got half credit on the worker-1 warning.

### DeepSeek V4.1 Flash

- Explain: one run was perfect. The other two stopped to ask for a registry
  login instead of using the reference snapshots in `fixtures/`.
- Merge: one run was perfect. One didn't replace the monitoring CR with
  `ReduceMonitoringFootprint` and didn't write `kustomization.yaml`. The third
  didn't write `kustomization.yaml` either, and didn't flag the catalog image tag
  `1.3.0`.
- Required CR severity: all three runs were perfect.
- Topology: one run was perfect. The other two got half credit on the worker-1
  warning. They called worker-1's profile a standalone fork that won't get the
  new kernel arg, but didn't say it matches no reference pool.

### GLM 5.3

- Explain: two runs stopped at the registry login. The third found an upstream
  ZTP site-generator image cached on the host, extracted the real 4.18 and 4.20
  references from it and explained those, so it missed the fixture's changes.
- Merge: one run hit the 60-turn limit and scored 0. Another dropped a
  `group.ice-ptp` entry from the partner's Tuned scheduler patch and didn't flag
  the catalog tag. The third kept pinned 4.18 versions, didn't write
  `kustomization.yaml` and didn't flag the catalog tag.
- Required CR severity: one run stopped at the registry login.
- Topology: one run changed the partner's real-time profile by adding
  `module_blacklist=irdma`, which the skill says not to do. Another got half
  credit on the worker-1 warning. Two runs also failed the channel check, which
  only looks at patches (see below).

## Overall

Opus and DeepSeek finish within two points of each other, and the gap is
smaller than the run-to-run spread. Opus is a little ahead on Topology, where
it gave the full worker-1 warning in two runs out of three against DeepSeek's
one. DeepSeek is a little faster, and Opus is the only model that kept the
NMState CR the Merge check expects to be removed. Both lose half of Explain to
the registry login. GLM trails on every test and takes the longest.

## DeepSeek vs GLM

GLM took almost twice as long: 25 minutes against 14 overall, and 11 minutes per
Merge run against under 5. It also ran out of turns once in Merge, while
DeepSeek never errored.

The clearest behavioral difference is how they treat partner content. DeepSeek
always left the partner's own real-time profile alone and flagged it. GLM asked
whether to change it and listed "Yes, add it" as the recommended first choice.
The eval answers every question with the first choice, so the change went
through.

On Merge accuracy they share two misses: both forgot `kustomization.yaml` and the
catalog tag. GLM also dropped a Tuned scheduler entry, and DeepSeek once missed
the monitoring CR replacement.

Neither Explain score says much about the model (see the next section). GLM went
looking for references elsewhere on the host, while DeepSeek either used the
fixtures or stopped to ask.

## Failures by cause

Most failures come from the test environment. With no registry login, agents
either use the `fixtures/` snapshots or stop to ask, and on a laptop they can
also reach cached images, other temp files and the rest of the home directory.
That explains most of the low Explain scores and GLM's 75% in Required CR
severity. The OpenShell sandbox avoids this: DeepSeek scored 12/12 on Explain
there.

The runs also weren't isolated from each other. They share `/tmp`, agents
extract references to fixed paths like `/tmp/ref-4.18` and reuse whatever an
earlier run left there, and they list each other's output directories and
pointer files. The cleanup between models failed too, so GLM and Opus ran with
earlier models' files still in `/tmp`, and GLM's runs touched DeepSeek's
leftovers. The scores can't separate this noise out.

Some checks fail correct work. `semver-sweep` fails an agent that keeps pinned
4.18 values and flags them, which is what the skill asks for. The T4 channel
check reads only patches, so it fails an agent that correctly drops a redundant
channel patch.

The judge is inconsistent on one point: Sonnet gives the worker-1 warning 1.0
in some runs and 0.5 in others for the same "standalone fork" wording.

The real misses are the missing `kustomization.yaml`, the unflagged catalog tag,
the dropped Tuned entry (Opus and GLM once each), the kept NMState CR (Opus
twice), DeepSeek's missed monitoring CR, and GLM's change to the partner profile
and its turn limit.

Fixes for the check and judge issues are in progress and aren't part of these
runs.

## Scoring

A test's score is the weighted average of its checks, and it passes at 0.9
(`defaultTest.threshold`), so a single minor miss doesn't fail a test. Checks
that should fail a test on their own carry more weight: `safety` (5) in Merge
and `topology-preservation` (2) in Topology. `cost` and `latency` lower the
score but can't fail a test by themselves.

Merge scores sit close to 100% even when a run gets something wrong. Most of
its checks give partial credit, so a missed file check might score 16/17 and
cost the run less than a point. Read the failures, not just the percentage.

## Reproduce

```bash
export ANTHROPIC_BASE_URL=<gateway url> ANTHROPIC_API_KEY=<key>
RDS_AGENT_MODEL=<model> make eval-repeat
```

Results stay local in `~/.promptfoo/promptfoo.db`, and `make eval-view` opens
them.
