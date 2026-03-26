# Multi-Model Examples

Use different AI models for different tasks within one DevDuck session.

---

## Creative + Analytical Pipeline

```python
# Step 1: Creative writing with Anthropic
use_agent(
    prompt="Write a product description for an AI-powered rubber duck",
    system_prompt="You are a creative copywriter.",
    model_provider="anthropic"
)

# Step 2: SEO analysis with OpenAI
use_agent(
    prompt="Analyze the above copy for SEO optimization",
    system_prompt="You are an SEO expert.",
    model_provider="openai"
)
```

## Local Privacy + Cloud Power

```python
# Process sensitive data locally
use_agent(
    prompt="Extract PII from this document and redact it",
    system_prompt="You redact personal information.",
    model_provider="ollama",
    model_settings={"model_id": "qwen3:8b"},
    tools=["file_read", "file_write"]
)

# Send redacted version to cloud for analysis
use_agent(
    prompt="Analyze the redacted document for business insights",
    system_prompt="You are a business analyst.",
    model_provider="bedrock"
)
```

## Model Comparison

```python
# Compare answers from different models
for provider in ["anthropic", "openai", "bedrock"]:
    use_agent(
        prompt="Explain quantum computing in one sentence",
        system_prompt="You are precise and concise.",
        model_provider=provider
    )
```

## Tool-Isolated Sub-Agents

```python
# Read-only auditor
use_agent(
    prompt="Review this codebase for security issues",
    system_prompt="You are a security auditor. Report only, never modify.",
    tools=["file_read", "shell"]  # No write access
)

# Builder with full access
use_agent(
    prompt="Implement the security fixes from the audit",
    system_prompt="You are a security engineer.",
    tools=["file_read", "file_write", "editor", "shell"]
)
```
