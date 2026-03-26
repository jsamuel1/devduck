# API Reference

## Python API

### Module-Level Functions

```python
import devduck

# Direct call (module is callable)
devduck("your query")

# Helper functions
from devduck import ask, status, restart, hot_reload

result = ask("analyze this code")
info = status()
restart()
hot_reload()
```

### Session Recording API

```python
from devduck import (
    start_recording,
    stop_recording,
    load_session,
    resume_session,
    list_sessions,
)

# Record
recorder = start_recording(session_id="my-session")
export_path = stop_recording()

# Load and replay
session = load_session("session.zip")
print(session.events)
print(session.snapshots)

# Resume
result = resume_session("session.zip", new_query="continue")
result = resume_session("session.zip", snapshot_id=2)

# List
sessions = list_sessions()
```

### DevDuck Class

```python
from devduck import devduck

# The auto-initialized instance
devduck("query")
devduck.status()
devduck.restart()
devduck.agent  # Strands Agent instance
devduck.model  # Current model name
devduck.tools  # Loaded tools list
devduck.ambient  # AmbientMode instance (if enabled)
```

---

## CLI Reference

```bash
devduck [query]              # Interactive REPL or one-shot
devduck --tui                # Multi-conversation TUI
devduck --mcp                # MCP stdio mode
devduck --record             # Enable session recording
devduck --resume FILE        # Resume from session
devduck --snapshot ID        # Specific snapshot (with --resume)

# AgentCore
devduck deploy [options]     # Deploy to AgentCore
devduck list [--region]      # List deployed agents
devduck status [--name]      # Check agent status
devduck invoke PROMPT [opts] # Invoke deployed agent
```

---

## Tool Quick Reference

### Core Tools

| Tool | Key Actions |
|------|-------------|
| `shell(command)` | Execute shell commands |
| `editor(command, path, ...)` | File editing |
| `file_read(path, mode)` | Read files |
| `file_write(path, content)` | Write files |
| `use_github(query, variables)` | GitHub GraphQL API |
| `use_agent(prompt, system_prompt, ...)` | Spawn sub-agents |
| `manage_tools(action, ...)` | Runtime tool management |
| `manage_messages(action, ...)` | Conversation history |

### DevDuck Tools

| Tool | Key Actions |
|------|-------------|
| `system_prompt(action, ...)` | View/update system prompt |
| `websocket(action, ...)` | WebSocket server |
| `zenoh_peer(action, ...)` | P2P networking |
| `agentcore_proxy(action, ...)` | Mesh relay |
| `tasks(action, prompt, ...)` | Background tasks |
| `scheduler(action, name, ...)` | Cron jobs |
| `session_recorder(action, ...)` | Session recording |
| `ambient_mode(action, ...)` | Background thinking |
| `sqlite_memory(action, ...)` | Persistent memory |
| `telegram(action, ...)` | Telegram bot |
| `dialog(dialog_type, text, ...)` | Interactive dialogs |
| `use_computer(action, ...)` | Mouse/keyboard/screenshots |
| `listen(action, ...)` | Speech-to-text |
| `retrieve(text, ...)` | Knowledge base RAG |
| `store_in_kb(content, ...)` | Knowledge base storage |

---

## Environment Variables

### Model

| Variable | Description |
|----------|-------------|
| `MODEL_PROVIDER` | Force model provider |
| `STRANDS_MODEL_ID` | Specific model ID |
| `STRANDS_MAX_TOKENS` | Max tokens (default: 60000) |
| `STRANDS_TEMPERATURE` | Temperature (default: 1.0) |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `GOOGLE_API_KEY` | Gemini API key |
| `OLLAMA_HOST` | Ollama host URL |

### Servers

| Variable | Default | Description |
|----------|---------|-------------|
| `DEVDUCK_ENABLE_WS` | `true` | WebSocket server |
| `DEVDUCK_WS_PORT` | `10001` | WebSocket port |
| `DEVDUCK_ENABLE_TCP` | `false` | TCP server |
| `DEVDUCK_TCP_PORT` | `10002` | TCP port |
| `DEVDUCK_ENABLE_MCP` | `false` | MCP HTTP server |
| `DEVDUCK_MCP_PORT` | `10003` | MCP port |
| `DEVDUCK_ENABLE_ZENOH` | `true` | Zenoh P2P |
| `DEVDUCK_ENABLE_AGENTCORE_PROXY` | `true` | Mesh relay |
| `DEVDUCK_AGENTCORE_PROXY_PORT` | `10000` | Proxy port |

### Features

| Variable | Default | Description |
|----------|---------|-------------|
| `DEVDUCK_TOOLS` | core set | Tool configuration |
| `DEVDUCK_AMBIENT_MODE` | `false` | Ambient mode |
| `DEVDUCK_KNOWLEDGE_BASE_ID` | — | Auto RAG |
| `DEVDUCK_LOAD_TOOLS_FROM_DIR` | `true` | Hot-load ./tools/ |
| `DEVDUCK_ASCIINEMA` | `false` | Record .cast |
| `DEVDUCK_AUTO_START_SERVERS` | `true` | Auto-start servers |
| `MCP_SERVERS` | — | MCP server config (JSON) |
| `BYPASS_TOOL_CONSENT` | `true` | Skip tool confirmations |
