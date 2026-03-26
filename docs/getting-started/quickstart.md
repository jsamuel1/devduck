# Quickstart

Get productive with DevDuck in 2 minutes.

---

## Interactive REPL

```bash
devduck
```

```
🦆 DevDuck
📝 Logs: /tmp/devduck/logs
🦆 ✓ Zenoh peer: hostname-abc123
🦆 ✓ WebSocket server: localhost:10001

🦆 create a python web server with FastAPI
```

Type your query and DevDuck handles the rest — writing files, running commands, installing packages.

## One-Shot Mode

```bash
devduck "explain this error" < error.log
devduck "create a REST API for user management"
devduck "review the last 5 commits on this repo"
```

## Multi-Conversation TUI

```bash
devduck --tui
```

Run multiple conversations concurrently in a Textual-based terminal UI. Each conversation has its own panel with streaming markdown output.

## Python API

```python
import devduck

# Direct call
devduck("analyze this code and suggest improvements")

# Or use the ask helper
from devduck import ask
result = ask("what files are in this directory?")
print(result)
```

---

## Shell Commands

Prefix with `!` to run shell commands directly:

```
🦆 !ls -la
🦆 !git status
🦆 !docker ps
```

---

## Key Workflows

### Load a Tool at Runtime

```
🦆 load the clipboard tool from strands-fun-tools
```

DevDuck will install the package and load the tool — no restart needed.

### Fetch a Tool from GitHub

```
🦆 fetch the scraper tool from https://github.com/cagataycali/devduck/blob/main/devduck/tools/scraper.py
```

### Record a Session

```
🦆 record
... do your work ...
🦆 record
🎬 Session exported: /tmp/devduck/recordings/session-20260326.zip
```

### Toggle Ambient Mode

```
🦆 ambient       # standard — thinks when you're idle
🦆 auto          # autonomous — works until [AMBIENT_DONE]
```

---

## Configuration

Key environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_PROVIDER` | auto-detect | Force model provider |
| `STRANDS_MODEL_ID` | provider default | Specific model ID |
| `DEVDUCK_TOOLS` | core set | Tool configuration |
| `DEVDUCK_AMBIENT_MODE` | `false` | Enable ambient mode |
| `DEVDUCK_ENABLE_WS` | `true` | WebSocket server |
| `DEVDUCK_ENABLE_ZENOH` | `true` | Zenoh P2P |
| `MCP_SERVERS` | — | MCP server config (JSON) |

---

## Next Steps

- [Hot Reload](../guide/hot-reload.md) — Edit code while the agent runs
- [Tools](../guide/tools.md) — Load, create, and manage tools
- [Models](../guide/models.md) — All 14 supported providers
- [Zenoh P2P](../guide/zenoh.md) — Multi-instance networking
