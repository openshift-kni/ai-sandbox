# Run the eval in OpenShell

One command creates a fresh confined sandbox, uploads the checkout, installs
the pinned dependencies, runs Promptfoo, downloads the results, and deletes the
sandbox. Vertex credentials never enter the sandbox: they stay on the gateway
as an OpenShell provider.

## Prerequisites

- OpenShell CLI and gateway version 0.0.116 or newer
- A registered gateway (`openshell gateway list`)
- Google Cloud Application Default Credentials with access to the configured
  Vertex models

There is no config file. The scripts read the environment, and the gateway comes
from the CLI's own `OPENSHELL_GATEWAY`, so your current gateway is used unless
you override it:

```sh
export OPENSHELL_GATEWAY=my-gateway   # optional; only if it is not the current one
```

Four scripts in `scripts/`, one per step, using `openshell` commands with shell
orchestration. `make openshell-<name>` just runs `scripts/<name>.sh`, so CI can call
either, and you can copy a command out of one and run it by hand.

| Script | What it does |
| --- | --- |
| `setup.sh` | one-time per gateway: store your gcloud ADC there as a provider |
| `run.sh` | the whole run: create, upload, eval, collect, delete |
| `collect.sh` | download one sandbox's results; for retrying a failed download |
| `clean.sh` | delete one sandbox |

Each script's header lists the variables it reads.

## One-time: register the Vertex provider

```sh
make openshell-setup
```

This stores your local gcloud ADC on the gateway as a `google-vertex-ai`
provider. A sandbox created with `--provider` sees only a placeholder token in
`GOOGLE_VERTEX_AI_TOKEN`, plus `ANTHROPIC_VERTEX_PROJECT_ID` and
`CLOUD_ML_REGION`; the sandbox proxy substitutes the real short-lived token on
requests to `aiplatform.googleapis.com`. That placeholder is handed to both
Vertex clients: Claude Code skips its own Google auth
(`CLAUDE_CODE_SKIP_VERTEX_AUTH=1`) and sends it as its bearer token, and the
judge switches from Promptfoo's `vertex:` provider, which insists on an ADC
file, to the plain HTTP client configured in `promptfooconfig.yaml`.
Both grader clients are configured in that file; `make eval-openshell` selects
the HTTP client with `PROMPTFOO_GRADING_PROVIDER=https`. No credential file is
uploaded.

## Run

```sh
export VERTEX_AI_PROJECT_ID=my-gcp-project
make openshell-setup    # once per gateway
make openshell-run
```

One-test smoke run:

```sh
make openshell-run PROMPTFOO_EVAL_ARGS='--filter-first-n 1'
```

`run.sh` names the sandbox `rds-<MMDD-HHMMSS>` and uses `sandbox create --upload`
to create it and upload the checkout
(honoring `.gitignore`, so `node_modules`, `.venv`, and `results/` stay local),
starts the install-and-eval job, polls until it exits, downloads the results,
and deletes the sandbox. It exits with the eval's own code. Pass
`OPENSHELL_SANDBOX` to choose the name, and `OPENSHELL_KEEP=1` to keep the
sandbox running after the download so you can look around in it; delete it
with `make openshell-clean` when you are done.

Install and eval run as one detached job inside the sandbox, polled with short
`sandbox exec` calls, because attached exec streams are cut by the OpenShift
route's idle timeout once they go quiet for about a minute. Promptfoo runs three
tests at a time (`PROMPTFOO_CONCURRENCY`; the full suite takes about seven
minutes). If a run reports `policy_denied` with "ambiguous shared socket
ownership", rerun with `PROMPTFOO_CONCURRENCY=1`: that denial hit the judge's ADC
token refresh once at concurrency 4 and has not recurred since the credential
file left the sandbox.

If the download fails, `run.sh` keeps the sandbox and prints the retry. Finish it
by hand:

```sh
OPENSHELL_SANDBOX=rds-0918-1400 make openshell-collect
OPENSHELL_SANDBOX=rds-0918-1400 make openshell-clean
```

To watch a run started in another shell, or to leave one going overnight:

```sh
make openshell-run &
openshell sandbox exec --name rds-0918-1400 --no-tty -- tail -n 30 /sandbox/rds-eval-results/eval.log
```

## Results

Each run lands in `results/<sandbox-name>/`: `promptfoo.json`, `eval.log`,
`exit-code`, the Promptfoo SQLite state, and any `rds-merge-*` output the agent
wrote. `results/latest` points to the most recent collected run. Browse it
with:

```sh
make openshell-view
```

That sets `PROMPTFOO_CONFIG_DIR` to the downloaded state; your local Promptfoo
database is untouched.

## Policy and image

`openshell-policy.yaml` is passed on `sandbox create` by `run.sh`. Gateways provisioned by
the team's `ooo` installer carry a global policy lock, and then the global
policy applies instead; `openshell policy get <sandbox>` shows which one is in
effect. Either way the eval needs egress to Vertex, the npm registry, PyPI, and
GitHub release assets.

`run.sh` creates the sandbox from the OpenShell community `base` image
(`--from base`), which already ships uv, Python 3.14, node and git, so the run
goes straight to `make setup`. Override with `OPENSHELL_IMAGE` if you need the
gateway's own default (on `ooo`-provisioned gateways that is
`quay.io/telco5gci/sandbox`, which has Python 3.13 and no uv, and will not work
without reinstating an install step). Base also exports
`VIRTUAL_ENV=/sandbox/.venv`; `run.sh` unsets it so `uv sync` uses the project's
own venv.
