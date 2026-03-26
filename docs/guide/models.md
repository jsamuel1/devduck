# Model Providers

DevDuck supports 14 model providers with smart auto-detection.

---

## Auto-Detection Priority

DevDuck checks for credentials in this order and uses the first available:

| # | Provider | Detection |
|---|----------|-----------|
| 1 | **Amazon Bedrock** | `AWS_BEARER_TOKEN_BEDROCK` or AWS STS credentials |
| 2 | **Anthropic** | `ANTHROPIC_API_KEY` |
| 3 | **OpenAI** | `OPENAI_API_KEY` |
| 4 | **GitHub Models** | `GITHUB_TOKEN` or `PAT_TOKEN` |
| 5 | **Google Gemini** | `GOOGLE_API_KEY` or `GEMINI_API_KEY` |
| 6 | **Cohere** | `COHERE_API_KEY` |
| 7 | **Writer** | `WRITER_API_KEY` |
| 8 | **Mistral** | `MISTRAL_API_KEY` |
| 9 | **LiteLLM** | `LITELLM_API_KEY` |
| 10 | **LlamaAPI** | `LLAMAAPI_API_KEY` |
| 11 | **SageMaker** | `SAGEMAKER_ENDPOINT_NAME` |
| 12 | **LlamaCpp** | `LLAMACPP_MODEL_PATH` |
| 13 | **MLX** | Apple Silicon + `strands_mlx` installed |
| 14 | **Ollama** | Fallback (always available) |

---

## Manual Selection

```bash
# Force specific provider
export MODEL_PROVIDER=anthropic
devduck

# With specific model
export MODEL_PROVIDER=bedrock
export STRANDS_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0
devduck

# Common parameters
export STRANDS_MAX_TOKENS=60000
export STRANDS_TEMPERATURE=1.0
```

---

## Provider Configuration

=== "Amazon Bedrock"
    ```bash
    # Option 1: AWS credentials (default profile)
    aws configure

    # Option 2: Bearer token
    export AWS_BEARER_TOKEN_BEDROCK=...

    # Option 3: Explicit
    export MODEL_PROVIDER=bedrock
    export STRANDS_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0
    ```

=== "Anthropic"
    ```bash
    export ANTHROPIC_API_KEY=sk-ant-...
    # Optional:
    export STRANDS_MODEL_ID=claude-sonnet-4-20250514
    ```

=== "OpenAI"
    ```bash
    export OPENAI_API_KEY=sk-...
    # Optional:
    export STRANDS_MODEL_ID=gpt-4o
    ```

=== "Google Gemini"
    ```bash
    export GOOGLE_API_KEY=...
    # Optional:
    export STRANDS_MODEL_ID=gemini-2.5-flash
    ```

=== "Ollama (Local)"
    ```bash
    # Just have Ollama running
    ollama serve

    # Optional:
    export OLLAMA_HOST=http://localhost:11434
    export STRANDS_MODEL_ID=qwen3:1.7b  # macOS default
    ```

=== "MLX (Apple Silicon)"
    ```bash
    pip install strands-mlx
    export MODEL_PROVIDER=mlx
    export STRANDS_MODEL_ID=mlx-community/Qwen3-1.7B-4bit
    ```

---

## Multi-Model with use_agent

Use different models for different tasks within the same session:

```python
# Use Anthropic for creative writing
use_agent(
    prompt="Write a haiku about artificial intelligence",
    system_prompt="You are a minimalist poet.",
    model_provider="anthropic"
)

# Use local Ollama for sensitive data
use_agent(
    prompt="Summarize this confidential document",
    system_prompt="You summarize documents concisely.",
    model_provider="ollama",
    model_settings={"model_id": "qwen3:8b"}
)

# Use environment configuration
use_agent(
    prompt="Analyze this data",
    system_prompt="You are a data analyst.",
    model_provider="env"
)
```

→ See [Multi-Agent](multi-agent.md) for more patterns.

---

## Ollama Smart Defaults

DevDuck picks sensible Ollama models per platform:

| OS | Default Model |
|----|---------------|
| macOS | `qwen3:1.7b` |
| Linux | `qwen3:30b` |
| Windows | `qwen3:8b` |

Override with `STRANDS_MODEL_ID`.
