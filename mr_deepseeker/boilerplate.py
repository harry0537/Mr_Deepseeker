#!/usr/bin/env python3
"""
Boilerplate generation — offload mechanical code tasks to DeepSeek
so your Claude session budget goes to the thinking work, not the typing work.

generate(task)           — generate any code from a description
expand_stub(code)        — take a stub/skeleton and fill it out fully
write_tests(code)        — generate pytest tests for given code
write_docstrings(code)   — add docstrings to all functions in a file
translate(code, lang)    — rewrite code in another language
"""
from __future__ import annotations
import ast
import logging
import re
from collections import Counter

from mr_deepseeker.llm_client import delegate_code

logger = logging.getLogger(__name__)

_MAX_INPUT_CHARS = 40_000  # ~10k tokens — warn above this
_MAX_OUTPUT_TOKENS = 8192  # deepseek-chat hard output cap
# House rule: no worker rewrites a file above this many lines whole. Bigger files
# go through _splice (one line range at a time) or the caller gets an error.
_MAX_WHOLE_FILE_LINES = 300


def _strip_fences(text: str) -> str:
    """Strip a wrapping markdown code fence the model added despite instructions."""
    t = text.strip()
    if not t.startswith("```"):
        return text
    first_nl = t.find("\n")
    if first_nl == -1:
        return text
    body = t[first_nl + 1:]
    stripped = body.rstrip()
    if stripped.endswith("```"):
        body = stripped[:-3].rstrip("\n") + "\n"
    return body


def _full_file_max_tokens(code: str, requested: int) -> int:
    """Full-file ops must fit the whole file in the response — scale cap to input."""
    needed = len(code) // 3 + 512
    if needed > _MAX_OUTPUT_TOKENS:
        logger.warning(
            "Input (%d chars) likely exceeds the %d-token output cap — full-file "
            "result may truncate. Use fix_bugs_surgical or split the file.",
            len(code), _MAX_OUTPUT_TOKENS,
        )
    return min(_MAX_OUTPUT_TOKENS, max(requested, needed))


def _check_size(code: str, label: str = "input") -> None:
    if len(code) > _MAX_INPUT_CHARS:
        logger.warning(
            "%s is %d chars — may exceed LLM token limit and cause truncated output. "
            "Consider splitting into smaller chunks.",
            label, len(code)
        )

def _too_big_for_whole_file(code: str) -> bool:
    return len(code.splitlines()) > _MAX_WHOLE_FILE_LINES


def _check_python(result: str, original: str, what: str) -> str:
    """Refuse model output that no longer parses — the caller gets nothing to write.

    Skipped when the original did not parse either: there is no baseline to hold
    the edit to, and refusing would make broken files unfixable.
    """
    try:
        ast.parse(original)
    except SyntaxError:
        logger.warning("%s: original does not parse — syntax guard skipped", what)
        return result
    try:
        ast.parse(result)
    except SyntaxError as e:
        raise ValueError(
            f"{what}: model output is not valid Python "
            f"(line {e.lineno}: {e.msg}) — nothing applied"
        ) from e
    return result


_DEF_RE = re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+(\w+)", re.MULTILINE)


def _def_names(src: str) -> Counter[str]:
    # Counter, not set: two classes' __init__ collapse to one set member, so
    # dropping one of them would pass the guard.
    return Counter(_DEF_RE.findall(src))


def _edge_blanks(lines: list[str], tail: bool = False) -> list[str]:
    seq = reversed(lines) if tail else iter(lines)
    blanks = []
    for ln in seq:
        if ln.strip():
            break
        blanks.append(ln)
    return blanks[::-1] if tail else blanks


def _strip_edge_blanks(lines: list[str]) -> list[str]:
    start, end = 0, len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return lines[start:end]


def _splice(
    code: str, start0: int, end0: int, request: str, max_tokens: int, what: str
) -> str:
    """Send lines start0..end0 (0-indexed, inclusive) with `request`, splice the
    answer back, and return the whole file — only if it still parses."""
    lines = code.splitlines(keepends=True)
    snippet = "".join(lines[start0:end0 + 1])
    out = _strip_fences(delegate_code(
        f"{request}\n\nThis is lines {start0 + 1}-{end0 + 1} of a larger file. "
        f"Return ONLY the rewritten snippet, same indentation.\n\n"
        f"Snippet:\n{snippet}",
        system=_SNIPPET_SYSTEM, max_tokens=max_tokens,
    ))
    if not out.strip():
        raise ValueError(f"{what}: empty response for lines {start0 + 1}-{end0 + 1}")
    # The window is padded past the target function, so it usually holds
    # neighbours too. A model that answers with only the function it fixed
    # deletes them — and the file still parses. Every def/class that went in
    # must come back out.
    lost = list((_def_names(snippet) - _def_names(out)).elements())
    if lost:
        raise ValueError(
            f"{what}: lines {start0 + 1}-{end0 + 1} came back without "
            f"{sorted(lost)} — nothing applied"
        )
    new_lines = out.splitlines(keepends=True)
    if not new_lines[-1].endswith("\n"):
        new_lines[-1] += "\n"
    # Models strip blank lines at the window edges, which eats the two-line gap
    # between top-level defs (observed live). Put the original edges back.
    new_lines = (_edge_blanks(lines[start0:end0 + 1])
                 + _strip_edge_blanks(new_lines)
                 + _edge_blanks(lines[start0:end0 + 1], tail=True))
    result = "".join(lines[:start0] + new_lines + lines[end0 + 1:])
    return _check_python(result, code, f"{what} lines {start0 + 1}-{end0 + 1}")


def _line_range_splice(
    code: str, line_range: tuple[int, int], request: str, max_tokens: int, what: str
) -> str:
    start, end = line_range
    n = len(code.splitlines())
    if not 1 <= start <= end <= n:
        raise ValueError(f"{what}: line_range {line_range} outside 1-{n}")
    return _splice(code, start - 1, end - 1, request, max_tokens, what)


def _refuse_whole_file(code: str, what: str) -> None:
    if _too_big_for_whole_file(code):
        raise ValueError(
            f"{what}: file is {len(code.splitlines())} lines (> "
            f"{_MAX_WHOLE_FILE_LINES}) — pass line_range=(start, end) to edit one "
            f"section at a time; whole-file rewrites truncate and corrupt"
        )


_CODE_SYSTEM = (
    "You are an expert programmer. Return ONLY the requested code — "
    "no explanation, no markdown fences, no preamble. "
    "The output will be written directly to a file."
)

_TEST_SYSTEM = (
    "You are an expert at writing pytest test suites. "
    "Return ONLY valid Python test code using pytest. "
    "No explanation, no markdown fences."
)

_DOCSTRING_SYSTEM = (
    "You are a Python documentation expert. "
    "Add concise one-line docstrings to all functions and classes that lack them. "
    "Return the COMPLETE file with docstrings added. No other changes."
)


def generate(task: str, language: str = "python", max_tokens: int = 4096) -> str:
    """
    Generate code for a task description.

    Args:
        task:      what to build (e.g. "async rate limiter with token bucket algorithm")
        language:  target language (default: python)
        max_tokens: response length cap

    Returns:
        Generated code as a string.

    Example:
        code = generate("dataclass for a trade order: BUY/SELL enum, price, qty, ts")
        print(code)
    """
    prompt = f"Language: {language}\n\nTask: {task}"
    return _strip_fences(
        delegate_code(prompt, system=_CODE_SYSTEM, max_tokens=max_tokens)
    )


def expand_stub(code: str, context: str = "", max_tokens: int = 4096) -> str:
    """
    Take a stub or skeleton and fill it out completely.

    Args:
        code:    stub code with TODOs, pass statements, or incomplete logic
        context: optional extra instructions (e.g. "use asyncio, no third-party libs")

    Returns:
        Fully implemented code.

    Example:
        stub = '''
        def calculate_kelly_fraction(win_rate: float, win_loss_ratio: float) -> float:
            # TODO: implement Kelly criterion
            pass
        '''
        full = expand_stub(stub, context="clamp result to [0, 0.25]")
    """
    _check_size(code, "expand_stub input")
    parts = []
    if context:
        parts.append(f"Requirements: {context}\n\n")
    parts.append(f"Complete this implementation:\n\n{code}")
    max_tokens = _full_file_max_tokens(code, max_tokens)
    return _strip_fences(
        delegate_code("".join(parts), system=_CODE_SYSTEM, max_tokens=max_tokens)
    )


def write_tests(code: str, context: str = "", max_tokens: int = 4096) -> str:
    """
    Generate a pytest test suite for the given code.

    Args:
        code:    source code to test
        context: optional hints (e.g. "mock external API calls", "include edge cases")

    Returns:
        pytest test file as a string.

    Example:
        tests = write_tests(open("my_module.py").read(), context="mock network calls")
        open("test_my_module.py", "w").write(tests)
    """
    _check_size(code, "write_tests input")
    parts = []
    if context:
        parts.append(f"Testing requirements: {context}\n\n")
    parts.append(f"Write a complete pytest test suite for:\n\n{code}")
    return _strip_fences(
        delegate_code("".join(parts), system=_TEST_SYSTEM, max_tokens=max_tokens)
    )


def write_docstrings(code: str, max_tokens: int = 4096) -> str:
    """
    Add one-line docstrings to all undocumented functions and classes.

    Args:
        code: Python source code

    Returns:
        Same code with docstrings added.

    Example:
        src = open("utils.py").read()
        documented = write_docstrings(src)
        open("utils.py", "w").write(documented)
    """
    _check_size(code, "write_docstrings input")
    return _strip_fences(delegate_code(
        f"Add docstrings to all undocumented functions and classes:\n\n{code}",
        system=_DOCSTRING_SYSTEM,
        max_tokens=_full_file_max_tokens(code, max_tokens),
    ))


def translate(
    code: str, target_language: str, context: str = "", max_tokens: int = 4096
) -> str:
    """
    Rewrite code in another language, preserving logic exactly.

    Args:
        code:            source code in any language
        target_language: language to translate to (e.g. "TypeScript", "Go", "Rust")
        context:         optional hints (e.g. "use idiomatic Go, no generics")

    Returns:
        Translated code as a string.

    Example:
        go_code = translate(python_code, "Go", context="use standard library only")
    """
    _check_size(code, "translate input")
    parts = [f"Translate to {target_language}"]
    if context:
        parts.append(f" ({context})")
    parts.append(f":\n\n{code}")
    max_tokens = _full_file_max_tokens(code, max_tokens)
    return _strip_fences(
        delegate_code("".join(parts), system=_CODE_SYSTEM, max_tokens=max_tokens)
    )


_REFACTOR_SYSTEM = (
    "You are an expert Python refactoring engine. "
    "Apply ONLY the requested changes — do not add features, do not change logic. "
    "Return the COMPLETE refactored file. No explanation, no markdown fences."
)

_TYPE_HINT_SYSTEM = (
    "You are a Python typing expert. "
    "Add PEP 484 type annotations to all function signatures and variable "
    "assignments that lack them. "
    "Do not change any logic. Return the COMPLETE annotated file. No markdown fences."
)

_FIX_SYSTEM = (
    "You are an expert Python bug fixer. "
    "Apply ALL listed fixes to the code. "
    "Do not change anything not mentioned in the fix list. "
    "Return the COMPLETE fixed file. No explanation, no markdown fences."
)

_SNIPPET_SYSTEM = (
    "You are an expert Python editor working on ONE SECTION of a larger file. "
    "Apply only the requested change to the snippet you are given. "
    "Return ONLY that snippet, rewritten — not the whole file, keep its original "
    "indentation. No explanation, no markdown fences."
)

_SUMMARIZE_SYSTEM = (
    "You are a code summarizer. Given Python source code, produce a compact "
    "technical digest that another AI can use to understand the file without "
    "reading it in full. "
    "Include: purpose, public API (functions/classes, signatures, one-liner), "
    "key dependencies, important constants/config, known gotchas. "
    "Be terse. Max 40 lines. Plain text, no markdown."
)

_COMMIT_SYSTEM = (
    "You are a git commit message writer. "
    "Given a git diff, write a concise imperative-mood commit message "
    "(subject line ≤72 chars). "
    "Optionally add a bullet-point body if the diff is complex. "
    "Do NOT include Co-Authored-By lines. Return ONLY the commit message text."
)


def refactor(
    code: str,
    instructions: str,
    max_tokens: int = 4096,
    line_range: tuple[int, int] | None = None,
) -> str:
    """
    Mechanically refactor code per instructions — no logic changes.

    Args:
        code:         Python source to refactor
        instructions: what to change (e.g. "rename foo→bar, extract helper 40-60")
        line_range:   (start, end) 1-indexed inclusive — rewrite only that section.
                      REQUIRED for files over 300 lines.

    Returns:
        Refactored code (full file) as a string.

    Raises:
        ValueError: file too big without line_range, or the result does not parse.

    Example:
        new_code = refactor(src, "rename _internal_calc to _kelly_calc everywhere")
        new_code = refactor(src, "extract the retry loop", line_range=(120, 180))
    """
    if line_range:
        return _line_range_splice(
            code, line_range, f"Refactor (no logic changes): {instructions}",
            max(max_tokens, 4096), "refactor",
        )
    _refuse_whole_file(code, "refactor")
    _check_size(code, "refactor input")
    return _check_python(_strip_fences(delegate_code(
        f"Instructions: {instructions}\n\nCode:\n\n{code}",
        system=_REFACTOR_SYSTEM,
        max_tokens=_full_file_max_tokens(code, max_tokens),
    )), code, "refactor")


def add_type_hints(
    code: str, max_tokens: int = 4096, line_range: tuple[int, int] | None = None
) -> str:
    """
    Add PEP 484 type annotations to all unannotated functions/variables.

    Args:
        code:       Python source code
        line_range: (start, end) 1-indexed inclusive — annotate only that section.
                    REQUIRED for files over 300 lines.

    Returns:
        Same code (full file) with type hints added.

    Raises:
        ValueError: file too big without line_range, or the result does not parse.

    Example:
        typed = add_type_hints(open("utils.py").read())
        open("utils.py", "w").write(typed)
    """
    if line_range:
        return _line_range_splice(
            code, line_range,
            "Add PEP 484 type annotations where missing. Do not change logic.",
            max(max_tokens, 4096), "add_type_hints",
        )
    _refuse_whole_file(code, "add_type_hints")
    _check_size(code, "add_type_hints input")
    return _check_python(_strip_fences(delegate_code(
        f"Add type hints to this Python file:\n\n{code}",
        system=_TYPE_HINT_SYSTEM,
        max_tokens=_full_file_max_tokens(code, max_tokens),
    )), code, "add_type_hints")


def _bug_lines_prompt(bugs: list[dict]) -> str:
    parts = []
    for i, b in enumerate(bugs, 1):
        loc = f"{b.get('file', '?')}:{b.get('line', '?')}"
        parts.append(
            f"{i}. [{b.get('severity','?').upper()}] {loc} — {b.get('description','')}"
            + (f"\n   FIX: {b['remediation']}" if b.get("remediation") else "")
        )
    return "\n".join(parts)


def _extract_enclosing_function(
    lines: list[str], target_1idx: int, pad: int = 10
) -> tuple[int, int]:
    """Return (start, end) 0-indexed range of the function around target_1idx."""
    n = len(lines)
    t = min(target_1idx - 1, n - 1)

    # Walk back to find enclosing def/class
    func_start = max(0, t - pad)
    for i in range(t, -1, -1):
        s = lines[i].lstrip()
        if s.startswith(("def ", "async def ", "class ")):
            func_start = i
            break

    # Walk forward: stop at a same-or-lower indent def/class after the body starts
    func_indent = len(lines[func_start]) - len(lines[func_start].lstrip())
    func_end = min(n - 1, t + pad)
    for i in range(func_start + 2, n):
        s = lines[i].lstrip()
        if s and not s.startswith("#"):
            indent = len(lines[i]) - len(s)
            if indent <= func_indent and s.startswith(("def ", "async def ", "class ")):
                func_end = i - 1
                break
    else:
        func_end = n - 1

    # Add a small buffer
    return max(0, func_start - 3), min(n - 1, func_end + 3)


def fix_bugs_surgical(
    code: str, bugs: list[dict], context: str = "", max_tokens: int = 8192
) -> str:
    """
    Fix bugs by sending only the affected code sections to DeepSeek.
    Safe for large files that exceed token limits in full-file mode.

    Groups bugs by proximity, extracts the enclosing function for each group,
    fixes it independently, then splices the result back into the original file.

    Args:
        code:      full Python source
        bugs:      list of bug dicts (file, line, description, remediation)
        context:   optional extra instructions
        max_tokens: response length cap per chunk

    Returns:
        Fixed source code (full file).
    """
    lines = code.splitlines(keepends=True)
    n = len(lines)

    # Collect (line_number_1idx, bug) pairs, skip bugs with no line.
    # Line numbers often arrive as strings (parsed from "file.py:42") — coerce.
    located: list[tuple[int, dict]] = []
    for b in bugs:
        try:
            ln = int(str(b.get("line")).strip())
        except (TypeError, ValueError):
            continue
        if 1 <= ln <= n:
            located.append((ln, b))

    if not located:
        # No line info. Calling fix_bugs() here recursed forever on big files
        # (fix_bugs -> surgical -> fix_bugs ...); go straight to the full path.
        if _too_big_for_whole_file(code):
            raise ValueError(
                f"fix_bugs_surgical: no bug has a usable line number and the file "
                f"is {n} lines — add line numbers, can't rewrite it whole"
            )
        logger.warning(
            "fix_bugs_surgical: no line numbers — falling back to full-file fix"
        )
        return _fix_bugs_full(code, bugs, context=context, max_tokens=max_tokens)

    # Sort by line, then group bugs whose enclosing functions overlap
    located.sort(key=lambda x: x[0])
    groups: list[tuple[int, int, list[dict]]] = []  # (start_0idx, end_0idx, bugs)
    for ln, bug in located:
        s, e = _extract_enclosing_function(lines, ln)
        merged = False
        for i, (gs, ge, gblist) in enumerate(groups):
            if s <= ge and e >= gs:  # overlapping ranges — merge
                groups[i] = (min(gs, s), max(ge, e), gblist + [bug])
                merged = True
                break
        if not merged:
            groups.append((s, e, [bug]))

    # Fix each group independently and splice back. All-or-nothing: any group
    # that comes back empty or unparseable raises, so the caller never writes a
    # file with some fixes silently dropped.
    # Reverse order so earlier line indices stay valid after splicing.
    result = code
    for gs, ge, gblist in sorted(groups, key=lambda x: x[0], reverse=True):
        request = f"Apply these fixes:\n{_bug_lines_prompt(gblist)}"
        if context:
            request += f"\n\nContext: {context}"
        result = _splice(result, gs, ge, request, max_tokens, "fix_bugs_surgical")
        logger.info(
            "fix_bugs_surgical: patched lines %d-%d (%d bugs)",
            gs + 1, ge + 1, len(gblist),
        )

    return result


def fix_bugs(
    code: str, bugs: list[dict], context: str = "", max_tokens: int = 4096
) -> str:
    """
    Apply a list of bug fixes (from review_project output) to source code.
    Automatically uses surgical (chunk) mode for large files.

    Args:
        code:    Python source code to fix
        bugs:    list of bug dicts with keys: file, line, description, remediation
        context: optional extra instructions

    Returns:
        Fixed source code.

    Example:
        result = review_project("/path/to/bot")
        critical = [b for b in result["bugs"] if b["severity"] in ("critical", "high")]
        fixed = fix_bugs(open("bot.py").read(), critical)
    """
    if _too_big_for_whole_file(code):
        logger.info(
            "fix_bugs: %d lines (> %d) — switching to surgical mode",
            len(code.splitlines()), _MAX_WHOLE_FILE_LINES,
        )
        return fix_bugs_surgical(
            code, bugs, context=context, max_tokens=max(max_tokens, 8192)
        )
    return _fix_bugs_full(code, bugs, context=context, max_tokens=max_tokens)


def _fix_bugs_full(
    code: str, bugs: list[dict], context: str = "", max_tokens: int = 4096
) -> str:
    """Whole-file fix — small files only (see _MAX_WHOLE_FILE_LINES)."""
    fix_list = _bug_lines_prompt(bugs)
    parts = [f"Apply these fixes:\n{fix_list}\n\n"]
    if context:
        parts.append(f"Additional context: {context}\n\n")
    parts.append(f"Code:\n\n{code}")
    max_tokens = _full_file_max_tokens(code, max_tokens)
    return _check_python(_strip_fences(
        delegate_code("".join(parts), system=_FIX_SYSTEM, max_tokens=max_tokens)
    ), code, "fix_bugs")


def _chunk_summarize(code: str, filename: str, max_tokens: int) -> str:
    """Summarize a large file by chunking, summarizing each chunk, then synthesizing."""
    chunk_size = 35_000
    lines = code.splitlines(keepends=True)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in lines:
        if current_len + len(line) > chunk_size and current:
            chunks.append("".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += len(line)
    if current:
        chunks.append("".join(current))

    chunk_digests = []
    for i, chunk in enumerate(chunks):
        header = f"File: {filename} (part {i+1}/{len(chunks)})\n\n"
        digest = delegate_code(
            f"{header}{chunk}", system=_SUMMARIZE_SYSTEM, max_tokens=max_tokens
        )
        chunk_digests.append(digest)

    if len(chunk_digests) == 1:
        return chunk_digests[0]

    combined = "\n\n---\n\n".join(
        f"[Part {i+1}]\n{d}" for i, d in enumerate(chunk_digests)
    )
    synthesis_prompt = (
        f"File: {filename}\n\n"
        f"Below are summaries of {len(chunks)} chunks of the same file. "
        f"Produce ONE unified compact digest covering the full file.\n\n{combined}"
    )
    return delegate_code(
        synthesis_prompt, system=_SUMMARIZE_SYSTEM, max_tokens=max_tokens
    )


def summarize_file(code: str, filename: str = "", max_tokens: int = 1024) -> str:
    """
    Return a compact digest of a file — use instead of Read when Claude needs
    to understand a file without consuming full context.

    Args:
        code:     Python source code
        filename: optional filename for context

    Returns:
        Compact text summary (≤40 lines).

    Example:
        digest = summarize_file(open("alpaca_bot.py").read(), "alpaca_bot.py")
        # Pass digest to Claude instead of the full 400-line file
    """
    if len(code) > _MAX_INPUT_CHARS:
        logger.info(
            "summarize_file: %s is %d chars — auto-chunking",
            filename or "input", len(code),
        )
        return _chunk_summarize(code, filename, max_tokens)
    header = f"File: {filename}\n\n" if filename else ""
    return delegate_code(
        f"{header}{code}",
        system=_SUMMARIZE_SYSTEM,
        max_tokens=max_tokens,
    )


def write_commit_message(diff: str, context: str = "", max_tokens: int = 512) -> str:
    """
    Generate a git commit message from a diff.

    Args:
        diff:    output of `git diff` or `git diff --staged`
        context: optional hint (e.g. "this fixes the Kelly sizing bug")

    Returns:
        Commit message string (subject + optional body).

    Example:
        import subprocess
        diff = subprocess.check_output(["git", "diff", "--staged"], text=True)
        msg = write_commit_message(diff)
        subprocess.run(["git", "commit", "-m", msg])
    """
    _check_size(diff, "write_commit_message diff")
    parts = []
    if context:
        parts.append(f"Context: {context}\n\n")
    parts.append(f"Git diff:\n\n{diff}")
    return delegate_code("".join(parts), system=_COMMIT_SYSTEM, max_tokens=max_tokens)
