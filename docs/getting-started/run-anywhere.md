# Run Anywhere

DevDuck runs on Linux, macOS, Windows, Docker, Android, and Cloud.

---

## Platform Setup

=== "🐧 Linux"
    ```bash
    # Ubuntu/Debian
    sudo apt update && sudo apt install -y python3.13 python3.13-venv pipx
    pipx install devduck

    # Or with pip
    python3.13 -m pip install devduck
    ```

=== "🍎 macOS"
    ```bash
    # With Homebrew
    brew install python@3.13 pipx
    pipx install devduck

    # Apple Silicon bonus: local models via MLX
    pip install strands-mlx
    ```

=== "🪟 Windows"
    ```powershell
    # Install Python 3.13 from python.org, then:
    pip install devduck

    # Or with pipx
    pipx install devduck
    ```

=== "🐳 Docker"
    ```bash
    docker run -it \
      -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
      cagataycali/devduck

    # With volume mount for persistence
    docker run -it \
      -v $(pwd):/workspace \
      -w /workspace \
      -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
      cagataycali/devduck
    ```

=== "📱 Android (Termux)"
    ```bash
    pkg install python
    pip install devduck
    export ANTHROPIC_API_KEY=sk-ant-...
    devduck
    ```

=== "☁️ Cloud"
    ```bash
    # AWS EC2 / Lambda / AgentCore
    pip install devduck
    devduck deploy --launch  # → AgentCore

    # GitHub Codespaces
    pipx install devduck && devduck
    ```

---

## Environment Variables

### Model Configuration

```bash
export MODEL_PROVIDER=bedrock          # Force provider
export STRANDS_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0
export STRANDS_MAX_TOKENS=60000
export STRANDS_TEMPERATURE=1.0
```

### Server Configuration

```bash
export DEVDUCK_ENABLE_WS=true          # WebSocket (default: true)
export DEVDUCK_WS_PORT=10001           # WebSocket port
export DEVDUCK_ENABLE_TCP=false        # TCP server
export DEVDUCK_ENABLE_ZENOH=true       # Zenoh P2P (default: true)
export DEVDUCK_ENABLE_MCP=false        # MCP HTTP server
```

### Feature Flags

```bash
export DEVDUCK_AMBIENT_MODE=true       # Background thinking
export DEVDUCK_LOAD_TOOLS_FROM_DIR=true # Auto-load ./tools/*.py
export DEVDUCK_KNOWLEDGE_BASE_ID=...   # Automatic RAG
export DEVDUCK_ASCIINEMA=true          # Record .cast files
```

### Tool Configuration

```bash
# Format: package1:tool1,tool2;package2:tool3,tool4
export DEVDUCK_TOOLS="strands_tools:shell,editor;devduck.tools:system_prompt,websocket"
```
