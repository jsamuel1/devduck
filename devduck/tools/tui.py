"""
🖥️ TUI Tool — Let the agent dynamically push content to the TUI.

The agent can write markdown panels, tables, notifications, progress bars,
and custom Rich renderables into the running TUI from any conversation.
"""

import sys
import time
from typing import Any, Dict, List, Optional

from strands import tool


# ─── Global TUI app reference (set by tui.py on startup) ────────
_tui_app = None


def set_tui_app(app):
    """Register the running TUI app instance for tool access."""
    global _tui_app
    _tui_app = app


def get_tui_app():
    """Get the current TUI app if running."""
    return _tui_app


@tool
def tui(
    action: str,
    content: str = "",
    title: str = "",
    style: str = "cyan",
    markdown: bool = True,
    conv_id: int = 0,
) -> Dict[str, Any]:
    """
    🖥️ Push dynamic content to the DevDuck TUI.

    Use this to render rich panels, markdown, notifications, and status
    updates directly in the TUI interface. Works from any conversation.

    Args:
        action: Action to perform:
            - "panel": Render a Rich panel with content (markdown or plain)
            - "notify": Show a transient notification toast
            - "markdown": Render raw markdown into the conversation log
            - "status": Update the status bar text
            - "clear_done": Clear completed conversation panels
            - "info": Get current TUI state (active conversations, peers, etc.)
        content: Text content (supports markdown when markdown=True)
        title: Panel title (for "panel" action)
        style: Border/accent style color (e.g. "cyan", "green", "red", "#61afef")
        markdown: Whether to render content as Markdown (default: True)
        conv_id: Target conversation ID (0 = create a new standalone panel)

    Returns:
        Dict with status and result info

    Examples:
        # Render a markdown report panel
        tui(action="panel", content="## Results\\n- Item 1\\n- Item 2", title="Report")

        # Show a notification toast
        tui(action="notify", content="Build complete! ✅")

        # Push markdown into the current conversation
        tui(action="markdown", content="| Col1 | Col2 |\\n|------|------|\\n| a | b |", conv_id=3)

        # Get TUI state
        tui(action="info")
    """
    try:
        app = get_tui_app()

        if app is None:
            return {
                "status": "error",
                "content": [{"text": "TUI is not running. Use `devduck --tui` to start TUI mode."}],
            }

        if action == "panel":
            return _action_panel(app, content, title, style, markdown)
        elif action == "notify":
            return _action_notify(app, content, title, style)
        elif action == "markdown":
            return _action_markdown(app, content, conv_id)
        elif action == "status":
            return _action_status(app, content)
        elif action == "clear_done":
            app.action_clear_done()
            return {
                "status": "success",
                "content": [{"text": "Cleared completed conversations."}],
            }
        elif action == "info":
            return _action_info(app)
        else:
            return {
                "status": "error",
                "content": [{"text": f"Unknown action: {action}. Valid: panel, notify, markdown, status, clear_done, info"}],
            }

    except Exception as e:
        return {
            "status": "error",
            "content": [{"text": f"TUI tool error: {e}"}],
        }


def _action_panel(app, content: str, title: str, style: str, use_markdown: bool) -> Dict:
    """Render a standalone panel in the TUI."""
    from textual.widgets import Static
    from textual.containers import ScrollableContainer
    from textual.css.query import NoMatches
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.text import Text

    try:
        scroll = app.query_one("#conversations-scroll", ScrollableContainer)
    except NoMatches:
        return {"status": "error", "content": [{"text": "TUI scroll area not found"}]}

    if use_markdown and content:
        renderable = Markdown(content)
    else:
        renderable = Text(content)

    panel_widget = Static(
        Panel(
            renderable,
            title=title or "🦆 Agent Output",
            border_style=style,
            padding=(1, 2),
        )
    )

    app.call_from_thread(scroll.mount, panel_widget)
    app.call_from_thread(scroll.scroll_end, animate=False)

    return {
        "status": "success",
        "content": [{"text": f"Panel rendered: {title or 'Agent Output'} ({len(content)} chars)"}],
    }


def _action_notify(app, content: str, title: str, style: str) -> Dict:
    """Show a notification toast."""
    severity = "information"
    if style in ("red", "error"):
        severity = "error"
    elif style in ("yellow", "warning"):
        severity = "warning"

    app.call_from_thread(app.notify, content, title=title or "🦆 DevDuck", severity=severity)

    return {
        "status": "success",
        "content": [{"text": f"Notification shown: {content[:100]}"}],
    }


def _action_markdown(app, content: str, conv_id: int) -> Dict:
    """Render markdown into a specific conversation or as standalone."""
    from textual.widgets import Static, RichLog
    from textual.containers import ScrollableContainer
    from textual.css.query import NoMatches
    from rich.markdown import Markdown

    if conv_id > 0:
        # Push into existing conversation
        panel = app._active_conversations.get(conv_id)
        if not panel:
            return {
                "status": "error",
                "content": [{"text": f"Conversation #{conv_id} not found. Active: {list(app._active_conversations.keys())}"}],
            }

        try:
            log = panel.query_one(f"#log-{conv_id}", RichLog)
            app.call_from_thread(log.write, Markdown(content))
            return {
                "status": "success",
                "content": [{"text": f"Markdown rendered in conversation #{conv_id}"}],
            }
        except NoMatches:
            return {"status": "error", "content": [{"text": f"Log widget not found for #{conv_id}"}]}
    else:
        # Standalone markdown panel
        return _action_panel(app, content, "", "dim", True)


def _action_status(app, content: str) -> Dict:
    """Update the TUI status bar."""
    from textual.widgets import Static
    from textual.css.query import NoMatches
    from rich.text import Text

    try:
        bar = app.query_one("#status-bar", Static)
        t = Text()
        t.append(" 🦆 ", style="bold bright_yellow")
        t.append(content, style="bold")
        app.call_from_thread(bar.update, t)
        return {
            "status": "success",
            "content": [{"text": f"Status bar updated: {content[:100]}"}],
        }
    except NoMatches:
        return {"status": "error", "content": [{"text": "Status bar not found"}]}


def _action_info(app) -> Dict:
    """Get current TUI state."""
    active = []
    done = []
    for cid, panel in app._active_conversations.items():
        entry = {"id": cid, "query": panel.query[:80], "color": panel.color}
        if panel.is_done:
            done.append(entry)
        else:
            active.append(entry)

    peer_count = 0
    try:
        _zp_mod = sys.modules.get("devduck.tools.zenoh_peer")
        if _zp_mod:
            peer_count = len(_zp_mod.ZENOH_STATE.get("peers", {}))
    except Exception:
        pass

    info = {
        "tui_running": True,
        "total_queries": app._total_queries,
        "active_conversations": active,
        "done_conversations": len(done),
        "zenoh_peers": peer_count,
    }

    import json
    return {
        "status": "success",
        "content": [{"text": json.dumps(info, indent=2)}],
    }
