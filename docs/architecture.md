# Architecture

DevDuck is a single `DevDuck` class in `__init__.py` that auto-initializes on import.

---

## File Structure

```
devduck/
├── __init__.py              # Core: DevDuck class, REPL, CLI, session recording, ambient mode
├── tui.py                   # Multi-conversation Textual TUI
├── landing.py               # Rich landing screen for REPL
├── callback_handler.py      # Streaming callback handler for CLI
├── asciinema_callback_handler.py  # .cast file recording
├── agentcore_handler.py     # HTTP handler for AgentCore deployment
├── tools/                   # 60+ built-in tools
│   ├── system_prompt.py     # Self-improvement via prompt management
│   ├── manage_tools.py      # Runtime tool add/remove/create/fetch
│   ├── manage_messages.py   # Conversation history management
│   ├── websocket.py         # WebSocket server
│   ├── zenoh_peer.py        # P2P auto-discovery networking
│   ├── agentcore_proxy.py   # Unified mesh relay
│   ├── unified_mesh.py      # Ring context shared memory
│   ├── tasks.py             # Background parallel agent tasks
│   ├── scheduler.py         # Cron and one-time job scheduling
│   ├── telegram.py          # Telegram bot integration
│   ├── slack.py             # Slack integration
│   ├── speech_to_speech.py  # Real-time voice
│   ├── lsp.py               # Language Server Protocol
│   ├── use_mac.py           # Unified macOS control
│   └── ...                  # 40+ more tools
└── tools/ (hot-reload)      # ./tools/*.py auto-loaded at runtime
```

---

## Core Design Patterns

### Self-Awareness

The system prompt includes the agent's **complete source code** via `get_own_source_code()`. This means the agent can inspect its own implementation to answer questions accurately.

### Self-Healing

`_self_heal(error)` retries initialization on failure (max 2 attempts). Context window overflow is auto-detected — history is cleared and the query is retried.

### Hot-Reload

A background `_file_watcher_thread` monitors `__init__.py` for changes. On detection, `os.execv()` restarts the process. If the agent is executing, reload is deferred until completion.

### Dynamic Tool Loading

Tools are configured via `DEVDUCK_TOOLS` env var. Additional tools can be loaded at runtime via `manage_tools()` or by dropping `.py` files in `./tools/`.

---

## Initialization Flow

```mermaid
flowchart TD
    A["import devduck"] --> B["DevDuck.__init__()"]
    B --> C["Load tools from DEVDUCK_TOOLS"]
    C --> D["Load MCP servers"]
    D --> E["Select model (auto-detect)"]
    E --> F["Create Strands Agent"]
    F --> G["Start servers (WS, Zenoh, Proxy)"]
    G --> H["Start file watcher"]
    H --> I["Start ambient mode (if enabled)"]
    I --> J["Ready"]
```

---

## Query Flow

```mermaid
flowchart TD
    A["devduck(query)"] --> B{"Recording active?"}
    B -->|Yes| C["Record user message"]
    B -->|No| D["Check ambient results"]
    C --> D
    D --> E{"KB configured?"}
    E -->|Yes| F["Retrieve from KB"]
    E -->|No| G["Inject dynamic context"]
    F --> G
    G --> H["Run agent"]
    H --> I{"Recording?"}
    I -->|Yes| J["Record response + snapshot"]
    I -->|No| K["Store to KB"]
    J --> K
    K --> L["Push to mesh ring"]
    L --> M["Return result"]
```

---

## Module Callable Pattern

The module itself is callable — no need to access the `devduck` instance:

```python
import devduck
devduck("query")  # Works because of CallableModule metaclass
```

This is achieved by replacing `sys.modules[__name__].__class__` with a custom `CallableModule` that defines `__call__`.

---

## State Management

| Data | Location |
|------|----------|
| Conversation history | `agent.messages` (in-memory) |
| Shell history | `~/.devduck_history` |
| Logs | `/tmp/devduck/logs/devduck.log` |
| Session recordings | `/tmp/devduck/recordings/` |
| Scheduler jobs | Persisted to disk |
| SQLite memory | Default path |

---

## Framework

Built on [Strands Agents SDK](https://strandsagents.com) — a model-agnostic agent framework with tool use, streaming, and multi-provider support.
