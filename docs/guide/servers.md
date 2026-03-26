# Servers

Connect to DevDuck via WebSocket, TCP, Unix sockets, or MCP. All with real-time streaming.

---

## Port Allocation

| Port | Protocol | Default | Description |
|------|----------|---------|-------------|
| 10000 | WebSocket | Enabled | Mesh Relay (browser + AgentCore) |
| 10001 | WebSocket | Enabled | Per-message DevDuck agent |
| 10002 | TCP | Disabled | Raw socket |
| 10003 | HTTP | Disabled | MCP HTTP server |
| — | Unix Socket | Disabled | IPC gateway |
| multicast | Zenoh | Enabled | P2P auto-discovery |

---

## Configuration

```bash
export DEVDUCK_ENABLE_WS=true          # WebSocket (default: true)
export DEVDUCK_WS_PORT=10001
export DEVDUCK_ENABLE_TCP=false         # TCP (default: false)
export DEVDUCK_TCP_PORT=10002
export DEVDUCK_ENABLE_MCP=false         # MCP HTTP (default: false)
export DEVDUCK_MCP_PORT=10003
export DEVDUCK_ENABLE_IPC=false         # IPC (default: false)
export DEVDUCK_IPC_SOCKET=/tmp/devduck_main.sock
export DEVDUCK_ENABLE_ZENOH=true        # Zenoh P2P (default: true)
export DEVDUCK_ENABLE_AGENTCORE_PROXY=true  # Mesh relay (default: true)
export DEVDUCK_AGENTCORE_PROXY_PORT=10000
```

!!! info "Smart Port Handling"
    If a port is in use, DevDuck automatically finds the next available port.

---

## WebSocket Server

JSON-based protocol with turn tracking and streaming chunks.

### Message Types

| Type | Direction | Description |
|------|-----------|-------------|
| `connected` | Server→Client | Connection established |
| `turn_start` | Server→Client | New conversation turn |
| `chunk` | Server→Client | Streaming text chunk |
| `tool_start` | Server→Client | Tool invocation started |
| `tool_end` | Server→Client | Tool completed |
| `turn_end` | Server→Client | Turn completed |
| `error` | Server→Client | Error occurred |

### Example Client

```javascript
const ws = new WebSocket('ws://localhost:10001');

ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    switch(msg.type) {
        case 'chunk':
            process.stdout.write(msg.data);
            break;
        case 'tool_start':
            console.log(`🛠️ Tool #${msg.tool_number}: ${msg.data}`);
            break;
        case 'turn_end':
            console.log('\n✅ Complete');
            break;
    }
};

ws.onopen = () => ws.send('Hello DevDuck!');
```

### Tool API

```python
# Start server
websocket(action="start_server", port=10001)

# Check status
websocket(action="get_status")

# Stop server
websocket(action="stop_server")
```

---

## TCP Server

Raw text protocol for scripts and CLI tools.

```bash
# Connect with netcat
echo "Hello DevDuck" | nc localhost 10002

# Interactive session
nc localhost 10002
```

```python
tcp(action="start_server", port=10002)
tcp(action="get_status")
tcp(action="stop_server")
```

---

## IPC (Unix Socket)

Fast local communication for same-machine agent coordination.

```python
ipc(action="start_server", socket_path="/tmp/devduck_main.sock")
```

```bash
# Connect from another process
echo "query" | socat - UNIX-CONNECT:/tmp/devduck_main.sock
```
