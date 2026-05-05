# Mr_Deepseeker

> *"Why pay a surgeon to mop the floor?"*

**Mr_Deepseeker is a Claude Code skill** that intercepts mechanical code tasks — reviews, test generation, boilerplate, docstrings, translation — and routes them to DeepSeek instead of burning your Claude session budget on them.

You keep working in Claude Code exactly as you do now. Mr_Deepseeker just makes sure the expensive model only does the expensive work.

Zero dependencies. Pure Python stdlib.

---

## Install

```bash
git clone https://github.com/harry0537/Mr_Deepseeker.git
cp -r Mr_Deepseeker/claude_skill ~/.claude/skills/Mr_Deepseeker
```

Add your DeepSeek API key (free at [platform.deepseek.com](https://platform.deepseek.com)):

```bash
echo "DEEPSEEK_API_KEY=sk-your-key-here" > ~/.claude/skills/Mr_Deepseeker/.env
```

That's it. Restart Claude Code and the skill is live.

---

## What happens inside Claude Code

Ask Claude to do any mechanical code task and Mr_Deepseeker handles it:

```
you:    review my project
claude: [runs DeepSeek review, presents results — zero session tokens burned]

you:    write tests for src/parser.py
claude: [generates full pytest suite via DeepSeek]

you:    expand this stub
claude: [fills out implementation via DeepSeek]

you:    translate utils.py to TypeScript
claude: [routes to DeepSeek, returns idiomatic TS]
```

Trigger phrases: *"review [project]"*, *"audit [folder]"*, *"find bugs in"*, *"write tests for"*, *"generate boilerplate"*, *"write docstrings"*, *"expand this stub"*, *"translate to [language]"*

---

## The economics

This isn't just convenience. The numbers make the case:

| | Input | Output |
|---|---|---|
| **Claude Sonnet** | $3.00 / 1M tokens | $15.00 / 1M tokens |
| **DeepSeek v3** | $0.27 / 1M tokens | $1.10 / 1M tokens |
| **Savings** | **11× cheaper** | **13.6× cheaper** |

A full codebase review — 8k tokens in, 2k tokens out — costs **$0.004 with DeepSeek** versus **$0.054 with Claude**. Every review you offload preserves ~10,000 Claude tokens and extends your session before you hit the wall.

Reviewing 7 projects in parallel? That's a $0.03 DeepSeek call versus a $0.38 Claude session burn.

**Mr_Deepseeker is not a replacement for Claude. It's the system that makes Claude last.**

---

## What it can do

### Code Review
Severity-ranked bug reports with file/line references and remediation hints:

```
[CRITICAL] order_manager.py:87  [race_condition]
    Position update and order submission are not atomic
    FIX: Use asyncio.Lock() around the update block

[HIGH]     risk_engine.py:134  [logic_error]
    Kelly fraction not clamped — can return >1.0 on high-confidence signals
    FIX: fraction = min(kelly_fraction, max_kelly) before returning
```

### Boilerplate & Generation
- **generate** — code from a plain-English description
- **expand_stub** — fill out a skeleton or TODO implementation
- **write_tests** — full pytest suite for any module
- **write_docstrings** — add docstrings to every undocumented function
- **translate** — rewrite code in another language (Go, TypeScript, Rust, etc.)

---

## Using the Python API directly

The skill runs on top of a clean Python library you can also call standalone:

```python
from mr_deepseeker import review_project, review_all, generate, write_tests, load_env
load_env()

# Review a project
result = review_project("/path/to/project", context="focus on race conditions")
for bug in result["bugs"]:
    print(f"[{bug['severity'].upper()}] {bug['file']}:{bug.get('line','')} — {bug['description']}")

# Review multiple projects in parallel
report = review_all({
    "api":    {"path": "/path/api",    "context": "REST API"},
    "worker": {"path": "/path/worker", "context": "async worker"},
})

# Generate boilerplate
code = generate("async rate limiter using token bucket, stdlib only")
tests = write_tests(open("src/parser.py").read())
```

### CLI

```bash
python3 scripts/review.py review /path/to/project
python3 scripts/review.py review /path/to/project "focus on async race conditions"
python3 scripts/review.py review-all examples/custom_registry.json
python3 scripts/review.py json /path/to/project
```

---

## LLM fallback chain

One key is enough. Tries providers in order until one succeeds:

1. **DeepSeek** (`DEEPSEEK_API_KEY`) — primary, best for code, cheapest
2. **Ollama** (local, `OLLAMA_MODEL`) — free if you have Ollama running
3. **OpenRouter** (`OPENROUTER_API_KEY`) — free tier models
4. **Groq** (`GROQ_API_KEY`) — fast free tier, rate limited

---

## Project structure

```
claude_skill/           ← install this as your Claude Code skill
├── SKILL.md
└── references/

mr_deepseeker/          ← the engine underneath
├── deepseek.py         # review_project(), review_all()
├── boilerplate.py      # generate(), expand_stub(), write_tests(), write_docstrings(), translate()
├── llm_client.py       # LLM delegation + fallback chain
└── env.py              # .env loader

scripts/
└── review.py           # standalone CLI

examples/
└── custom_registry.json
```

---

## License

MIT
