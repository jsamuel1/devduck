# Background Tasks

Ambient mode, parallel tasks, and scheduled jobs.

---

## Ambient Mode — Think While Idle

```
🦆 ambient
🌙 Ambient mode enabled (standard)

🦆 analyze the security posture of this codebase

[Agent responds with initial findings]

[You go idle for 30 seconds...]

🌙 [ambient] Thinking... (iteration 1/3)
[Deeper analysis: checks dependencies, scans for CVEs...]
🌙 [ambient] Work stored.

🦆 what else did you find?
🌙 [ambient] Injecting background work into context...
[Enhanced response with background findings]
```

## Autonomous Mode — Work Until Done

```
🦆 auto
🌙 Autonomous mode started

🦆 build a complete CRUD API with tests

🌙 [AUTONOMOUS] Thinking... (iteration 1/100)
[Creates project structure...]

🌙 [AUTONOMOUS] Thinking... (iteration 2/100)
[Implements endpoints...]

... continues until agent says [AMBIENT_DONE] ...
```

## Parallel Background Tasks

```python
# Create parallel tasks
tasks(action="create", task_id="lint", prompt="Run linting on the codebase")
tasks(action="create", task_id="test", prompt="Run all tests")
tasks(action="create", task_id="docs", prompt="Generate API documentation")

# Check status
tasks(action="list")

# Get results
tasks(action="get_result", task_id="lint")
```

## Scheduled Jobs

```python
# Daily code review at 9am
scheduler(
    action="add",
    name="daily-review",
    schedule="0 9 * * *",
    prompt="Review new PRs on cagataycali/devduck and summarize findings"
)

# One-time deploy at specific time
scheduler(
    action="add",
    name="deploy",
    run_at="2026-03-27T15:00:00",
    prompt="Deploy the staging branch to production"
)

# List all jobs
scheduler(action="list")

# View execution history
scheduler(action="history")
```
