# TUI Mode

Multi-conversation terminal UI with concurrent panels and streaming markdown.

---

## Launch

```bash
devduck --tui
```

Requires the `textual` package:

```bash
pip install textual
```

---

## Features

- **Multiple conversations** — Run several conversations concurrently in separate panels
- **Streaming markdown** — Rich formatted output as the agent responds
- **Interleaved execution** — Conversations run in parallel, not blocking each other
- **Full tool access** — Each conversation has access to the complete tool set
- **Keyboard navigation** — Switch between conversations with keyboard shortcuts

---

## vs REPL Mode

| Feature | REPL | TUI |
|---------|------|-----|
| Conversations | Single | Multiple concurrent |
| Output | Plain text streaming | Rich markdown panels |
| Interaction | Sequential | Parallel |
| UI | prompt_toolkit | Textual framework |
| Dependencies | Built-in | Requires `textual` |

For simple tasks, use `devduck` (REPL). For complex multi-task workflows, use `devduck --tui`.
