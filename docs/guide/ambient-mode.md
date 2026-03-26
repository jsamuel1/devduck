# Ambient Mode

Background intelligence while you're away. DevDuck continues exploring, researching, and building.

---

## Two Operating Modes

| | Standard 🌙 | Autonomous 🚀 |
|--|-------------|----------------|
| **Trigger** | After idle (30s) | Immediate |
| **Max Iterations** | 3 | 100 |
| **Cooldown** | 60s | 10s |
| **Stops when** | Max iterations reached | `[AMBIENT_DONE]` signal or max iterations |
| **Cost** | Low | High |

---

## Quick Start

=== "Environment Variable"
    ```bash
    DEVDUCK_AMBIENT_MODE=true devduck
    ```

=== "REPL Commands"
    ```
    🦆 ambient     # Toggle standard mode
    🦆 auto        # Toggle autonomous mode
    ```

=== "Tool API"
    ```python
    ambient_mode(action="start")                    # Standard
    ambient_mode(action="start", autonomous=True)   # Autonomous
    ambient_mode(action="status")
    ambient_mode(action="configure", idle_threshold=60, max_iterations=5)
    ambient_mode(action="stop")
    ```

---

## How It Works

### Standard Mode

```
🦆 analyze the security of this codebase

[Agent responds with initial analysis]

[You go idle for 30 seconds...]

🌙 [ambient] Thinking... (iteration 1/3)
──────────────────────────────────────────────────
[Agent explores deeper — checks vulnerabilities, reviews deps...]
──────────────────────────────────────────────────
🌙 [ambient] Work stored. Will be injected into next query.

🦆 what did you find?
🌙 [ambient] Injecting background work into context...
[Response includes enriched findings from background work]
```

### Autonomous Mode

```
🦆 auto
🌙 Ambient mode started (AUTONOMOUS)

🦆 build a complete REST API for user management

🌙 [AUTONOMOUS] Thinking... (iteration 1/100)
[Creates project structure...]

🌙 [AUTONOMOUS] Thinking... (iteration 2/100)
[Implements routes...]

🌙 [AUTONOMOUS] Thinking... (iteration 3/100)
[Adds tests...]

...

🌙 [AUTONOMOUS] Agent signaled completion. Stopping.
```

The agent includes `[AMBIENT_DONE]` in its response to signal completion.

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DEVDUCK_AMBIENT_MODE` | `false` | Enable on startup |
| `DEVDUCK_AMBIENT_IDLE_SECONDS` | `30` | Seconds before ambient triggers |
| `DEVDUCK_AMBIENT_MAX_ITERATIONS` | `15` | Max standard iterations |
| `DEVDUCK_AMBIENT_COOLDOWN` | `60` | Seconds between standard runs |
| `DEVDUCK_AUTONOMOUS_COOLDOWN` | `10` | Seconds between autonomous runs |
| `DEVDUCK_AUTONOMOUS_MAX_ITERATIONS` | `100` | Max autonomous iterations |

---

## Key Behaviors

- **User typing interrupts** — Ambient work stops gracefully when you start typing
- **Results are injected** — Background findings are automatically prepended to your next query
- **Agent-safe** — Ambient mode waits if the agent is already executing
- **Completion signal** — Agent can say `[AMBIENT_DONE]`, `[TASK_COMPLETE]`, or `[NOTHING_MORE_TO_DO]` to stop autonomous mode
