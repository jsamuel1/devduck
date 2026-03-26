# CLI Workflows

Common patterns for daily DevDuck usage.

---

## Code Review

```
🦆 review the last 3 commits for security issues
```

DevDuck runs `git log`, reads the diffs, analyzes for vulnerabilities, and reports findings.

## Project Scaffolding

```
🦆 create a FastAPI project with user auth, PostgreSQL, and Docker
```

Creates directory structure, writes all files, sets up Docker Compose, and runs initial tests.

## Bug Investigation

```bash
devduck "this test is failing, fix it" < test_output.log
```

Reads the error, finds the source file, applies the fix, and re-runs the test.

## File Operations

```
🦆 find all TODO comments in this repo and create GitHub issues for each
```

Combines `file_read` (search mode), `use_github` (create issues), and summarizes what was created.

## Shell Automation

```
🦆 !docker ps
🦆 the api container keeps crashing, investigate and fix
```

Prefix `!` for direct shell. Then natural language to investigate logs, edit configs, and restart.

## Session Recording

```
🦆 record
🦆 set up the CI pipeline for this project
... agent creates .github/workflows, configures tests, etc. ...
🦆 record
🎬 Session exported: /tmp/devduck/recordings/session-20260326.zip
```

Later, resume:

```bash
devduck --resume session-20260326.zip "add deployment stage"
```

## Scheduled Tasks

```
🦆 schedule a daily code review of new PRs at 9am
```

Uses the `scheduler` tool to create a cron job that runs automatically.
