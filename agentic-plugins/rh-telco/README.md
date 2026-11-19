# Red Hat Telco agentic plugin

Skills applicable to deploying, managing, and operating OpenShift clusters
running telco workloads.

**Persona**: Telco partner platform engineer (OpenShift RAN or Core)
**Marketplaces**: Lola, Claude Code

**AI-generated output requires expert human review.** These skills rely
on a large language model (LLM) to produce their results. LLMs can and do
make mistakes — including reasonable-looking output that is subtly wrong.
You **must** review all generated output (policies and other artifacts)
for correctness, completeness, accuracy, and suitability before applying
them to your environment. Do not deploy AI-generated configuration
without thorough expert human review.

**Data handling and privacy.** Any input provided to these skills —
including policy files, configuration data, cluster details, and Git
repository content — may be sent to the LLM for processing.

See the full
[disclaimer](https://github.com/openshift-kni/ai-sandbox/blob/main/rds-policy/README.md#important-security-privacy-and-disclaimer).

## Getting Started

The skills are tested with Claude Code. You can install them with Lola or as
a Claude Code plugin. The plugin also includes any hooks a skill ships with;
Lola installs only the skills.

### Lola

From your project:

```bash
lola market add rh-agentic-collections https://raw.githubusercontent.com/RHEcosystemAppEng/agentic-catalog/main/marketplace/rh-agentic-collection.yml
lola install rh-telco -a claude-code
```

Lola puts the skills in `.claude/skills/` and keeps a copy of the catalog in
`.lola/`. Add `.lola/` to your `.gitignore`.

To update, remove the module and install it again. Removing it uninstalls it
from every project, so reinstall it wherever you use it:

```bash
lola market update rh-agentic-collections
lola mod rm -f rh-telco
lola install rh-telco -a claude-code
```

### Claude Code plugin

```bash
claude plugin marketplace add RHEcosystemAppEng/agentic-catalog
claude plugin install rh-telco@ecosystem-plugins
```

To update:

```bash
claude plugin marketplace update ecosystem-plugins
claude plugin update rh-telco@ecosystem-plugins
```

## Skills

### rds-policy-update

Updates your Day 2 PolicyGenerator policies when you move to a new OCP
version, say 4.18 to 4.20. Both the RAN and Core reference configurations
are handled with the same skill. You need `podman` with access to
`registry.redhat.io` and read access to your policies. Then ask:

```
upgrade my policies from 4.18 to 4.20, the policy source is ./acme-ran
```

See the
[rds-policy-update docs](https://github.com/openshift-kni/ai-sandbox/blob/main/rds-policy/README.md#quick-start)
for the full prerequisites, what a run does, and the validation hook.

## Development

The source, design docs, and evals are in
[openshift-kni/ai-sandbox](https://github.com/openshift-kni/ai-sandbox).
To test local changes:

```bash
claude --plugin-dir /path/to/ai-sandbox/agentic-plugins/rh-telco
```
