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
- **Credential management** — the gateway URL and key are passed into the
  sandbox. The agent can read the key, so confined egress is what contains it.

`promptfooconfig.yaml` bounds each test with `max_turns` and `max_budget_usd`,
and `PROMPTFOO_EVAL_TIMEOUT_MS` adds a per-test wall-clock timeout. These limit
one test, not the run as a whole, so the infra also bounds the job (see the
CronJob below).

We supply our own model gateway URL and key, since we cannot mount another
team's. We pass them into the sandbox, so the infra only needs somewhere to
store them. The handoff is the same on any platform.

### The infra: where the container runs

The infra does three things, none of which changes the container: **schedule**
(when it fires), **run** (the compute), and **store a secret** (the token).
GitHub Actions is out by org policy. Three ways to get the rest:

**Our cluster, an OpenShift CronJob (simplest).** We already run OpenShell on a
cluster, so little is new: a `CronJob` is the scheduler, the cluster is the
runner, a `Secret` holds the token, and a `PVC` keeps the history. The CronJob
kicks off an OpenShell sandbox run each week and bounds the job with
`concurrencyPolicy: Forbid` so runs never overlap, `activeDeadlineSeconds` of an
hour (a normal run takes minutes) to kill a hung run, `backoffLimit: 0` so a
failed run is not retried and billed twice, and CPU and memory limits on the
pod. Iterate with `oc apply`, and optionally add a `Route` to serve the
dashboard.

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
  OpenShell and our existing credential, iterate with `oc apply`. Whichever
  infra we land on, we first have to know what a cluster needs to run the
  OpenShell CronJob, and this is where we learn it end to end.
- **Long term: Prow.** The org-standard home once the loop is proven and
  OpenShell's requirements are understood.

## Trend Record

promptfoo writes a full `results.json` per run: every test's assertions and
score, token usage, cost, latency, model IDs, and timestamps. It is large and
can contain agent transcripts, so it stays on the `PVC` as drill-down only and
rotates out.

We keep it for one case: a failed run. `summary.json` tells us which test
dropped; the full file tells us why. It has the judge's reasoning for each score,
the agent's transcript, and what the skill produced (the `rds-merge-*` outputs),
so we can see what went wrong or re-grade later without re-running the agent. This
matters because the evals are non-deterministic: a bad run may not happen again,
so if we do not save it the evidence is lost. That is also why the file rotates
out — we only need it for runs that fail.

Proposed retention: the `PVC` keeps the full file for the last five runs, about
five weeks at one run a week, which leaves time to triage a failure. Each job
deletes the oldest run before writing its own. A failed run worth keeping longer
gets copied off the `PVC` by hand.

What we track over time is a small `summary.json` distilled from it (pass rate,
per-test score, cost, latency, model IDs, git SHA). It is small and holds no
transcripts or agent output, so we commit it to the repo. Git is the durable
record: diffable, reviewable, and independent of the cluster. Each run appends
one summary and pushes it, using a repo write token that OpenShell holds and
brokers. A small static page can render the
committed history as a trend.

As an option, we can self-host promptfoo's own server (a Docker image with a
persistent volume) and push each run to it with `promptfoo share`. That gives the
full promptfoo UI — run history, run-to-run diffs, and transcript drill-down —
with nothing to build, and since it is our own server it does not break the
third-party non-goal. The cost is a standing service to run, secure, and back up:
it stores everything, transcripts included, in SQLite on a volume, has no
built-in auth, and promptfoo itself calls it experimental, not production. So the
git summary stays the durable trend record; the self-hosted server is an optional
richer view over the same runs. To go beyond a trial, the server would have to
be an official managed service, not one we stand up and look after ourselves.
Before building one, check what already runs that we could use instead, such as
DCI.

## Non-Goals

- No merge gating on LLM evals — they are non-deterministic.
- No promptfoo cloud / `--share` — do not upload transcripts to a third party.
