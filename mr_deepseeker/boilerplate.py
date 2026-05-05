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

from mr_deepseeker.llm_client import delegate_code

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
    parts = [f"Translate to {target_language}"]
    if context:
        parts.append(f" ({context})")
    parts.append(f":\n\n{code}")
    return delegate_code("".join(parts), system=_CODE_SYSTEM, max_tokens=max_tokens)
