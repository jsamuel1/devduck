# Dynamic Tools

Load tools from Python packages, fetch from GitHub, or drop files in `./tools/`. No restart needed.

---

## Tool Configuration

Configure which tools load at startup via `DEVDUCK_TOOLS`:

```bash
# Format: package1:tool1,tool2;package2:tool3,tool4
export DEVDUCK_TOOLS="strands_tools:shell,editor;devduck.tools:system_prompt,websocket"
```

### Default Tools

```
devduck.tools:system_prompt,fetch_github_tool,manage_tools,manage_messages,
              tasks,websocket,zenoh_peer,ambient_mode,agentcore_proxy
strands_tools:shell
```

---

## manage_tools API

Runtime tool management — list, add, remove, create, fetch, or discover tools without restarting.

| Action | Description | Key Parameters |
|--------|-------------|----------------|
| `list` | List all loaded tools | — |
| `add` | Add tools from package or file | `tools` |
| `remove` | Remove tools by name | `name` |
| `create` | Create a tool from code | `code` |
| `fetch` | Fetch from GitHub URL | `url` |
| `discover` | Discover tools in a module | `tools`, `verbose` |
| `sandbox` | Validate code before loading | `code` |

### Examples

```python
# List all tools
manage_tools(action="list")

# Add tools from a package
manage_tools(action="add", tools="strands_tools.calculator")

# Add from file path
manage_tools(action="add", tools="./tools/my_tool.py")

# Create a tool at runtime
manage_tools(
    action="create",
    code='''
    from strands import tool

    @tool
    def greet(name: str) -> str:
        """Greet someone by name."""
        return f"Hello, {name}!"
    '''
)

# Fetch from GitHub
manage_tools(
    action="fetch",
    url="https://github.com/cagataycali/devduck/blob/main/devduck/tools/scraper.py"
)

# Discover available tools in a module
manage_tools(action="discover", tools="strands_tools", verbose=True)
```

---

## Fetch from GitHub

Download and load tools directly from GitHub repositories:

```python
manage_tools(
    action="fetch",
    url="https://github.com/owner/repo/blob/main/tools/my_tool.py"
)
```

Supported URL formats:

- `https://github.com/owner/repo/blob/main/tools/my_tool.py`
- `https://github.com/owner/repo/tree/main/tools/my_tool.py`
- `https://raw.githubusercontent.com/owner/repo/main/tools/my_tool.py`

---

## Hot Directory Loading

Drop `.py` files in `./tools/` — they're loaded automatically:

```python
# ./tools/weather.py
from strands import tool
import requests

@tool
def weather(city: str) -> str:
    """Get weather for a city."""
    return requests.get(f"https://wttr.in/{city}?format=%C+%t").text
```

!!! tip "No restart needed"
    Tools from the `./tools/` directory are auto-loaded by the Strands Agent SDK when `DEVDUCK_LOAD_TOOLS_FROM_DIR=true` (default).

---

## Available Tool Packages

### 🦆 DevDuck Core Tools

| Tool | Description |
|------|-------------|
| `system_prompt` | View/update system prompt, GitHub sync |
| `manage_tools` | Runtime tool management |
| `manage_messages` | Conversation history management |
| `websocket` | WebSocket server |
| `zenoh_peer` | P2P auto-discovery networking |
| `agentcore_proxy` | Unified mesh relay |
| `tasks` | Background parallel agent tasks |
| `scheduler` | Cron and one-time job scheduling |
| `telegram` | Telegram bot integration |
| `slack` | Slack integration |
| `speech_to_speech` | Real-time voice (Nova Sonic, OpenAI, Gemini) |
| `use_mac` | Unified macOS control |
| `apple_notes` | Apple Notes management |
| `scraper` | Web scraping |
| `lsp` | Language Server Protocol diagnostics |

### ⚡ Strands Core Tools

| Tool | Description |
|------|-------------|
| `shell` | Execute shell commands |
| `editor` | File editing (str_replace, create, insert) |
| `file_read` | Read files with search |
| `file_write` | Write files |
| `retrieve` | Knowledge base RAG |
| `use_agent` | Spawn sub-agents |
| `calculator` | Math operations |
| `use_computer` | Mouse/keyboard/screenshot control |

### 🎮 Strands Fun Tools

| Tool | Description |
|------|-------------|
| `clipboard` | System clipboard access |
| `screen_reader` | Screen content reading |
| `cursor` | Mouse control |
| `listen` | Speech-to-text with Whisper |
| `yolo_vision` | YOLO object detection |
