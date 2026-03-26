# AgentCore Deploy

Deploy DevDuck to Amazon Bedrock AgentCore with one command.

---

## Quick Deploy

```bash
devduck deploy --launch
```

This:

1. Creates a deployment directory with handler + requirements
2. Configures the agent with `agentcore` CLI
3. Launches the agent on AgentCore
4. Returns the agent ARN for invocation

---

## Prerequisites

```bash
pip install bedrock-agentcore
aws configure  # or have valid AWS credentials
```

---

## Commands

### Deploy

```bash
# Configure only (no launch)
devduck deploy

# Configure AND launch
devduck deploy --launch

# Custom configuration
devduck deploy \
    --name code-reviewer \
    --tools "strands_tools:shell,file_read;devduck.tools:use_github,editor" \
    --model "us.anthropic.claude-sonnet-4-20250514-v1:0" \
    --system-prompt "You are a senior code reviewer" \
    --region us-west-2 \
    --launch

# Full example with all options
devduck deploy \
    --name my-agent \
    --tools "strands_tools:shell" \
    --idle-timeout 1800 \
    --max-lifetime 43200 \
    --no-memory \
    --no-otel \
    --env "MY_VAR=value" \
    --env "OTHER=123" \
    --force-rebuild \
    --launch
```

### List Agents

```bash
devduck list
devduck list --region us-east-1
```

### Check Status

```bash
devduck status --name my-agent
```

### Invoke

```bash
devduck invoke "analyze this code" --name my-agent
devduck invoke "hello" --agent-id abc123
```

---

## Deploy Options

| Flag | Default | Description |
|------|---------|-------------|
| `--name` | `devduck` | Agent name |
| `--tools` | default set | Tool configuration |
| `--model` | claude-sonnet-4 | Model ID |
| `--region` | `us-west-2` | AWS region |
| `--launch` | false | Auto-launch after configure |
| `--system-prompt` | — | Custom system prompt |
| `--idle-timeout` | 900 | Idle timeout (seconds) |
| `--max-lifetime` | 28800 | Max lifetime (seconds) |
| `--no-memory` | false | Disable AgentCore memory |
| `--no-otel` | false | Disable OpenTelemetry |
| `--env` | — | Custom env vars (repeatable) |
| `--force-rebuild` | false | Force rebuild deps |

---

## Unified Mesh Proxy

DevDuck auto-starts an AgentCore proxy on `ws://localhost:10000` that connects:

- **CLI DevDuck** (local terminal)
- **Browser clients** (mesh.html)
- **Deployed AgentCore agents** (cloud)

All visible as peers in the same mesh:

```python
# List all peers (local + cloud)
agentcore_proxy(action="status")

# Invoke a cloud agent from CLI
agentcore_invoke(agent_id="abc123", prompt="hello from CLI")
```
