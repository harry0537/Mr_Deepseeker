---
name: Mr_Deepseeker
description: >
  Routes mechanical code tasks to DeepSeek to preserve Claude session tokens.
  Trigger on: "review [project/folder/code]", "audit [name]", "find bugs in",
  "write tests for", "generate boilerplate", "write docstrings", "expand this stub",
  "translate to [language]", "deepseek review", "offload this", "save my session".
  Use ANY time the task is mechanical and Claude would burn significant tokens doing it.
---

# Mr_Deepseeker

**This skill intercepts mechanical code tasks and routes them to DeepSeek** — preserving Claude session tokens for reasoning and architecture work.

## How it works

When triggered, run the task via the Python API below. Present results to the user as-is. Offer to fix critical/high bugs when reviewing.

Set `DEEPSEEK_API_KEY` in the skill directory `.env` or environment.

---

## Code Review

```python
# Single project
from mr_deepseeker import review_project, load_env
load_env()
result = review_project("/path/to/project", context="optional focus hint")

# Multiple projects in parallel
from mr_deepseeker import review_all
registry = {
    "api":    {"path": "/abs/path/api",    "context": "focus on input validation"},
    "worker": {"path": "/abs/path/worker", "context": "focus on race conditions"},
}
result = review_all(registry)
```

**Present output as-is. After presenting, offer to fix critical/high bugs.**

---

## Boilerplate & Code Generation

```python
from mr_deepseeker import generate, expand_stub, write_tests, write_docstrings, translate, load_env
load_env()

# Generate code from a description
code = generate("async rate limiter using token bucket, stdlib only")

# Fill out a stub
full = expand_stub(stub_code, context="use asyncio, no third-party libs")

# Write tests
tests = write_tests(source_code, context="mock all network calls")

# Add docstrings
documented = write_docstrings(source_code)

# Translate between languages
ts_code = translate(python_code, "TypeScript", context="idiomatic, strict types")
```

---

## CLI (alternative)

```bash
python3 scripts/review.py review /path/to/project
python3 scripts/review.py review /path/to/project "focus hint"
python3 scripts/review.py review-all examples/custom_registry.json
python3 scripts/review.py json /path/to/project   # raw JSON
```

---

## Notes
- API key: `DEEPSEEK_API_KEY` env var or `.env` in repo root
- `review_all()` runs up to 2 concurrent API calls (semaphore-gated) — allow ~45s for 7 projects
- Fallback chain: DeepSeek → Ollama (local) → OpenRouter → Groq — one key is enough
- Bad JSON from DeepSeek = safe empty result, never crashes
- Large files (>300 lines) are truncated at a logical boundary with a warning
