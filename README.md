# Mr_Deepseeker

**Stop burning Claude session limits on mechanical work.**

Mr_Deepseeker offloads code review and boilerplate generation to DeepSeek — a capable, cheap coding model — so your Claude sessions stay focused on the reasoning and architecture work only Claude should be doing.

Zero dependencies. Pure stdlib. Works standalone or as a [Claude Code](https://claude.ai/code) skill.

---

## The problem

Claude has session limits. Every token spent generating boilerplate, writing tests, reviewing files for bugs, or translating code is a token that could have gone to something harder. DeepSeek is purpose-built for mechanical code tasks and costs a fraction of a cent per call.

Mr_Deepseeker is the bridge.

---

## What it does

### Code Review
Point it at any Python folder. DeepSeek reads every `.py` file and returns a structured bug report — severity-ranked, file/line referenced, remediation included.

```
[CRITICAL] order_manager.py:87  [race_condition]
    Position update and order submission are not atomic
    FIX: Use asyncio.Lock() around the position update + submit block

[HIGH]     risk_engine.py:134  [logic_error]
    Kelly fraction not clamped — can return >1.0 on high-confidence signals
    FIX: fraction = min(kelly_fraction, max_kelly) before returning
```

### Boilerplate & Code Generation
Delegate any mechanical coding task: generate code from a description, fill out stubs, write tests, add docstrings, translate between languages.

```python
from mr_deepseeker import generate, expand_stub, write_tests, write_docstrings, translate

# Generate from scratch
code = generate("async rate limiter using token bucket, stdlib only")

# Fill out a stub
full = expand_stub(my_stub_code, context="use asyncio, no third-party libs")

# Write tests
tests = write_tests(open("my_module.py").read(), context="mock all network calls")

# Add docstrings to a file
src = write_docstrings(open("utils.py").read())

# Translate to another language
go_code = translate(python_code, "Go", context="idiomatic Go, stdlib only")
```

---

## Install

```bash
git clone https://github.com/harry0537/Mr_Deepseeker.git
cd Mr_Deepseeker
cp .env.example .env
# Add your DEEPSEEK_API_KEY to .env
```

Get a DeepSeek key at [platform.deepseek.com](https://platform.deepseek.com). Code reviews cost ~$0.01 each.

---

## Usage

### CLI — review a project

```bash
# Review a folder
python3 scripts/review.py review /path/to/your/project

# With focus hint
python3 scripts/review.py review /path/to/your/project "focus on async race conditions"

# Review multiple projects from a registry
python3 scripts/review.py review-all examples/custom_registry.json

# Raw JSON output
python3 scripts/review.py json /path/to/your/project
```

### Python API — review

```python
from mr_deepseeker import review_project, review_all, load_env
load_env()  # loads .env

result = review_project("/path/to/project", context="focus on API timeout handling")

for bug in result["bugs"]:
    sev = bug["severity"].upper()
    loc = f"{bug['file']}:{bug.get('line', '')}"
    print(f"[{sev}] {loc} — {bug['description']}")

# Multiple folders in parallel
registry = {
    "api":    {"path": "/path/to/api",    "context": "REST API, focus on input validation"},
    "worker": {"path": "/path/to/worker", "context": "async worker, focus on race conditions"},
}
report = review_all(registry)
print(f"Total bugs: {report['summary']['total_bugs']}")
```

### Python API — boilerplate

```python
from mr_deepseeker import generate, expand_stub, write_tests, write_docstrings, translate, load_env
load_env()

# Generate a dataclass
code = generate("dataclass for a trade order: BUY/SELL enum, ticker str, price float, quantity int, timestamp datetime")
print(code)

# Expand a stub you wrote
stub = """
def retry(fn, max_attempts: int, backoff: float):
    # TODO: exponential backoff, re-raise on final attempt
    pass
"""
print(expand_stub(stub))

# Write tests for an existing module
tests = write_tests(open("src/parser.py").read())
open("tests/test_parser.py", "w").write(tests)

# Translate Python → TypeScript
ts = translate(open("src/utils.py").read(), "TypeScript")
open("src/utils.ts", "w").write(ts)
```

---

## As a Claude Code Skill

Install so Claude automatically delegates to Mr_Deepseeker when approaching session limits:

```bash
cp -r claude_skill ~/.claude/skills/Mr_Deepseeker
```

Add your key to `~/.claude/skills/Mr_Deepseeker/.env` (or set `DEEPSEEK_API_KEY` in your environment).

Claude will offload code review and boilerplate tasks to DeepSeek instead of burning session tokens on them.

---

## LLM fallback chain

One key is enough. Mr_Deepseeker tries providers in order until one works:

1. **DeepSeek** (`DEEPSEEK_API_KEY`) — primary, best quality, cheapest
2. **Ollama** (local) — free if you have Ollama running
3. **OpenRouter** (`OPENROUTER_API_KEY`) — free tier models
4. **Groq** (`GROQ_API_KEY`) — fast free tier, rate limited

---

## Output schema

```json
{
  "files_reviewed": ["order_manager.py", "risk_engine.py"],
  "bugs": [
    {
      "severity": "critical",
      "file": "order_manager.py",
      "line": 87,
      "category": "race_condition",
      "description": "Position update and order submission are not atomic",
      "remediation": "Use asyncio.Lock() around the update block"
    }
  ],
  "reliability_risks": ["No circuit breaker on API failures"],
  "dead_code_fragments": [{"file": "utils.py", "lines": "45-60", "function": "old_formatter"}]
}
```

---

## Project structure

```
mr_deepseeker/
├── deepseek.py      # review_project(), review_all()
├── boilerplate.py   # generate(), expand_stub(), write_tests(), write_docstrings(), translate()
├── llm_client.py    # LLM delegation with fallback chain
└── env.py           # .env loader

scripts/
└── review.py        # CLI

claude_skill/
├── SKILL.md         # Claude Code skill definition
└── references/

examples/
├── custom_registry.json
└── trading_brain_example.py
```

---

## License

MIT
