// Wraps promptfoo's opencode:sdk provider, which reports only the agent's last
// step. Returns what the assertions read from the Claude provider: every tool
// call in metadata.toolCalls, plus token usage summed across the session.
// promptfoo fetches session history only while the skill tool is enabled.
const { Agent, setGlobalDispatcher } = require('undici');

// session.prompt holds one request open for the whole run, so Node's default
// 300s headers timeout would drop longer runs. Stays above the 15 min latency gate.
const RUN_TIMEOUT_MS = 20 * 60 * 1000;
setGlobalDispatcher(new Agent({ headersTimeout: RUN_TIMEOUT_MS, bodyTimeout: RUN_TIMEOUT_MS }));

const TOOL_NAMES = { bash: 'Bash', edit: 'Edit', write: 'Write' };

function toToolCall(part) {
  const { filePath, command } = part.state?.input ?? {};
  return { name: TOOL_NAMES[part.tool] ?? part.tool, input: { file_path: filePath, command } };
}

function sumTokenUsage(steps) {
  const sum = (read) => steps.reduce((total, step) => total + (read(step.tokens) ?? 0), 0);
  const cached = sum((tokens) => tokens.cache?.read);
  const reasoning = sum((tokens) => tokens.reasoning);
  return {
    total: sum((tokens) => tokens.total),
    prompt: sum((tokens) => tokens.input),
    completion: sum((tokens) => tokens.output),
    cached,
    numRequests: steps.length,
    completionDetails: { reasoning, cacheReadInputTokens: cached },
  };
}

class OpenCodeProvider {
  constructor(options) {
    this.options = options;
    this.sessionParts = new Map();
  }

  id() {
    return 'opencode:sdk';
  }

  async load() {
    const { loadApiProvider } = await import('promptfoo');
    const inner = await loadApiProvider('opencode:sdk', { options: { ...this.options, id: undefined } });
    const fetchParts = inner.fetchCurrentPromptParts.bind(inner);
    inner.fetchCurrentPromptParts = async (client, session, ...rest) => {
      const parts = await fetchParts(client, session, ...rest);
      this.sessionParts.set(session.sessionId, parts);
      return parts;
    };
    return inner;
  }

  async callApi(prompt, context, callOptions) {
    this.inner ??= this.load();
    const response = await (await this.inner).callApi(prompt, context, callOptions);
    const parts = this.sessionParts.get(response.sessionId);
    this.sessionParts.delete(response.sessionId);
    if (!parts?.length) {
      return response;
    }
    return {
      ...response,
      tokenUsage: sumTokenUsage(parts.filter((part) => part.type === 'step-finish')),
      metadata: {
        ...response.metadata,
        toolCalls: parts.filter((part) => part.type === 'tool').map(toToolCall),
      },
    };
  }

  async cleanup() {
    await (await this.inner)?.cleanup();
  }
}

module.exports = OpenCodeProvider;
