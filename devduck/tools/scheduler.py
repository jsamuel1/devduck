"""⏰ Scheduler tool for DevDuck.

Cron-based and one-time job scheduling with disk persistence.
Each DevDuck session has its own scheduler. Jobs survive restarts.

Examples:
    scheduler(action="add", name="backup", schedule="0 */6 * * *", prompt="Run backup check")
    scheduler(action="add", name="remind", run_at="2026-03-04T15:00:00", prompt="Remind me about the meeting")
    scheduler(action="list")
    scheduler(action="remove", name="backup")
    scheduler(action="start")
    scheduler(action="stop")
    scheduler(action="status")
    scheduler(action="history", name="backup")
"""

import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from strands import tool

logger = logging.getLogger(__name__)

# Persistence
SCHEDULER_DIR = Path.home() / ".devduck" / "scheduler"
SCHEDULER_DIR.mkdir(parents=True, exist_ok=True)
JOBS_FILE = SCHEDULER_DIR / "jobs.json"
HISTORY_FILE = SCHEDULER_DIR / "history.json"

# Runtime state
_state: Dict[str, Any] = {
    "running": False,
    "thread": None,
    "stop_event": None,
    "jobs": {},
    "agent": None,
}


def _load_jobs() -> Dict[str, dict]:
    if JOBS_FILE.exists():
        try:
            return json.loads(JOBS_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_jobs(jobs: dict):
    JOBS_FILE.write_text(json.dumps(jobs, indent=2, default=str))


def _load_history() -> List[dict]:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())
        except Exception:
            pass
    return []


def _save_history(history: list):
    # Keep last 500 entries
    HISTORY_FILE.write_text(json.dumps(history[-500:], indent=2, default=str))


def _parse_cron(cron_expr: str) -> Optional[dict]:
    """Parse simple cron expression: min hour dom month dow."""
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        return None
    fields = ["minute", "hour", "dom", "month", "dow"]
    return {f: p for f, p in zip(fields, parts)}


def _cron_matches(cron: dict, dt: datetime) -> bool:
    """Check if datetime matches cron expression."""

    def _match_field(pattern: str, value: int, max_val: int) -> bool:
        if pattern == "*":
            return True
        for part in pattern.split(","):
            if "/" in part:
                base, step = part.split("/", 1)
                base_val = 0 if base == "*" else int(base)
                step_val = int(step)
                if (
                    step_val > 0
                    and (value - base_val) % step_val == 0
                    and value >= base_val
                ):
                    return True
            elif "-" in part:
                lo, hi = part.split("-", 1)
                if int(lo) <= value <= int(hi):
                    return True
            else:
                if int(part) == value:
                    return True
        return False

    return (
        _match_field(cron["minute"], dt.minute, 59)
        and _match_field(cron["hour"], dt.hour, 23)
        and _match_field(cron["dom"], dt.day, 31)
        and _match_field(cron["month"], dt.month, 12)
        and _match_field(cron["dow"], dt.weekday(), 6)  # 0=Monday
    )


def _execute_job(job: dict, agent: Any):
    """Execute a scheduled job."""
    name = job["name"]
    prompt = job["prompt"]
    system_prompt = job.get(
        "system_prompt", "You are executing a scheduled task. Be concise and efficient."
    )

    logger.info(f"⏰ Executing scheduled job: {name}")
    print(f"\n⏰ [scheduler] Running '{name}'...")

    record = {
        "name": name,
        "started_at": datetime.now().isoformat(),
        "prompt": prompt[:200],
        "status": "running",
    }

    try:
        if agent and hasattr(agent, "tool"):
            result = agent.tool.use_agent(
                prompt=prompt,
                system_prompt=system_prompt,
                record_direct_tool_call=False,
                agent=agent,
            )
            result_text = result.get("content", [{}])[0].get("text", "No response")
            record["result"] = result_text[:2000]
            record["status"] = "success"
            print(f"⏰ [scheduler] '{name}' completed.")
        else:
            record["result"] = "No agent available"
            record["status"] = "skipped"
    except Exception as e:
        record["result"] = str(e)
        record["status"] = "error"
        logger.error(f"Scheduler job '{name}' failed: {e}")
        print(f"⏰ [scheduler] '{name}' failed: {e}")

    record["finished_at"] = datetime.now().isoformat()

    # Save history
    history = _load_history()
    history.append(record)
    _save_history(history)


def _scheduler_loop(stop_event: threading.Event):
    """Main scheduler loop - checks every 30 seconds."""
    last_check_minute = -1

    while not stop_event.is_set():
        try:
            now = datetime.now()

            # Only check once per minute
            if now.minute == last_check_minute:
                stop_event.wait(10)
                continue
            last_check_minute = now.minute

            jobs = _load_jobs()
            agent = _state.get("agent")

            for name, job in list(jobs.items()):
                if not job.get("enabled", True):
                    continue

                # One-time job
                if job.get("run_at"):
                    run_at = datetime.fromisoformat(job["run_at"])
                    if now >= run_at and not job.get("executed"):
                        _execute_job(job, agent)
                        job["executed"] = True
                        job["last_run"] = now.isoformat()
                        _save_jobs(jobs)
                    continue

                # Cron job
                cron = job.get("cron_parsed")
                if cron and _cron_matches(cron, now):
                    # Prevent double execution in same minute
                    last_run = job.get("last_run")
                    if last_run:
                        lr = datetime.fromisoformat(last_run)
                        if (
                            lr.minute == now.minute
                            and lr.hour == now.hour
                            and lr.date() == now.date()
                        ):
                            continue

                    _execute_job(job, agent)
                    job["last_run"] = now.isoformat()
                    job["run_count"] = job.get("run_count", 0) + 1
                    _save_jobs(jobs)

        except Exception as e:
            logger.error(f"Scheduler loop error: {e}")

        stop_event.wait(10)

    logger.info("Scheduler loop stopped")


@tool
def scheduler(
    action: str,
    name: Optional[str] = None,
    schedule: Optional[str] = None,
    run_at: Optional[str] = None,
    prompt: Optional[str] = None,
    system_prompt: Optional[str] = None,
    enabled: bool = True,
    agent: Any = None,
) -> Dict[str, Any]:
    """⏰ Job scheduler - cron and one-time tasks with persistence.

    Args:
        action: Action to perform:
            - start: Start the scheduler daemon
            - stop: Stop the scheduler
            - status: Show scheduler status
            - add: Add a new job (requires name + schedule/run_at + prompt)
            - remove: Remove a job (requires name)
            - list: List all jobs
            - enable: Enable a job (requires name)
            - disable: Disable a job (requires name)
            - history: Show execution history (optional: name to filter)
            - run_now: Execute a job immediately (requires name)
            - clear_history: Clear execution history
        name: Job name (unique identifier)
        schedule: Cron expression (e.g., "*/5 * * * *" = every 5 min, "0 9 * * 1" = Mon 9am)
        run_at: ISO datetime for one-time job (e.g., "2026-03-04T15:00:00")
        prompt: Agent prompt to execute when job triggers
        system_prompt: Custom system prompt for the job agent
        enabled: Whether the job is enabled (default: True)
        agent: Parent agent instance

    Returns:
        Dict with status and content
    """
    action = action.lower()

    if action == "start":
        if _state["running"]:
            return {
                "status": "success",
                "content": [{"text": "⏰ Scheduler already running."}],
            }

        _state["agent"] = agent
        stop_event = threading.Event()
        _state["stop_event"] = stop_event
        _state["running"] = True

        t = threading.Thread(target=_scheduler_loop, args=(stop_event,), daemon=True)
        t.start()
        _state["thread"] = t

        jobs = _load_jobs()
        return {
            "status": "success",
            "content": [{"text": f"⏰ Scheduler started. {len(jobs)} jobs loaded."}],
        }

    elif action == "stop":
        if not _state["running"]:
            return {
                "status": "success",
                "content": [{"text": "Scheduler not running."}],
            }

        _state["stop_event"].set()
        _state["running"] = False
        return {"status": "success", "content": [{"text": "⏰ Scheduler stopped."}]}

    elif action == "status":
        jobs = _load_jobs()
        active = sum(1 for j in jobs.values() if j.get("enabled", True))
        return {
            "status": "success",
            "content": [
                {
                    "text": f"⏰ Scheduler: {'running' if _state['running'] else 'stopped'} | Jobs: {len(jobs)} ({active} active)"
                }
            ],
        }

    elif action == "add":
        if not name or not prompt:
            return {
                "status": "error",
                "content": [{"text": "name and prompt required"}],
            }
        if not schedule and not run_at:
            return {
                "status": "error",
                "content": [{"text": "schedule (cron) or run_at (datetime) required"}],
            }

        jobs = _load_jobs()
        job = {
            "name": name,
            "prompt": prompt,
            "system_prompt": system_prompt,
            "enabled": enabled,
            "created_at": datetime.now().isoformat(),
            "run_count": 0,
        }

        if schedule:
            cron = _parse_cron(schedule)
            if not cron:
                return {
                    "status": "error",
                    "content": [
                        {
                            "text": f"Invalid cron: {schedule}. Format: min hour dom month dow"
                        }
                    ],
                }
            job["schedule"] = schedule
            job["cron_parsed"] = cron
            job["type"] = "cron"
        else:
            try:
                datetime.fromisoformat(run_at)
            except ValueError:
                return {
                    "status": "error",
                    "content": [
                        {"text": f"Invalid datetime: {run_at}. Use ISO format."}
                    ],
                }
            job["run_at"] = run_at
            job["type"] = "once"
            job["executed"] = False

        jobs[name] = job
        _save_jobs(jobs)

        sched_info = schedule or f"at {run_at}"
        return {
            "status": "success",
            "content": [{"text": f"⏰ Job '{name}' added ({sched_info})"}],
        }

    elif action == "remove":
        if not name:
            return {"status": "error", "content": [{"text": "name required"}]}
        jobs = _load_jobs()
        if name not in jobs:
            return {"status": "error", "content": [{"text": f"Job '{name}' not found"}]}
        del jobs[name]
        _save_jobs(jobs)
        return {"status": "success", "content": [{"text": f"⏰ Job '{name}' removed"}]}

    elif action == "list":
        jobs = _load_jobs()
        if not jobs:
            return {"status": "success", "content": [{"text": "No scheduled jobs."}]}

        lines = [f"⏰ Scheduled Jobs ({len(jobs)}):\n"]
        for n, j in jobs.items():
            status = "✅" if j.get("enabled", True) else "⏸️"
            jtype = j.get("type", "?")
            sched = j.get("schedule") or f"at {j.get('run_at', '?')}"
            runs = j.get("run_count", 0)
            last = j.get("last_run", "never")[:19] if j.get("last_run") else "never"
            prompt_preview = j.get("prompt", "")[:80]
            lines.append(
                f"  {status} **{n}** [{jtype}] {sched} | runs: {runs} | last: {last}\n     → {prompt_preview}"
            )

        return {"status": "success", "content": [{"text": "\n".join(lines)}]}

    elif action in ("enable", "disable"):
        if not name:
            return {"status": "error", "content": [{"text": "name required"}]}
        jobs = _load_jobs()
        if name not in jobs:
            return {"status": "error", "content": [{"text": f"Job '{name}' not found"}]}
        jobs[name]["enabled"] = action == "enable"
        _save_jobs(jobs)
        return {
            "status": "success",
            "content": [
                {
                    "text": f"⏰ Job '{name}' {'enabled' if action == 'enable' else 'disabled'}"
                }
            ],
        }

    elif action == "history":
        history = _load_history()
        if name:
            history = [h for h in history if h.get("name") == name]
        if not history:
            return {
                "status": "success",
                "content": [{"text": f"No history{f' for {name}' if name else ''}."}],
            }

        lines = [f"⏰ History (last {min(len(history), 20)}):\n"]
        for h in history[-20:]:
            emoji = (
                "✅"
                if h.get("status") == "success"
                else "❌" if h.get("status") == "error" else "⏭️"
            )
            lines.append(
                f"  {emoji} [{h.get('started_at', '?')[:19]}] {h.get('name', '?')}: {h.get('result', '')[:100]}"
            )

        return {"status": "success", "content": [{"text": "\n".join(lines)}]}

    elif action == "run_now":
        if not name:
            return {"status": "error", "content": [{"text": "name required"}]}
        jobs = _load_jobs()
        if name not in jobs:
            return {"status": "error", "content": [{"text": f"Job '{name}' not found"}]}

        job = jobs[name]
        run_agent = agent or _state.get("agent")
        if not run_agent:
            return {
                "status": "error",
                "content": [{"text": "No agent available. Start scheduler first."}],
            }

        _execute_job(job, run_agent)
        jobs[name]["last_run"] = datetime.now().isoformat()
        jobs[name]["run_count"] = jobs[name].get("run_count", 0) + 1
        _save_jobs(jobs)
        return {
            "status": "success",
            "content": [{"text": f"⏰ Job '{name}' executed."}],
        }

    elif action == "clear_history":
        _save_history([])
        return {"status": "success", "content": [{"text": "⏰ History cleared."}]}

    else:
        return {"status": "error", "content": [{"text": f"Unknown action: {action}"}]}
