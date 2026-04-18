# Self-Replication & Persistence

DevDuck can install itself — or independent copies of itself — as a **persistent OS service** that survives terminal close, auto-restarts on failure, and starts at boot.

Backed by **systemd** on Linux and **launchd** on macOS. Exposed as both a CLI subcommand (`devduck service …`) and an **agent tool** (`service(…)`), so your agent can literally replicate itself on command.

---

## Why

- **Persist listeners** (Telegram, Slack, WhatsApp) beyond a shell session
- **Keep schedulers alive** so cron-style jobs fire when you're not around
- **Fleet out** — spawn a devduck on every host over SSH, each with its own role and tools
- **Self-directed replication** — the agent decides when and where to copy itself based on a conversation

---

## Mesh by default

Every installed service automatically joins the **devduck mesh** via
[Zenoh P2P](zenoh.md):

- `DEVDUCK_ENABLE_ZENOH=true` — the service joins the mesh on boot
- `zenoh_peer` is spliced into `DEVDUCK_TOOLS` if you don't include it
- Port-binding servers (WebSocket, TCP, MCP, AgentCore proxy) are disabled
  by default so a fleet of services don't fight over ports
- Every incoming message (telegram, whatsapp, zenoh broadcast) goes
  through `DevDuck.__call__`, which injects the current ring context,
  peer list, and ambient state into the agent's prompt

The result: spawned services are **mesh-aware on every turn**. They know
who else is alive, what recent activity has happened across the fleet,
and can broadcast/direct-message peers without any extra configuration.

To opt out, override the flags in `--env`:

```bash
devduck service install --name solo --env DEVDUCK_ENABLE_ZENOH=false ...
```

---

## CLI

### Install locally (no sudo, user-level)

```bash
devduck service install \
  --name my-bot \
  --tools "devduck.tools:telegram,scheduler;strands_tools:shell" \
  --env TELEGRAM_BOT_TOKEN=... \
  --env AWS_BEARER_TOKEN_BEDROCK=... \
  --startup-prompt "Start the telegram listener. Stay alive."
```

After install:

```bash
systemctl --user status devduck-my-bot.service
journalctl --user -u devduck-my-bot -f   # or tail the log file directly
```

### Install remotely over SSH

```bash
devduck service install \
  --name worker1 \
  --ssh user@host.example.com \
  --tools "devduck.tools:scheduler,notify;strands_tools:shell,file_read" \
  --env AWS_BEARER_TOKEN_BEDROCK=... \
  --startup-prompt "You are worker1. Stay alive."
```

The remote host must have `devduck` installed (pipx/pip/uvx, any way). The tool:

1. SSHs in, resolves `$HOME` on the target
2. Writes env file, wrapper, and unit file in the right locations for the target's init system
3. Reloads systemd (or launchd) and starts the service

### Install system-wide (requires sudo)

```bash
sudo devduck service install --system --name fleet-agent --tools "..."
```

Linux: writes to `/etc/systemd/system/`. macOS: writes to `/Library/LaunchDaemons/`.

### Manage services

```bash
devduck service status    --name my-bot
devduck service logs      --name my-bot --lines 200 --follow
devduck service restart   --name my-bot
devduck service stop      --name my-bot
devduck service start     --name my-bot
devduck service enable    --name my-bot    # start at boot
devduck service disable   --name my-bot
devduck service uninstall --name my-bot
```

All actions accept `--ssh user@host` to operate on a remote host.

### Preview without installing

```bash
devduck service show --name my-bot --ssh user@host
```

Dry-runs the install and prints exactly what files would be written, including contents. Great for code review or debugging path issues.

---

## Agent tool

The `service` tool is loaded by default, so the agent can use it in any conversation:

```python
import devduck

devduck.ask(
    "Spawn a copy of yourself on ops@worker1 named 'pr-watcher' with "
    "use_github+scheduler+telegram. Pass through GITHUB_TOKEN and "
    "TELEGRAM_BOT_TOKEN from my env. Its job: poll my open PRs every "
    "5 min and notify me on telegram if any are waiting on me."
)
```

The agent translates that into a tool call:

```python
service(
    action="install",
    name="pr-watcher",
    ssh="ops@worker1",
    tools="devduck.tools:use_github,scheduler,telegram;strands_tools:shell",
    env_vars={"GITHUB_TOKEN": "...", "TELEGRAM_BOT_TOKEN": "..."},
    startup_prompt=(
        "Schedule a job: every 5 min, list my open PRs, and telegram "
        "me any that are waiting on review from me."
    ),
)
```

### Tool reference

```python
service(
    action: str,                       # install|uninstall|start|stop|restart|
                                       # status|enable|disable|logs|show
    name: str = "devduck",             # service instance name
    system: bool = False,              # system-wide vs user-level
    ssh: Optional[str] = None,         # user@host for remote ops

    # install-only
    model: Optional[str] = None,              # STRANDS_MODEL_ID override
    model_provider: Optional[str] = None,     # bedrock|anthropic|openai|…
    tools: Optional[str] = None,              # DEVDUCK_TOOLS config string
    system_prompt: Optional[str] = None,      # inline or "@/path/to/file"
    startup_prompt: Optional[str] = None,     # first ask() on boot
    mcp_servers: Optional[str] = None,        # MCP_SERVERS JSON
    env_vars: Optional[Dict[str, str]] = None,
    work_dir: Optional[str] = None,
    memory_max: str = "8G",
    restart_sec: int = 15,
    no_start: bool = False,

    # logs-only
    lines: int = 80,
    follow: bool = False,
) -> Dict[str, Any]
```

---

## What gets installed

### Linux (user-level)

| File         | Path                                            |
|--------------|-------------------------------------------------|
| systemd unit | `~/.config/systemd/user/devduck-<name>.service` |
| Env file     | `~/.config/devduck/devduck-<name>.env`          |
| Wrapper      | `~/.local/bin/devduck-<name>-agent`             |
| Log          | `~/.cache/devduck-<name>.log`                   |

### Linux (system-wide)

| File         | Path                                            |
|--------------|-------------------------------------------------|
| systemd unit | `/etc/systemd/system/devduck-<name>.service`    |
| Env file     | `/etc/devduck/devduck-<name>.env`               |
| Wrapper      | `/usr/local/bin/devduck-<name>-agent`           |
| Log          | `/var/log/devduck-<name>.log`                   |

### macOS (user-level)

| File   | Path                                                         |
|--------|--------------------------------------------------------------|
| Plist  | `~/Library/LaunchAgents/dev.devduck.<name>.plist`            |
| Env    | `~/Library/Application Support/devduck/devduck-<name>.env`   |
| Wrapper| `~/Library/Application Support/devduck/devduck-<name>-agent` |
| Log    | `~/Library/Logs/devduck-<name>.log`                          |

---

## How it works

### The wrapper script

Each service gets a small bash wrapper (`devduck-<name>-agent`) that:

1. Resolves the pipx/pip Python that has `devduck` installed
2. Self-heals the `pydantic-core` native binary mismatch that commonly breaks pipx installs
3. Sources the env file
4. Calls `python -c "import devduck; devduck.ask('<startup_prompt>')"` if a startup prompt was given
5. Parks in an idle loop (so systemd keeps the process alive for the scheduler/listeners)

### The unit file

```ini
[Unit]
Description=🦆 DevDuck Service (<name>)
After=network-online.target

[Service]
Type=simple
EnvironmentFile=%h/.config/devduck/devduck-<name>.env
ExecStart=%h/.local/bin/devduck-<name>-agent
Restart=always
RestartSec=15
MemoryMax=8G
StandardOutput=append:%h/.cache/devduck-<name>.log
StandardError=append:%h/.cache/devduck-<name>.log

[Install]
WantedBy=default.target
```

On macOS the equivalent launchd plist is used.

### Idempotency

Re-running `install` with the same `--name`:

- Overwrites the env file (picks up new tokens)
- Overwrites the unit/plist (picks up new tools, prompts, resource limits)
- Reloads systemd and restarts the service

Safe to wrap in config management (Ansible, etc.).

---

## Patterns

### One service per role

```bash
devduck service install --name telegram-bot  --tools "...,telegram,..." --env TELEGRAM_BOT_TOKEN=...
devduck service install --name slack-bot     --tools "...,slack,..."    --env SLACK_BOT_TOKEN=...
devduck service install --name pr-watcher    --tools "...,use_github,scheduler,..." --env GITHUB_TOKEN=...
```

Three independent services, three independent agents, each with just the tools and secrets it needs.

### Agent-directed fleet

```python
devduck.ask("""
I have 5 worker boxes (worker1..worker5 at 10.0.0.{41..45}).
Deploy a devduck 'probe' service on each, with just strands_tools:shell
loaded. Each probe should on boot run: uname -a && uptime && df -h, then
notify() the parent. Use my AWS_BEARER_TOKEN_BEDROCK for model access.
""")
```

The agent loops over hosts, calls `service(action="install", ssh=..., ...)` in parallel, and reports back.

### Progressive self-persistence

An agent running in a tmux can detect its own volatility and persist itself:

```python
# In the system prompt or a periodic check:
# "If you're running in a terminal and handling long-lived work
#  (scheduler jobs, listeners), call service(action='install', ...)
#  to move yourself into systemd so you survive terminal close."
```

---

## Troubleshooting

### Remote install fails with "devduck not found"

Install devduck on the target first:

```bash
ssh user@host 'pipx install devduck[all]'
```

### "Failed to connect to bus" on remote systemd user units

The target user needs a lingering session:

```bash
ssh user@host 'loginctl enable-linger'
```

### pydantic-core architecture mismatch after OS upgrade

The wrapper detects this and reinstalls it automatically. If it persists:

```bash
devduck service logs --name my-bot --lines 50
# Then manually:
ssh user@host '~/.local/share/pipx/venvs/devduck/bin/pip install --force-reinstall pydantic-core'
devduck service restart --name my-bot
```

### macOS: launchd job not starting

launchd needs the plist to be loaded into the current user's session. Log out/in once after first install, or:

```bash
launchctl unload ~/Library/LaunchAgents/dev.devduck.<name>.plist
launchctl load   ~/Library/LaunchAgents/dev.devduck.<name>.plist
```

---

## Security notes

- Env files are written with mode `0600` (user-only readable) to protect tokens
- Remote installs copy env files over SSH only — secrets never touch a git repo
- `--system` installs put the env file in `/etc/devduck/` with `root:root 0600`
- Wrappers are mode `0755` (executable, world-readable, but not writable)

If you rotate a secret, re-run `devduck service install` with the new value — it's idempotent.

---

## Related

- [Messaging](messaging.md) — Telegram/Slack/WhatsApp listeners are the classic use case
- [Scheduler](../api-reference.md#scheduler) — Cron jobs that actually fire, because the service stays alive
- [Ambient Mode](ambient-mode.md) — Background thinking, now with a background process
