# Mr_Deepseeker setup prompt

Give this file to your AI coding agent (Claude Code, Codex, or similar). In a new session, say:

> Fetch https://raw.githubusercontent.com/harry0537/Mr_Deepseeker/main/SETUP_PROMPT.md with `curl -fsSL` and follow it exactly.

Or paste everything below the line.

---

Set up Mr_Deepseeker for me. Do every step yourself. The only thing you need from me is a DeepSeek API key, and I'll type that into a file myself in step 3. Never ask me to paste the key in chat. Don't ask me anything else unless a step fails.

**0. Pick the install location**
- If you are **Claude Code**, use `SKILL_DIR=~/.claude/skills/Mr_Deepseeker`. You'll install it as a skill and a subagent.
- Any **other agent** (Codex, GPT, Cursor, Gemini, ...) uses `SKILL_DIR=~/.mr_deepseeker`. You'll install it as a local package and add routing notes to your instructions file.

In every step below, write `SKILL_DIR` out as the real absolute path.

**1. Check prerequisites**
- `python3 --version` must be 3.10 or newer. Stop and tell me if it's older. The package is stdlib-only, so there's nothing to pip install.
- `git` must be available.

**2. Get the code**
- If `SKILL_DIR/.git` exists, run `git -C SKILL_DIR pull --ff-only`.
- Otherwise run `git clone https://github.com/harry0537/Mr_Deepseeker.git SKILL_DIR`.
- Confirm that `SKILL_DIR/SKILL.md` and `SKILL_DIR/mr_deepseeker/` exist.

**3. Make the key file. I add the key myself.**
- If `SKILL_DIR/.env` does not exist, run `cp SKILL_DIR/.env.example SKILL_DIR/.env`. Never overwrite an existing `.env`.
- Run `chmod 600 SKILL_DIR/.env`. The file is gitignored, and the package loads it automatically.
- Give me the full path to the file. Tell me to open it in an editor, replace `paste-your-key-here` with my key from https://platform.deepseek.com/api_keys, save, and reply "done".
- Wait for "done". If I start pasting the key into chat, stop me and point me back to the file.
- Never `cat`, read, or print `.env`. To check my edit, run only this (it never prints the key):
  `python3 -c "import re,sys,pathlib;v=re.search(r'DEEPSEEK_API_KEY=(.*)',pathlib.Path(sys.argv[1]).read_text()).group(1).strip();print('set' if v and v!='paste-your-key-here' else 'NOT SET', v[:4], len(v))" SKILL_DIR/.env`
  If it prints `NOT SET`, ask me to edit the file again.
- Never copy the key anywhere else: not into a `.md` file, an agent or instructions file, git, or memory.

**4. Wire it in**

*Claude Code:* the skill is already live, because `SKILL_DIR/SKILL.md` is loaded from `~/.claude/skills`. Now write the subagent file `~/.claude/agents/deepseeker.md`:

````markdown
---
name: deepseeker
description: DeepSeek-powered worker. Route here FIRST for repo scanning, auditing, tracing flow, summarizing files/logs/codebases, multi-file understanding (>3 files), "find all X", "why failing", AND code tasks (new code, refactors, tests, docstrings, boilerplate, mechanical edits). Runs in an isolated context, so the main session never sees the raw files. Returns contract JSON.
tools: Read, Grep, Glob, Bash, Edit, Write
model: haiku
---

You are the Mr_Deepseeker worker. You drive the DeepSeek API through the local package. DeepSeek does the heavy reading and generation; YOU orchestrate and apply the results. Do NOT read large files into your own context when `summarize_file` can digest them.

## Package
Location: `SKILL_DIR`. The key loads automatically from the `.env` file in that folder.

```bash
cd SKILL_DIR && python3 - <<'EOF'
from mr_deepseeker import summarize_file, load_env
load_env()
print(summarize_file(open("/path/to/file.py").read(), filename="file.py"))
EOF
```

Functions (full signatures and workflows are in `SKILL_DIR/SKILL.md`):
- Understanding: `summarize_file`, `review_project`, `review_all`
- Generation: `generate`, `expand_stub`, `write_tests`, `write_docstrings`, `translate`
- Editing: `refactor`, `add_type_hints`, `fix_bugs`, `fix_bugs_surgical`
- Misc: `write_commit_message`

## Rules
- For files over 100 lines, run `summarize_file` first and work from the digest.
- Never send raw logs over 300 lines. Trim them with tail or grep first.
- Files over 300 lines are never rewritten whole, and the package enforces this. `fix_bugs` switches to surgical mode, which needs bug line numbers. `refactor` and `add_type_hints` need `line_range=(start, end)`, so loop over sections.
- Edit functions raise `ValueError` instead of returning bad code. When one raises, report the step as failed. Never hand-merge the model's text into the file yourself.
- After writing any `.py` file, run `ruff check <file> --select E,F,W --quiet` if ruff is installed, and report the result in `verification`.
- Be surgical: touch only what the task requires.
- Set `requires_claude_review: true` if the risk is high or critical, if the change touches auth, money, or concurrency, or if your confidence is below 0.6.

## Output contract (mandatory: your final message is this JSON)
The schema's source of truth is `SKILL_DIR/references/contract.md`. Read it before you return.
- `coverage`: the files actually sent, skipped, and truncated. `review_project()` computes this; copy it verbatim. `complete: false` means a PARTIAL audit, so never report it as clean.
- `engine`: the output of `last_engine()` from `mr_deepseeker.llm_client`. A bad key silently falls through to free models, so if this isn't deepseek-chat, set `requires_claude_review: true`.
- `verification` (code tasks only): what you actually ran and its verbatim output. `not_run` is an honest answer.
- `handoff`: "coder" | "debugger" | "architect" | "code-reviewer" | null. The main session dispatches; workers never spawn agents.
````

*Other agents:* there's no subagent. Instead, propose adding this block to your global instructions file, for example `~/.codex/AGENTS.md` for Codex or your tool's equivalent. Show me the block and ask before you write it:

```markdown
## Mr_Deepseeker (cheap DeepSeek worker)
Package at SKILL_DIR (stdlib Python; the key is in SKILL_DIR/.env and must never be printed).
Route file summarizing, repo audits, test/docstring/boilerplate generation, and mechanical refactors to it:
  cd SKILL_DIR && python3 -c "from mr_deepseeker import load_env, summarize_file; load_env(); ..."
Functions and workflows: SKILL_DIR/SKILL.md. Output contract: SKILL_DIR/references/contract.md.
Always report `last_engine()` from mr_deepseeker.llm_client. If it isn't deepseek-chat, flag the result.
Files over 300 lines: pass line_range to refactor/add_type_hints. A ValueError means the step failed; don't hand-merge.
```

**5. Smoke test (required, don't skip)**
```bash
cd SKILL_DIR && python3 - <<'EOF'
from mr_deepseeker import summarize_file, load_env
from mr_deepseeker.llm_client import last_engine
load_env()
print(summarize_file("def add(a, b):\n    return a + b\n", filename="t.py"))
print("ENGINE:", last_engine())
EOF
```
The test passes only if a summary prints AND `ENGINE` contains `deepseek`.
- `No API key set` means the `.env` edit didn't save. Go back to step 3.
- Any other engine means the key is wrong or has no credit. Tell me, and don't call the setup done.

**6. Wrap up**
Tell me:
- which files you created
- the masked key: first 4 characters and the length
- the engine the smoke test reported
- that I need to restart my agent so the new setup loads

Claude Code usage after the restart: say "use deepseeker to …", or run `/Mr_Deepseeker` for quick inline work. Optionally, offer to add this line to `~/.claude/CLAUDE.md`, and ask before you add it:
`Route repo scanning, file summarizing, audits and mechanical code tasks to the deepseeker agent first; Claude keeps architecture, review, and final decisions.`
