# Session Recording

Time-travel debugger for AI agents. Capture, replay, and resume.

---

## Three-Layer Capture

| Layer | Events | Examples |
|-------|--------|----------|
| 💾 **sys** | OS-level events | `file.open`, `http.get` |
| 🔧 **tool** | Tool invocations | `tool.call`, `tool.result` |
| 🤖 **agent** | Agent behavior | `message`, `snapshot.created` |

---

## Quick Start

=== "Command Line"
    ```bash
    # Start with recording
    devduck --record

    # Record a one-shot query
    devduck --record "create a web scraper"

    # Resume from session
    devduck --resume session.zip

    # Resume specific snapshot
    devduck --resume session.zip --snapshot 2

    # Resume and continue
    devduck --resume session.zip "continue from here"
    ```

=== "REPL"
    ```
    🦆 record          # Start recording
    ... do your work ...
    🦆 record          # Stop and export ZIP
    ```

=== "Tool API"
    ```python
    # Start recording
    session_recorder(action="start")

    # Create state snapshot
    session_recorder(action="snapshot", description="after API setup")

    # Check status
    session_recorder(action="status")

    # Export without stopping
    session_recorder(action="export", output_path="~/Desktop/checkpoint.zip")

    # Stop and export
    session_recorder(action="stop")

    # List recordings
    session_recorder(action="list")
    ```

---

## Full State Resume

Snapshots capture your **complete conversation state**, allowing you to resume exactly where you left off.

### What's Captured

- ✅ Full `agent.messages` array
- ✅ System prompt
- ✅ Working directory
- ✅ Loaded tools list
- ✅ Last query and result
- ✅ Model information
- ✅ Environment variables (redacted)

### Resume Workflow

```python
from devduck import load_session

# Load a session
session = load_session("~/Desktop/session-20260202.zip")
print(session)  # LoadedSession(events=42, snapshots=3, duration=124.5s)

# See what happened
tool_events = session.get_events_by_layer("tool")

# Resume from a snapshot (restores agent.messages!)
result = session.resume_from_snapshot(2, agent=my_agent)
print(f"Restored {result['messages_restored']} messages")

# Resume and continue with new query
result = session.resume_and_continue(2, "what was I working on?", agent=my_agent)
```

---

## Export Format

Sessions export as ZIP files containing:

| File | Format | Content |
|------|--------|---------|
| `events.jsonl` | JSON Lines | All recorded events |
| `snapshots.json` | JSON | State snapshots |
| `metadata.json` | JSON | Session info |
| `session.pkl` | Pickle/Dill | Serialized state for replay |

Recordings are saved to `/tmp/devduck/recordings/`.

---

## Python API

```python
from devduck import (
    start_recording,
    stop_recording,
    load_session,
    resume_session,
    list_sessions,
)

# Start recording
recorder = start_recording(session_id="my-session")

# ... do work ...

# Stop and export
export_path = stop_recording()

# List all recordings
sessions = list_sessions()

# Resume a session
result = resume_session("session.zip", new_query="continue")
```
