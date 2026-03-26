# System Prompt

View, update, and sync your agent's personality. Self-improvement across sessions.

---

## Actions

| Action | Description | Parameters |
|--------|-------------|------------|
| `view` | View current system prompt | — |
| `update` | Replace the system prompt | `prompt`, `repository` (optional) |
| `add_context` | Append without replacing | `context` |
| `reset` | Reset to default | — |
| `get_github_context` | Get GitHub event context | — |

---

## Basic Usage

```python
# View current prompt
system_prompt(action="view")

# Update locally (saves to env var + .prompt file)
system_prompt(
    action="update",
    prompt="You are a specialized Python developer..."
)

# Add context without replacing
system_prompt(
    action="add_context",
    context="When working with async code, always use asyncio.gather."
)
```

---

## GitHub Repository Sync

Persist system prompt changes across deployments by syncing to GitHub repository variables:

```python
# Update and sync to GitHub
system_prompt(
    action="update",
    prompt="You are DevDuck, an expert AI developer...",
    repository="cagataycali/devduck"
)

# Use custom variable name
system_prompt(
    action="update",
    prompt="Specialized for data analysis...",
    repository="owner/repo",
    variable_name="DATA_AGENT_PROMPT"
)
```

### What Gets Updated

1. ✅ Environment variable (`SYSTEM_PROMPT`)
2. ✅ Local `.prompt` file
3. ✅ GitHub repository variable (if `repository` specified)

---

## Self-Improvement Pattern

When DevDuck discovers valuable patterns during conversations:

```python
# Step 1: Identify new insight
insight = "Always validate JSON before parsing to avoid crashes"

# Step 2: Add to system prompt
system_prompt(action="add_context", context=insight)

# Step 3: Sync to GitHub for persistence
system_prompt(
    action="update",
    prompt=current_prompt + "\n" + insight,
    repository="cagataycali/devduck"
)
```

!!! tip "Persistent Learning"
    New learnings persist across sessions via the `SYSTEM_PROMPT` environment variable and GitHub repository variables.

---

## AGENTS.md

DevDuck automatically loads `AGENTS.md` from the current working directory and injects it into the system prompt. This file describes project-specific context, conventions, and instructions.

```markdown
# AGENTS.md — My Project

## Architecture
- FastAPI backend in /api
- React frontend in /web

## Conventions
- Use pytest for all tests
- Follow Google Python Style Guide
```
