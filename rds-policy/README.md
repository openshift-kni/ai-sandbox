# RDS Policy Agent

AI-driven policy generation for OpenShift RDS version updates. Helps telco
partners update Day 2 configuration policies when moving between OCP versions
(e.g. 4.18 to 4.20).

## Important: Security, Privacy, and Disclaimer

This skill is provided as a tool to assist you in making updates to your
configuration policies. Read this section before using the skill.

**No warranty.** This skill is provided "as is" without warranty of any
kind. We do not guarantee the quality, correctness, completeness, or
suitability of its output for any particular environment or use case. See
LICENSE file in the root directory of this repository.

**AI-generated output requires expert human review.** This skill relies
on a large language model (LLM) to produce its results. LLMs can and do
make mistakes — including reasonable-looking output that is subtly wrong.
You **must** review all generated output (policies and other artifacts)
for correctness, completeness, accuracy, and suitability before applying
them to your environment. Do not deploy AI-generated configuration
without thorough expert human review.

**Data handling and privacy.** Any input provided to the skill —
including policy files, configuration data, cluster details, and Git
repository content — may be sent to the LLM for processing. Before using
the skill, ensure that:

- The LLM provider and hosting model meet your organization's
  requirements for **data privacy**, **data protection**, and **data
  retention**.
- Appropriate data protection agreements (DPAs) are in place with your
  LLM provider.
- You use privately hosted or locally running models if your data
  classification requires it.
- You anonymize or redact sensitive information in inputs where
  necessary.

**Credentials and access control.** Installing the skill into your
environment (e.g. harness) gives it access to the LLM you have
configured and authenticated in that environment. You are responsible
for ensuring that:

- The execution environment has access **only** to the data and systems
  you intend to expose to the skill.
- The environment is sufficiently sandboxed to prevent unintended access
  to other systems, networks, or data stores.
- No credentials are available in the environment that could allow the
  skill (or the LLM) to escalate access beyond what you explicitly
  intend to provide — including Git tokens, API keys, cloud provider
  credentials, and cluster kubeconfigs.

**Not a substitute for your validation process.** The skill's output
should pass through your existing change management, review, and CI/CD
pipelines — not bypass them. Treat its output as a draft that requires
the same scrutiny as any hand-written policy change.

**Non-deterministic output.** LLM-generated results are inherently
non-deterministic. Running the same prompt twice may produce different
output. Always validate results against your requirements rather than
assuming consistency across runs.

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

### Prerequisites

- **TLS certificates** — all root and self-signed certificates required
  to reach internal Git hosts must be present in the execution
  environment's trust store before running the skill.

#### Optional (for validation hook)

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
