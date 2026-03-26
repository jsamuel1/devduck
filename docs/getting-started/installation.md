# Installation

## Quick Install

=== "pipx (recommended)"
    ```bash
    pipx install devduck
    ```

=== "pip"
    ```bash
    pip install devduck
    ```

=== "From source"
    ```bash
    git clone git@github.com:cagataycali/devduck.git
    cd devduck
    python3.13 -m venv .venv && source .venv/bin/activate
    pip install -e .
    ```

=== "Docker"
    ```bash
    docker run -it --env ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY cagataycali/devduck
    ```

## Requirements

- **Python** 3.10–3.13
- **Model provider** — at least one of:
    - AWS credentials (Bedrock)
    - `ANTHROPIC_API_KEY`
    - `OPENAI_API_KEY`
    - `GOOGLE_API_KEY` (Gemini)
    - Ollama running locally (zero-config fallback)

## Verify Installation

```bash
devduck --help
```

```
🦆 DevDuck - Extreme minimalist self-adapting agent

positional arguments:
  query                 Query to send to the agent

options:
  --tui                 Launch multi-conversation TUI
  --mcp                 Start MCP server in stdio mode
  --record              Enable session recording
  --resume SESSION_FILE Resume from recorded session
```

## Model Setup

DevDuck auto-detects your model provider from environment variables:

```bash
# Pick one (or let DevDuck auto-detect):
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
export GOOGLE_API_KEY=...

# Or force a specific provider:
export MODEL_PROVIDER=bedrock
export STRANDS_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0
```

→ See [Models](../guide/models.md) for all 14 supported providers.

## Optional Dependencies

```bash
# For TUI mode
pip install textual

# For MCP integration
pip install mcp

# For Apple Silicon local models
pip install strands-mlx

# For extended tool ecosystem
pip install strands-tools strands-tools-fun
```

## Next Steps

→ **[Quickstart](quickstart.md)** — Your first DevDuck session
