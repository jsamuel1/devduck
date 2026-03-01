"""Slack tool for DevDuck agents - listen & send messages.

Follows the TCP tool pattern: each incoming Slack message spawns a fresh
DevDuck instance that processes it with full tool access. Responses are sent
back to the thread automatically (when auto_reply=true).

Features:
- Socket Mode real-time event processing (one DevDuck per message)
- Send messages, reactions, file uploads via Slack API
- Event history stored as JSONL
- Auto-reply toggle via STRANDS_SLACK_AUTO_REPLY env var
- Listen-only tag filtering via STRANDS_SLACK_LISTEN_ONLY_TAG
- Thinking/completion reaction indicators

Environment Variables:
    SLACK_BOT_TOKEN: xoxb-... token from Slack app
    SLACK_APP_TOKEN: xapp-... token with Socket Mode enabled
    STRANDS_SLACK_AUTO_REPLY: "true" to auto-reply (default: "false")
    STRANDS_SLACK_LISTEN_ONLY_TAG: Only process messages containing this tag
    SLACK_ALLOWED_USERS: Comma-separated allowlist of Slack user IDs or display names
        Example: "U0123ABCDEF,cagatay" or "U0123ABCDEF"
        If not set, all users are allowed (open access).
    SLACK_DEFAULT_EVENT_COUNT: Context event count (default: 42)

Required Slack App Scopes:
    chat:write, reactions:write, channels:history, app_mentions:read,
    channels:read, reactions:read, groups:read, im:read, mpim:read

Usage:
    # Start listening via Socket Mode
    slack(action="start_listener")

    # Send a message
    slack(action="send_message", channel="C123456", text="Hello!")

    # Reply in thread
    slack(action="send_message", channel="C123456", text="Reply", thread_ts="1234567890.123")

    # Add reaction
    slack(action="add_reaction", channel="C123456", timestamp="1234567890.123", emoji="thumbsup")

    # Get recent events
    slack(action="get_recent_events", count=10)

    # Stop listener
    slack(action="stop_listener")
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from strands import tool

logger = logging.getLogger(__name__)

# Event storage
EVENTS_DIR = Path.cwd() / "slack_events"
EVENTS_FILE = EVENTS_DIR / "events.jsonl"
EVENTS_DIR.mkdir(parents=True, exist_ok=True)

# Global listener state
_LISTENER_STATE: Dict[str, Any] = {
    "running": False,
    "bot_info": None,
    "connections": 0,
    "start_time": None,
    "parent_agent": None,
    "socket_client": None,
    "web_client": None,
}


def _get_web_client():
    """Get or create Slack WebClient."""
    if _LISTENER_STATE["web_client"]:
        return _LISTENER_STATE["web_client"]

    bot_token = os.environ.get("SLACK_BOT_TOKEN")
    if not bot_token:
        return None

    try:
        from slack_sdk.web.client import WebClient

        client = WebClient(token=bot_token)
        _LISTENER_STATE["web_client"] = client
        return client
    except ImportError:
        logger.error("slack_sdk not installed. pip install slack-sdk slack-bolt")
        return None
    except Exception as e:
        logger.error(f"Error creating Slack WebClient: {e}")
        return None


def _get_bot_info():
    """Get bot info (cached)."""
    if _LISTENER_STATE["bot_info"]:
        return _LISTENER_STATE["bot_info"]

    client = _get_web_client()
    if client:
        try:
            result = client.auth_test()
            _LISTENER_STATE["bot_info"] = dict(result.data)
            return _LISTENER_STATE["bot_info"]
        except Exception as e:
            logger.error(f"Error getting Slack bot info: {e}")
    return {}


def _store_event(event_data: Dict):
    """Append event to JSONL storage."""
    try:
        EVENTS_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "event_type": "slack_event",
            "payload": event_data,
            "timestamp": time.time(),
        }
        with open(EVENTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error(f"Error storing slack event: {e}")


def _get_recent_events(count: int = 20) -> List[Dict]:
    """Read last N events from JSONL."""
    if not EVENTS_FILE.exists():
        return []
    try:
        with open(EVENTS_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()[-count:]
        events = []
        for line in lines:
            try:
                events.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue
        return events
    except Exception as e:
        logger.error(f"Error reading slack events: {e}")
        return []


def _parse_allowed_users() -> Optional[Dict[str, set]]:
    """Parse SLACK_ALLOWED_USERS env var into sets of allowed IDs and names.

    Returns None if no allowlist is configured (open access).
    Returns {"ids": set of str, "names": set of lowercase str} otherwise.

    Slack user IDs always start with 'U' (e.g., U0123ABCDEF).
    Anything else is treated as a display name / username.
    """
    raw = os.environ.get("SLACK_ALLOWED_USERS", "").strip()
    if not raw:
        return None

    allowed_ids = set()
    allowed_names = set()

    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        # Slack user IDs start with U and are uppercase alphanumeric
        if entry.startswith("U") and entry[1:].isalnum():
            allowed_ids.add(entry)
        else:
            allowed_names.add(entry.lstrip("@").lower())

    return {"ids": allowed_ids, "names": allowed_names}


def _is_user_allowed(user_id: str) -> bool:
    """Check if a Slack user is in the allowlist.

    If SLACK_ALLOWED_USERS is not set, all users are allowed.
    Otherwise, the user's ID must match, or we look up their profile
    to check display_name / real_name against the names allowlist.
    """
    allowlist = _parse_allowed_users()
    if allowlist is None:
        return True  # No allowlist = open access

    if not user_id:
        return False

    # Check direct ID match
    if user_id in allowlist["ids"]:
        return True

    # If there are name-based entries, resolve user profile
    if allowlist["names"]:
        client = _get_web_client()
        if client:
            try:
                resp = client.users_info(user=user_id)
                user_data = resp.data.get("user", {})
                profile = user_data.get("profile", {})

                # Check: name, display_name, display_name_normalized, real_name, real_name_normalized
                candidates = [
                    user_data.get("name", ""),
                    profile.get("display_name", ""),
                    profile.get("display_name_normalized", ""),
                    profile.get("real_name", ""),
                    profile.get("real_name_normalized", ""),
                ]

                for name in candidates:
                    if name and name.lower() in allowlist["names"]:
                        return True

            except Exception as e:
                logger.debug(f"Could not resolve Slack user {user_id}: {e}")

    logger.info(
        f"Slack: blocked message from user_id={user_id} (not in SLACK_ALLOWED_USERS)"
    )
    return False


def _process_slack_message(event: Dict):
    """Process a single Slack message with a fresh DevDuck instance (TCP pattern)."""
    import threading

    channel_id = event.get("channel")
    text = event.get("text", "")
    user = event.get("user", "unknown")
    ts = event.get("ts")

    _LISTENER_STATE["connections"] += 1
    logger.info(f"Slack: processing message from {user} in {channel_id}")

    client = _get_web_client()

    # Add thinking reaction
    if client:
        try:
            client.reactions_add(name="thinking_face", channel=channel_id, timestamp=ts)
        except Exception as e:
            logger.debug(f"Could not add thinking reaction: {e}")

    try:
        from devduck import DevDuck

        # Fresh DevDuck per message (like TCP tool)
        connection_devduck = DevDuck(auto_start_servers=False)
        agent = connection_devduck.agent

        if not agent:
            logger.error("Failed to create DevDuck instance for slack message")
            return

        # Build context with recent events
        event_count = int(os.getenv("SLACK_DEFAULT_EVENT_COUNT", "42"))
        recent = _get_recent_events(event_count)
        event_ctx = (
            f"\nRecent Slack Events:\n{json.dumps(recent[-5:], indent=2)}"
            if recent
            else ""
        )

        # Inject slack context into system prompt
        agent.system_prompt += f"""

## Slack Integration Active:
- You are responding to a Slack message
- Channel: {channel_id}
- User: {user}
- Thread TS: {ts}
- Use slack tool to send messages: slack(action="send_message", channel="{channel_id}", text="reply", thread_ts="{ts}")
- Use slack tool to add reactions: slack(action="add_reaction", channel="{channel_id}", timestamp="{ts}", emoji="thumbsup")
- Use Slack markdown: *bold*, _italic_, `code`, ```code blocks```
{event_ctx}
"""

        prompt = f"[Slack #{channel_id}] User {user} says: {text}"
        result = agent(prompt)

        # Auto-reply if enabled
        auto_reply = os.getenv("STRANDS_SLACK_AUTO_REPLY", "false").lower() == "true"
        if auto_reply and result and str(result).strip() and client:
            try:
                client.chat_postMessage(
                    channel=channel_id,
                    text=str(result).strip(),
                    thread_ts=ts,
                )
            except Exception as e:
                logger.error(f"Error sending slack reply: {e}")

        # Remove thinking, add check
        if client:
            try:
                client.reactions_remove(
                    name="thinking_face", channel=channel_id, timestamp=ts
                )
                client.reactions_add(
                    name="white_check_mark", channel=channel_id, timestamp=ts
                )
            except Exception as e:
                logger.debug(f"Could not update reactions: {e}")

    except Exception as e:
        logger.error(f"Error processing slack message: {e}", exc_info=True)
        # Add error reaction
        if client:
            try:
                client.reactions_remove(
                    name="thinking_face", channel=channel_id, timestamp=ts
                )
                client.reactions_add(name="x", channel=channel_id, timestamp=ts)
            except Exception:
                pass


def _start_socket_mode(agent=None):
    """Start Slack Socket Mode listener."""
    import threading

    bot_token = os.environ.get("SLACK_BOT_TOKEN")
    app_token = os.environ.get("SLACK_APP_TOKEN")

    if not bot_token or not app_token:
        return {
            "status": "error",
            "content": [{"text": "❌ SLACK_BOT_TOKEN and SLACK_APP_TOKEN required."}],
        }

    if _LISTENER_STATE["running"]:
        return {
            "status": "success",
            "content": [{"text": "Slack listener already running"}],
        }

    try:
        from slack_bolt import App
        from slack_sdk.socket_mode import SocketModeClient
        from slack_sdk.socket_mode.request import SocketModeRequest
        from slack_sdk.socket_mode.response import SocketModeResponse
        from slack_sdk.web.client import WebClient
    except ImportError:
        return {
            "status": "error",
            "content": [
                {
                    "text": "❌ slack-sdk/slack-bolt not installed. pip install slack-sdk slack-bolt"
                }
            ],
        }

    try:
        web_client = WebClient(token=bot_token)
        _LISTENER_STATE["web_client"] = web_client

        socket_client = SocketModeClient(app_token=app_token, web_client=web_client)
        _LISTENER_STATE["socket_client"] = socket_client
        _LISTENER_STATE["parent_agent"] = agent

        # Get bot info
        bot_info = _get_bot_info()

        def process_event(client: SocketModeClient, req: SocketModeRequest):
            """Process incoming Socket Mode events."""
            # Acknowledge immediately
            response = SocketModeResponse(envelope_id=req.envelope_id)
            client.send_socket_mode_response(response)

            # Store event
            event_data = {
                "event_type": req.type,
                "payload": req.payload,
                "timestamp": time.time(),
                "envelope_id": req.envelope_id,
            }
            _store_event(event_data)

            # Process message events
            event = req.payload.get("event", {})
            if (
                req.type == "events_api"
                and event.get("type") == "message"
                and not event.get("subtype")
            ):
                # Skip own messages
                if event.get("bot_id") or event.get("user") == bot_info.get("user_id"):
                    return

                # User allowlist filter
                if not _is_user_allowed(event.get("user", "")):
                    return

                # Tag filter
                tag = os.environ.get("STRANDS_SLACK_LISTEN_ONLY_TAG")
                if tag and tag not in event.get("text", ""):
                    return

                # Process in thread (like TCP handle_client)
                t = threading.Thread(
                    target=_process_slack_message,
                    args=(event,),
                    daemon=True,
                )
                t.start()

        socket_client.socket_mode_request_listeners.append(process_event)
        socket_client.connect()

        _LISTENER_STATE["running"] = True
        _LISTENER_STATE["connections"] = 0
        _LISTENER_STATE["start_time"] = time.time()

        bot_name = bot_info.get("user", "unknown")

        return {
            "status": "success",
            "content": [
                {"text": f"✅ Slack Socket Mode listener started (@{bot_name})"},
                {"text": "🦆 Each message spawns a fresh DevDuck instance"},
                {
                    "text": f"Auto-reply: {os.getenv('STRANDS_SLACK_AUTO_REPLY', 'false')}"
                },
                {"text": f"Events stored: {EVENTS_FILE}"},
            ],
        }

    except Exception as e:
        logger.error(f"Error starting Slack Socket Mode: {e}", exc_info=True)
        return {"status": "error", "content": [{"text": f"❌ Error: {e}"}]}


@tool
def slack(
    action: str,
    channel: Optional[str] = None,
    text: Optional[str] = None,
    thread_ts: Optional[str] = None,
    timestamp: Optional[str] = None,
    emoji: Optional[str] = None,
    count: int = 20,
    parameters: Optional[Dict[str, Any]] = None,
    agent: Optional[Any] = None,
) -> Dict[str, Any]:
    """Slack integration for DevDuck - listen for messages and send responses.

    Each incoming message spawns a fresh DevDuck instance with full tool access.
    Provides Socket Mode listener and direct Slack API access.

    Args:
        action: Action to perform:
            Listener:
            - "start_listener": Start Socket Mode real-time listener
            - "stop_listener": Stop the listener
            - "listener_status": Get listener status
            - "get_recent_events": Get stored events

            Messaging:
            - "send_message": Send a message to a channel/thread
            - "add_reaction": Add emoji reaction to a message
            - "remove_reaction": Remove emoji reaction
            - "upload_file": Upload a file to a channel

            API Passthrough:
            - Any valid Slack API method (e.g., "conversations_list", "users_info")

        channel: Channel ID (e.g., "C0123456789")
        text: Message text (supports Slack markdown)
        thread_ts: Thread timestamp for replies
        timestamp: Message timestamp (for reactions)
        emoji: Emoji name without colons (for reactions)
        count: Number of recent events (for get_recent_events)
        parameters: Dict of params for API passthrough actions
        agent: Parent agent (auto-provided)

    Returns:
        Dict with status and content

    Environment Variables:
        SLACK_BOT_TOKEN: xoxb-... bot token
        SLACK_APP_TOKEN: xapp-... app token (for Socket Mode)
        STRANDS_SLACK_AUTO_REPLY: "true" to enable auto-reply
        STRANDS_SLACK_LISTEN_ONLY_TAG: Only process tagged messages
        SLACK_ALLOWED_USERS: Comma-separated user IDs/names allowlist
            Example: "U0123ABCDEF,cagatay" - if unset, all users allowed

    Examples:
        # Start listening
        slack(action="start_listener")

        # Send message
        slack(action="send_message", channel="C123", text="Hello!")

        # Reply in thread
        slack(action="send_message", channel="C123", text="Reply", thread_ts="1234.5678")

        # React to message
        slack(action="add_reaction", channel="C123", timestamp="1234.5678", emoji="thumbsup")

        # List channels
        slack(action="conversations_list")
    """

    # --- Event retrieval (no client needed) ---
    if action == "get_recent_events":
        events = _get_recent_events(count)
        if events:
            return {
                "status": "success",
                "content": [
                    {
                        "text": f"Recent {len(events)} Slack events:\n{json.dumps(events, indent=2, ensure_ascii=False)}"
                    }
                ],
            }
        return {"status": "success", "content": [{"text": "No events found"}]}

    if action == "listener_status":
        allowlist = _parse_allowed_users()
        status = {
            "running": _LISTENER_STATE["running"],
            "bot_info": _LISTENER_STATE["bot_info"],
            "messages_processed": _LISTENER_STATE["connections"],
            "events_file": str(EVENTS_FILE),
            "auto_reply": os.getenv("STRANDS_SLACK_AUTO_REPLY", "false"),
            "listen_only_tag": os.getenv("STRANDS_SLACK_LISTEN_ONLY_TAG", ""),
            "allowed_users": (
                {
                    "ids": sorted(allowlist["ids"]),
                    "names": sorted(allowlist["names"]),
                }
                if allowlist
                else "all (no restriction)"
            ),
            "uptime": (
                time.time() - _LISTENER_STATE["start_time"]
                if _LISTENER_STATE["start_time"]
                else 0
            ),
        }
        return {
            "status": "success",
            "content": [{"text": json.dumps(status, indent=2)}],
        }

    # --- Listener management ---
    if action == "start_listener":
        return _start_socket_mode(agent)

    if action == "stop_listener":
        if not _LISTENER_STATE["running"]:
            return {
                "status": "success",
                "content": [{"text": "Slack listener not running"}],
            }

        _LISTENER_STATE["running"] = False
        if _LISTENER_STATE["socket_client"]:
            try:
                _LISTENER_STATE["socket_client"].close()
            except Exception:
                pass
            _LISTENER_STATE["socket_client"] = None

        processed = _LISTENER_STATE["connections"]
        uptime = time.time() - (_LISTENER_STATE["start_time"] or time.time())

        return {
            "status": "success",
            "content": [
                {"text": "✅ Slack listener stopped"},
                {
                    "text": f"Stats: {processed} messages processed, uptime {uptime:.0f}s"
                },
            ],
        }

    # --- Actions requiring web client ---
    client = _get_web_client()
    if not client:
        return {
            "status": "error",
            "content": [
                {"text": "❌ SLACK_BOT_TOKEN not set or slack_sdk not installed."}
            ],
        }

    try:
        if action == "send_message":
            params = {"channel": channel, "text": text}
            if thread_ts:
                params["thread_ts"] = thread_ts
            resp = client.chat_postMessage(**params)
            return {
                "status": "success",
                "content": [
                    {"text": f"✅ Message sent. TS: {resp.get('ts', 'unknown')}"}
                ],
            }

        elif action == "add_reaction":
            client.reactions_add(name=emoji, channel=channel, timestamp=timestamp)
            return {
                "status": "success",
                "content": [{"text": f"✅ Reaction :{emoji}: added"}],
            }

        elif action == "remove_reaction":
            client.reactions_remove(name=emoji, channel=channel, timestamp=timestamp)
            return {
                "status": "success",
                "content": [{"text": f"✅ Reaction :{emoji}: removed"}],
            }

        elif action == "upload_file":
            params = parameters or {}
            if channel:
                params["channel_id"] = channel
            resp = client.files_upload_v2(**params)
            return {
                "status": "success",
                "content": [
                    {"text": f"✅ File uploaded: {json.dumps(resp.data, indent=2)}"}
                ],
            }

        else:
            # API passthrough - try any Slack method
            if hasattr(client, action) and callable(getattr(client, action)):
                method = getattr(client, action)
                resp = method(**(parameters or {}))
                return {
                    "status": "success",
                    "content": [
                        {"text": f"✅ {action} executed"},
                        {"text": json.dumps(resp.data, indent=2)},
                    ],
                }
            else:
                return {
                    "status": "error",
                    "content": [
                        {
                            "text": f"❌ Unknown action: {action}. Use: start_listener, stop_listener, "
                            "listener_status, get_recent_events, send_message, add_reaction, "
                            "remove_reaction, upload_file, or any Slack API method"
                        }
                    ],
                }

    except Exception as e:
        logger.error(f"Slack error in {action}: {e}", exc_info=True)
        return {"status": "error", "content": [{"text": f"❌ Error: {e}"}]}
