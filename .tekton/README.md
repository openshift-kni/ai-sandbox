# Konflux skill evaluation

The pipeline has three tasks: **init → clone-repository → evaluate-skill**.
It evaluates only `agentic-plugins/rh-telco/skills/rds-policy-update` on PRs
to `main` that change that skill or `.tekton/`.

The evaluator's defaults and native result reporting are unchanged. There
is no additional score threshold, pass/fail gate, aggregation task, custom
script, or test harness. Promptfoo remains separate. The supplied Task's
default runs Tier A scans; Tier B LLM evaluation is not opted in here.

## Reference and task import

The init/clone bundles and trusted-source wiring follow the
[GitLab PR pipeline](https://gitlab.cee.redhat.com/ai5-marketplace/agentic-plugins/-/blob/1a57de53e7ed45ac815f19b691aa7da684b7402b/.tekton/skills-evaluation-pull-request.yaml).
GitLab `main` was verified at that commit on 2026-10-28.

The evaluator is imported directly from
[the supplied GitHub task repository](https://github.com/RHEcosystemAppEng/konflux-ai5-evaluation/blob/383c76c5dc4bdaf7b8ff371cd13328b6868a233e/task/aeh-skill-eval/aeh-skill-eval.yaml)
at the pinned commit. Its `0.1.0` interface supports this repo's nested
skill path. The GitLab reference now uses `2.0.1`, whose batch runner
accepts only `<pack>/<skill>` IDs and expects `<pack>/skills/<skill>` at
the source root. Keeping the supplied Task avoids adding a layout adapter.
Its documented `0.1.0` bundle is unavailable, so the import uses the Git
resolver rather than that bundle. Runtime image defaults remain upstream-owned.

## Values to request from the Konflux team

The PaC Repository belongs in the team's tenant namespace. It needs these
custom parameters under `spec.params`:

| Parameter | Team-provided value |
| --- | --- |
| `konflux_application` | Application name |
| `konflux_component` | Component name |
| `build_service_account` | Build service account with registry credentials |
| `artifact_storage` | Writable Quay repository without a tag, e.g. `quay.io/<org>/<repo>` |

The team also needs GitHub/PaC onboarding, Git and bundle resolvers,
registry access, and a default storage class for the 2Gi scratch PVC.
PaC supplies `source_url`, `revision`, and `git_auth_secret` automatically.
The PipelineRun has no hardcoded namespace.

YAML and imported Task interfaces can be checked locally. A live Konflux
run still requires the team configuration above.
