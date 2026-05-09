#!/usr/bin/env python3
"""
LLM delegation client — tries providers in priority order until one succeeds.

Priority: DeepSeek(direct) → OpenRouter(deepseek-chat) → Ollama → OpenRouter(free) → Groq

Set API keys in .env or environment variables. DeepSeek is the cheapest
and most capable for code review tasks. OpenRouter acts as resilient fallback
for the same DeepSeek model when the direct API times out.
"""
from __future__ import annotations
import os
import json
import random
import threading
import time
import urllib.request
import urllib.error
import logging

logger = logging.getLogger(__name__)

# Limit concurrent outbound API calls across threads (review_all runs 3 threads)
_API_SEMAPHORE = threading.Semaphore(2)

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
OR_URL       = "https://openrouter.ai/api/v1/chat/completions"
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
OLLAMA_URL   = "http://localhost:11434/v1/chat/completions"

DEEPSEEK_MODEL = "deepseek-chat"

OR_DEEPSEEK_MODEL = "deepseek/deepseek-chat"  # paid — same model, OR's infra

OR_CODE_MODELS = [
    "qwen/qwen3-coder:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
]

GROQ_CODE_MODELS = [
    "llama-3.3-70b-versatile",
    "qwen/qwen3-32b",
    "llama-3.1-8b-instant",
]


def _call(url: str, api_key: str, model: str, prompt: str,
          system: str = "", max_tokens: int = 4096, timeout: int = 180,
          retries: int = 2) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = json.dumps({"model": model, "messages": messages, "max_tokens": max_tokens}).encode()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    last_exc: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
            if "error" in data:
                raise RuntimeError(f"API error: {data['error']}")
            choices = data.get("choices") or []
            if not choices:
                raise RuntimeError(f"Empty choices in response: {data}")
            return choices[0]["message"]["content"]
        except urllib.error.HTTPError as e:
            if e.code < 500:
                raise  # 4xx — client error, no point retrying
            last_exc = e
            logger.warning("HTTP %d from %s (attempt %d/%d)", e.code, url, attempt + 1, retries)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_exc = e
            logger.warning("Network error %s (attempt %d/%d): %s", url, attempt + 1, retries, e)

        if attempt < retries - 1:
            backoff = (2 ** attempt) + random.uniform(0, 1)
            logger.info("Retrying in %.1fs...", backoff)
            time.sleep(backoff)

    raise RuntimeError(f"Failed after {retries} attempts: {last_exc}")


def deepseek_ask(prompt: str, system: str = "", max_tokens: int = 4096,
                 model: str = DEEPSEEK_MODEL) -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY not set. Add it to .env")
    return _call(DEEPSEEK_URL, key, model, prompt, system, max_tokens)


def delegate_code(prompt: str, system: str = "", max_tokens: int = 4096) -> str:
    """
    Send prompt to best available LLM. Chain: DeepSeek → Ollama → OpenRouter → Groq.
    Semaphore-gated to max 2 concurrent outbound calls (safe for review_all parallelism).
    Raises RuntimeError if all providers fail.
    """
    with _API_SEMAPHORE:
        return _delegate_code_inner(prompt, system, max_tokens)


def _delegate_code_inner(prompt: str, system: str, max_tokens: int) -> str:
    last_exc: Exception | None = None

    or_key = os.environ.get("OPENROUTER_API_KEY", "")

    # 1. DeepSeek direct — short timeout so fallback kicks in fast
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if deepseek_key:
        try:
            return _call(DEEPSEEK_URL, deepseek_key, DEEPSEEK_MODEL, prompt, system,
                         max_tokens, timeout=60, retries=1)
        except Exception as e:
            logger.warning("DeepSeek(direct) failed: %s", e)
            last_exc = e

    # 2. OpenRouter → deepseek-chat (same model, more reliable infra)
    if or_key:
        try:
            return _call(OR_URL, or_key, OR_DEEPSEEK_MODEL, prompt, system,
                         max_tokens, timeout=90, retries=2)
        except Exception as e:
            logger.warning("OpenRouter(deepseek-chat) failed: %s", e)
            last_exc = e

    # 3. Ollama (local) — model configurable via OLLAMA_MODEL env var
    ollama_model = os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b")
    try:
        return _call(OLLAMA_URL, "", ollama_model, prompt, system, max_tokens, timeout=60, retries=1)
    except Exception as e:
        logger.warning("Ollama/%s failed: %s", ollama_model, e)
        last_exc = e

    # 4. OpenRouter free models
    if or_key:
        for model in OR_CODE_MODELS:
            try:
                return _call(OR_URL, or_key, model, prompt, system, max_tokens)
            except Exception as e:
                logger.warning("OpenRouter %s failed: %s", model, e)
                last_exc = e

    # 5. Groq
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if groq_key:
        for model in GROQ_CODE_MODELS:
            try:
                return _call(GROQ_URL, groq_key, model, prompt, system, max_tokens)
            except Exception as e:
                logger.warning("Groq %s failed: %s", model, e)
                last_exc = e

    raise RuntimeError(f"All LLM backends failed. Last error: {last_exc}")
