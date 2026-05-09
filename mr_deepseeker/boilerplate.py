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
import logging

from mr_deepseeker.llm_client import delegate_code

logger = logging.getLogger(__name__)

_MAX_INPUT_CHARS = 40_000  # ~10k tokens — warn above this


def _check_size(code: str, label: str = "input") -> None:
    if len(code) > _MAX_INPUT_CHARS:
        logger.warning(
            "%s is %d chars — may exceed LLM token limit and cause truncated output. "
            "Consider splitting into smaller chunks.",
            label, len(code)
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
        code = generate("dataclass for a trade order with BUY/SELL enum, price, quantity, timestamp")
        print(code)
    """
    prompt = f"Language: {language}\n\nTask: {task}"
    return delegate_code(prompt, system=_CODE_SYSTEM, max_tokens=max_tokens)


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
    return delegate_code("".join(parts), system=_CODE_SYSTEM, max_tokens=max_tokens)


def write_tests(code: str, context: str = "", max_tokens: int = 4096) -> str:
    """
    Generate a pytest test suite for the given code.

    Args:
        code:    source code to test
        context: optional hints (e.g. "mock the external API calls", "include edge cases")

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
    return delegate_code("".join(parts), system=_TEST_SYSTEM, max_tokens=max_tokens)


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
    return delegate_code(
        f"Add docstrings to all undocumented functions and classes:\n\n{code}",
        system=_DOCSTRING_SYSTEM,
        max_tokens=max_tokens,
    )


def translate(code: str, target_language: str, context: str = "", max_tokens: int = 4096) -> str:
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
    return delegate_code("".join(parts), system=_CODE_SYSTEM, max_tokens=max_tokens)


_REFACTOR_SYSTEM = (
    "You are an expert Python refactoring engine. "
    "Apply ONLY the requested changes — do not add features, do not change logic. "
    "Return the COMPLETE refactored file. No explanation, no markdown fences."
)

_TYPE_HINT_SYSTEM = (
    "You are a Python typing expert. "
    "Add PEP 484 type annotations to all function signatures and variable assignments that lack them. "
    "Do not change any logic. Return the COMPLETE annotated file. No markdown fences."
)

_FIX_SYSTEM = (
    "You are an expert Python bug fixer. "
    "Apply ALL listed fixes to the code. Do not change anything not mentioned in the fix list. "
    "Return the COMPLETE fixed file. No explanation, no markdown fences."
)

_SUMMARIZE_SYSTEM = (
    "You are a code summarizer. Given Python source code, produce a compact technical digest "
    "that another AI can use to understand the file without reading it in full. "
    "Include: purpose, public API (functions/classes with signatures + one-line description), "
    "key dependencies, important constants/config, known gotchas. "
    "Be terse. Max 40 lines. Plain text, no markdown."
)

_COMMIT_SYSTEM = (
    "You are a git commit message writer. "
    "Given a git diff, write a concise imperative-mood commit message (subject line ≤72 chars). "
    "Optionally add a bullet-point body if the diff is complex. "
    "Do NOT include Co-Authored-By lines. Return ONLY the commit message text."
)


def refactor(code: str, instructions: str, max_tokens: int = 4096) -> str:
    """
    Mechanically refactor code per instructions — no logic changes.

    Args:
        code:         Python source to refactor
        instructions: what to change (e.g. "rename foo→bar, extract helper for lines 40-60")

    Returns:
        Refactored code as a string.

    Example:
        new_code = refactor(src, "rename _internal_calc to _kelly_calc everywhere")
    """
    _check_size(code, "refactor input")
    return delegate_code(
        f"Instructions: {instructions}\n\nCode:\n\n{code}",
        system=_REFACTOR_SYSTEM,
        max_tokens=max_tokens,
    )


def add_type_hints(code: str, max_tokens: int = 4096) -> str:
    """
    Add PEP 484 type annotations to all unannotated functions/variables.

    Args:
        code: Python source code

    Returns:
        Same code with type hints added.

    Example:
        typed = add_type_hints(open("utils.py").read())
        open("utils.py", "w").write(typed)
    """
    _check_size(code, "add_type_hints input")
    return delegate_code(
        f"Add type hints to this Python file:\n\n{code}",
        system=_TYPE_HINT_SYSTEM,
        max_tokens=max_tokens,
    )


def fix_bugs(code: str, bugs: list[dict], context: str = "", max_tokens: int = 4096) -> str:
    """
    Apply a list of bug fixes (from review_project output) to source code.

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
    _check_size(code, "fix_bugs input")
    bug_lines = []
    for i, b in enumerate(bugs, 1):
        loc = f"{b.get('file', '?')}:{b.get('line', '?')}"
        bug_lines.append(
            f"{i}. [{b.get('severity','?').upper()}] {loc} — {b.get('description','')}"
            + (f"\n   FIX: {b['remediation']}" if b.get("remediation") else "")
        )
    fix_list = "\n".join(bug_lines)
    parts = [f"Apply these fixes:\n{fix_list}\n\n"]
    if context:
        parts.append(f"Additional context: {context}\n\n")
    parts.append(f"Code:\n\n{code}")
    return delegate_code("".join(parts), system=_FIX_SYSTEM, max_tokens=max_tokens)


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
    _check_size(code, "summarize_file input")
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
