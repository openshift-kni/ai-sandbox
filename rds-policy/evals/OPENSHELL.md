# Run the eval in OpenShell

One command creates a fresh confined sandbox, uploads the checkout, installs
the pinned dependencies, runs Promptfoo, downloads the results, and deletes the
sandbox. The model gateway key stays on the OpenShell gateway as a provider. The
sandbox gets a placeholder in `ANTHROPIC_API_KEY`, and OpenShell's proxy swaps in
the real key on requests to the model gateway, so the agent never sees it.

## Prerequisites

- OpenShell CLI and gateway version 0.0.116 or newer
- A registered gateway (`openshell gateway list`)
- An Anthropic-compatible model gateway on HTTPS port 443 that serves the agent
  model and `claude-sonnet-5`, the judge

There is no config file to edit. The scripts read the environment, and the gateway comes
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
| `setup.sh` | store the model gateway key as a provider, once per gateway |
| `run.sh` | the whole run: create, upload, eval, collect, delete |
| `collect.sh` | download one sandbox's results; for retrying a failed download |
| `clean.sh` | delete one sandbox |

Each script's header lists the variables it reads.

## Set up the key

Once per gateway, and again when the key or URL changes:

```sh
export ANTHROPIC_BASE_URL=<model gateway url> ANTHROPIC_API_KEY=<key>
make openshell-setup
```

`setup.sh` imports `openshell-provider.yaml` as a provider profile for the model
gateway host and creates the `rds-model-gateway` provider from
`ANTHROPIC_API_KEY`. The CLI reads the key from the environment, so it is not
on the command line. After this, `run.sh` doesn't need the key.

## Run

```sh
export ANTHROPIC_BASE_URL=<model gateway url> RDS_AGENT_MODEL=<agent model>
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
ownership", rerun with `PROMPTFOO_CONCURRENCY=1`.

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

`run.sh` fills in the model gateway's host from `ANTHROPIC_BASE_URL` and passes
`openshell-policy.yaml` on `sandbox create`. Gateways provisioned by
the team's `ooo` installer carry a global policy lock, and then the global
policy applies instead; `openshell policy get <sandbox>` shows which one is in
effect. Either way the eval needs egress to the model gateway, the npm registry,
PyPI, and GitHub release assets.

The rule for the model gateway must be L7 (`protocol: rest`), or OpenShell
can't add the key and refuses to create the sandbox. Endpoints from the provider
profile are not added to a global policy, so on a locked gateway the global
policy itself must list the model gateway host with `protocol: rest`.

`run.sh` creates the sandbox from the OpenShell community `base` image
(`--from base`), which already ships uv, Python 3.14, node and git, so the run
goes straight to `make setup`. Override with `OPENSHELL_IMAGE` if you need the
gateway's own default (on `ooo`-provisioned gateways that is
`quay.io/telco5gci/sandbox`, which has Python 3.13 and no uv, and will not work
without reinstating an install step). Base also exports
`VIRTUAL_ENV=/sandbox/.venv`; `run.sh` unsets it so `uv sync` uses the project's
own venv.
