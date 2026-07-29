# RDS Policy Agent

AI-driven policy generation for OpenShift RDS version updates. Helps telco
partners update Day 2 configuration policies when moving between OCP versions
(e.g. 4.18 to 4.20).

## Quick Start

Install as a plugin (skill + validation hook):

```sh
/plugin marketplace add openshift-kni/ai-sandbox
/plugin install rds-policy@openshift-kni-ai-sandbox --project  # team-shared
/plugin install rds-policy@openshift-kni-ai-sandbox --local    # personal only
```

Then prompt:

```
upgrade my policies from 4.18 to 4.20
```

For local development, run from `rds-policy/` or use `--plugin-dir`:

```sh
claude --plugin-dir /path/to/ai-sandbox/rds-policy
```

### Prerequisites (optional, for validation hook)

- `kustomize` (v4.5+)
- [PolicyGenerator plugin](https://github.com/open-cluster-management-io/policy-generator-plugin)
  binary at `~/.config/kustomize/plugin/policy.open-cluster-management.io/v1/policygenerator/PolicyGenerator`

Without these, the skill works normally but the validation hook is a
no-op.

## Skill image

Content-only OCI image for Kubernetes image volume mounts. The operator
mounts it read-only into the sandbox pod at `/app/skills/rds-policy-update/`
via the AgenticRun `tools.skills[]` spec:

```yaml
tools:
  skills:
  - image: <registry>/rds-policy-skill:latest
    paths: ["/skills/rds-policy-update"]
```

Build from this directory:

```sh
make build
# or: podman build -f Containerfile -t rds-policy-skill:latest .
```

## Docs

- [DESIGN.md](docs/DESIGN.md) — architecture and design
- [EVAL.md](docs/EVAL.md) — eval plan and framework
- [HOOKS.md](docs/HOOKS.md) — validation hook details and what it catches
