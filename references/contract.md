# Mr_Deepseeker Output Contract — SINGLE SOURCE OF TRUTH

Every Mr_Deepseeker / deepseeker task returns ONE of these JSON objects as its
final message. No freeform prose. Anything that disagrees with this file
(agent frontmatter, SKILL.md, docstrings) is stale — fix it here first, then
point the copy at this file.

## Investigation tasks

```json
{
  "objective": "what was investigated",
  "summary": "2-3 sentence finding",
  "root_cause": "specific cause if found, else null",
  "confidence": 0.0,
  "affected_files": ["relative/path/file.py"],
  "affected_functions": ["module.function_name"],
  "evidence": ["snippet or log line supporting the finding"],
  "recommended_actions": ["concrete action 1"],
  "risk_level": "low|medium|high|critical",
  "requires_claude_review": false,
  "handoff": null,
  "coverage": {"files_sent": [], "files_skipped": [], "files_truncated": [],
               "complete": true},
  "engine": "api.deepseek.com/deepseek-chat"
}
```

## Code tasks

```json
{
  "files_modified": [],
  "changes_made": [],
  "tests_added": [],
  "known_risks": [],
  "rollback_strategy": "",
  "confidence": 0.0,
  "requires_claude_review": false,
  "handoff": null,
  "verification": {"ruff": "pass|fail|not_run", "tests": "pass|fail|not_run",
                   "ran": "the command you actually ran", "output": ""},
  "engine": "api.deepseek.com/deepseek-chat"
}
```

## coverage — MANDATORY on any task that read files

`review_project()` returns `coverage` and `engine` computed by the process, not
by the model. Copy them into the contract verbatim.

- `files_sent` — what the model actually saw.
- `files_skipped` — hit the `max_files` cap (default 20) or failed to read.
- `files_truncated` — over 300 lines, cut at a def/class boundary.
- `complete` — false if either list is non-empty.

`complete` is also false when `parse_ok` is false — the model returned something
unparseable and `bugs: []` means "no answer", not "no bugs". Never report that as
a clean audit.

If `complete` is false the audit is PARTIAL. Say so in `summary` and never call
it clean. For a folder past the cap: raise `max_files`, or review in batches and
merge — do not report on the first 20 files as if they were the repo.

Reading files by hand (Read/grep) instead of `review_project`? Fill `coverage`
yourself with what you opened.

## engine — MANDATORY on every task

`last_engine()` (from `mr_deepseeker.llm_client`) gives `host/model` of the
provider that actually answered. The chain falls through on failure:

    DeepSeek(direct) → OpenRouter(deepseek-chat) → OpenAI(gpt-4o-mini)
    → OpenRouter(free models) → Groq(llama-3.3-70b / qwen3-32b / llama-3.1-8b)

A dead or revoked DeepSeek key falls all the way to a free 8B model without
raising. Unreported, that answer reads exactly like deepseek-chat. Always stamp
it. If `engine` is not a `deepseek-chat` entry, set
`requires_claude_review: true`.

## verification — MANDATORY on code tasks

"Done" means run, not written. Before returning a code contract:

```bash
ruff check <file> --select E,F,W --quiet
mypy <file> --ignore-missing-imports --no-error-summary
# plus the project's tests if any exist
```

Report failures verbatim in `verification.output`. `not_run` is allowed and
honest; a false `pass` is not. Main session treats `not_run` as untrusted.

## handoff

`"coder" | "debugger" | "architect" | "code-reviewer" | null` — the main session
dispatches. Workers never spawn agents.

## requires_claude_review: true when

- `risk_level` is high or critical
- touches trading execution, concurrency, auth, or money
- `confidence` < 0.6
- `coverage.complete` is false
- `engine` is not deepseek-chat
- finding contradicts known architecture
