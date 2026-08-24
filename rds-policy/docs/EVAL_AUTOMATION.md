# RDS Policy Agent — Eval Automation Design

Proposal for running the `rds-policy-update` skill evals on a schedule and
keeping a record of results over time.

## Problem

The suite ([evals/](../evals/)) runs locally, by hand, one pass at a time.
Two gaps:

1. Run it on a schedule (weekly), unattended.
2. Keep a trend record so scores, cost, and latency are comparable across runs.

## Design

Split the system into the container and the infra around it. The container is
the eval itself, built once. The infra only schedules it, runs it, and hands it
a token. Switching infra never changes the container, so the work carries across.

### The container (fixed)

The container is the existing promptfoo suite, run inside the OpenShell sandbox
via `make eval`. Same suite as today's local run, now placed in OpenShell.
OpenShell adds three things:

- **Sandboxing** — the agent runs with confined egress.
- **Audit** — the agent's tool calls and commands are logged.
- **Credential management** — OpenShell holds the token and brokers egress, so
  the agent never handles the raw secret.

Runaway is already bounded: `promptfooconfig.yaml` sets `max_turns` and
`max_budget_usd` per test. No new limits needed.

We supply our own Vertex service-account credential, since we cannot mount
another team's. We hand it to OpenShell to manage, so the infra only needs
somewhere to store the one secret. The handoff is the same on any platform.

### The infra: where the container runs

The infra does three things, none of which changes the container: **schedule**
(when it fires), **run** (the compute), and **store a secret** (the token).
GitHub Actions is out by org policy. Three ways to get the rest:

**Our cluster, an OpenShift CronJob (simplest).** We already run OpenShell on a
cluster, so little is new: a `CronJob` is the scheduler, the cluster is the
runner, a `Secret` holds the token, and a `PVC` keeps the history. The CronJob
kicks off an OpenShell sandbox run each week. Iterate with `oc apply`, and
optionally add a `Route` to serve the dashboard.

**Prow (org standard).** Prow already runs jobs for this repo, saves artifacts
to GCS, and has a path into the org's metrics. The catch is OpenShell. OpenShell
is a capability we run on a cluster, not a container a job pulls in; a Prow job
is one throwaway pod on a shared CI cluster that has no OpenShell, and those CI
clusters likely cannot reach the cluster where ours runs. So keeping OpenShell
under Prow means standing it up per run: spin up a cluster, install OpenShell,
run the eval, tear it down. On top of that, the job and its schedule live in
`openshift/release`, not here, so every change is a PR there and a push-and-wait
loop, with no built-in trend dashboard. There may be a lighter way to attach
OpenShell under Prow; we have not explored it, and it can wait.

**GitLab (managed alternative).** Scheduler, secret store, and a Pages dashboard
as a service, editable in the repo. Useful only if we do not want to own a
cluster: it still needs a runner (a personal namespace has none) and adds a
platform. Given we already have the cluster, it is redundant.

## Recommendation

The container is the same everywhere, so only the infra switches:

- **Short term: the CronJob on our cluster.** Fewest moving parts, reuses
  OpenShell and Vertex, iterate with `oc apply`. Whichever infra we land on, we
  first have to know what a cluster needs to run the OpenShell CronJob, and this
  is where we learn it end to end.
- **Long term: Prow.** The org-standard home once the loop is proven and
  OpenShell's requirements are understood.

## Trend Record

promptfoo writes a full `results.json` per run: every test's assertions and
score, token usage, cost, latency, model IDs, and timestamps. It is large and
can contain agent transcripts, so it stays on the `PVC` as drill-down only and
rotates out.

What we track over time is a small `summary.json` distilled from it (pass rate,
per-test score, cost, latency, model IDs, git SHA). It is tiny and numbers-only,
so we commit it to the repo. Git is the durable record: diffable, reviewable,
and independent of the cluster. Each run appends one summary and pushes it, using
a repo write token that OpenShell holds and brokers just like the Vertex one. A
small static page can render the committed history as a trend.

## Non-Goals

- No merge gating on LLM evals — they are non-deterministic.
- No promptfoo cloud / `--share` — do not upload transcripts to a third party.
