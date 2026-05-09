---
name: Mr_Deepseeker
description: >
  Routes mechanical code tasks to DeepSeek to preserve Claude session tokens.
  Trigger on: "review [project/folder/code]", "audit [name]", "find bugs in",
  "write tests for", "generate boilerplate", "write docstrings", "expand this stub",
  "translate to [language]", "refactor this", "add type hints", "fix these bugs",
  "summarize this file", "what does this file do", "generate commit message",
  "deepseek review", "offload this", "save my session".
  Use ANY time the task is mechanical and Claude would burn significant tokens doing it.
---

# Mr_Deepseeker

**Routes mechanical code tasks to DeepSeek — preserving Claude session tokens for reasoning and architecture work.**

---

## DIVISION OF LABOUR

| Task type | Who does it |
|-----------|-------------|
| Architecture decisions, tradeoffs, debugging reasoning | **Claude** |
| Reading + understanding unfamiliar files | **DeepSeek** (`summarize_file`) |
| Writing any code from scratch | **DeepSeek** (`generate`) |
| Filling out stubs / TODOs | **DeepSeek** (`expand_stub`) |
| Refactoring (rename, restructure, extract) | **DeepSeek** (`refactor`) |
| Adding type hints | **DeepSeek** (`add_type_hints`) |
| Writing tests | **DeepSeek** (`write_tests`) |
| Adding docstrings | **DeepSeek** (`write_docstrings`) |
| Bug review + audit | **DeepSeek** (`review_project`) |
| Applying bug fixes from review | **DeepSeek** (`fix_bugs`) |
| Translating to another language | **DeepSeek** (`translate`) |
| Git commit messages | **DeepSeek** (`write_commit_message`) |

---

## WORKFLOW 1 — File Understanding (SAVE TOKENS)

**Instead of reading files with Read tool, use `summarize_file` first.**

```python
from mr_deepseeker import summarize_file, load_env
load_env()

code = open("/path/to/file.py").read()
digest = summarize_file(code, filename="file.py")
print(digest)
# Claude works from the digest, not the 400-line file
```

Use this whenever:
- User asks "what does X do" and the file is >100 lines
- You need to understand multiple files before deciding what to change
- Exploring an unfamiliar codebase

---

## WORKFLOW 2 — Code Review + Auto-Fix

```python
from mr_deepseeker import review_project, fix_bugs, load_env
load_env()

# Step 1: review
result = review_project("/path/to/bot", context="focus on async race conditions")

# Step 2: let Claude decide which bugs to fix (reasoning layer)
critical = [b for b in result["bugs"] if b["severity"] in ("critical", "high")]

# Step 3: DeepSeek applies the fixes (writing layer)
src = open("/path/to/bot/main.py").read()
fixed = fix_bugs(src, critical)
open("/path/to/bot/main.py", "w").write(fixed)
```

Present review output as-is. After presenting, ask user which bugs to fix. Then use `fix_bugs` — do NOT write fixes manually.

---

## WORKFLOW 3 — Code Generation

```python
from mr_deepseeker import generate, expand_stub, write_tests, write_docstrings, translate, load_env
load_env()

# Generate from description
code = generate("async rate limiter using token bucket, stdlib only")

# Fill out a stub
full = expand_stub(stub_code, context="use asyncio, no third-party libs")

# Write tests
tests = write_tests(source_code, context="mock all network calls")

# Add docstrings
documented = write_docstrings(source_code)

# Translate
ts_code = translate(python_code, "TypeScript", context="idiomatic, strict types")
```

---

## WORKFLOW 4 — Mechanical Edits

```python
from mr_deepseeker import refactor, add_type_hints, write_commit_message, load_env
load_env()

# Rename / restructure
new_code = refactor(src, "rename _calc_kelly to _kelly_fraction everywhere; extract lines 40-60 into helper")

# Add types
typed = add_type_hints(src)

# Commit message from staged diff
import subprocess
diff = subprocess.check_output(["git", "diff", "--staged"], text=True)
msg = write_commit_message(diff, context="fixing the Kelly sizing bug")
print(msg)
```

---

## Code Review API

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

---

## CLI

```bash
python3 scripts/review.py review /path/to/project
python3 scripts/review.py review /path/to/project "focus hint"
python3 scripts/review.py review-all examples/custom_registry.json
python3 scripts/review.py json /path/to/project   # raw JSON
python3 scripts/review.py summarize /path/to/file.py
python3 scripts/review.py commit-msg              # reads git diff --staged
```

---

## Notes
- API key: `DEEPSEEK_API_KEY` env var or `.env` in repo root
- `review_all()` runs up to 2 concurrent API calls — allow ~45s for 7 projects
- Fallback chain: DeepSeek → Ollama (local) → OpenRouter → Groq — one key is enough
- Bad JSON from DeepSeek = safe empty result, never crashes
- Large files (>300 lines) truncated at logical boundary with a warning
- `summarize_file` is cheap (max_tokens=1024) — use it liberally
