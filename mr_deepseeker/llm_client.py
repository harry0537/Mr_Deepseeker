#!/usr/bin/env python3
"""
LLM delegation client — tries providers in priority order until one succeeds.

Priority: DeepSeek → Ollama (local) → OpenRouter → Groq

Set API keys in .env or environment variables. DeepSeek is the cheapest
and most capable for code review tasks.
"""
from __future__ import annotations
import os
import json
import urllib.request
import logging

logger = logging.getLogger(__name__)

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
OR_URL       = "https://openrouter.ai/api/v1/chat/completions"
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
OLLAMA_URL   = "http://localhost:11434/v1/chat/completions"

DEEPSEEK_MODEL = "deepseek-chat"

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
          system: str = "", max_tokens: int = 4096, timeout: int = 180) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = json.dumps({"model": model, "messages": messages, "max_tokens": max_tokens}).encode()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


def deepseek_ask(prompt: str, system: str = "", max_tokens: int = 4096,
                 model: str = DEEPSEEK_MODEL) -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY not set. Add it to .env")
    return _call(DEEPSEEK_URL, key, model, prompt, system, max_tokens)


def delegate_code(prompt: str, system: str = "", max_tokens: int = 4096) -> str:
    """
    Send prompt to best available LLM. Chain: DeepSeek → Ollama → OpenRouter → Groq.
    Raises RuntimeError if all providers fail.
    """
    last_exc: Exception | None = None

    # 1. DeepSeek
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if deepseek_key:
        try:
            return _call(DEEPSEEK_URL, deepseek_key, DEEPSEEK_MODEL, prompt, system, max_tokens)
        except Exception as e:
            logger.warning("DeepSeek failed: %s", e)
            last_exc = e

    # 2. Ollama (local)
    try:
        return _call(OLLAMA_URL, "", "qwen2.5:1.5b", prompt, system, max_tokens, timeout=60)
    except Exception as e:
        logger.warning("Ollama failed: %s", e)
        last_exc = e

    # 3. OpenRouter
    or_key = os.environ.get("OPENROUTER_API_KEY", "")
    if or_key:
        for model in OR_CODE_MODELS:
            try:
                return _call(OR_URL, or_key, model, prompt, system, max_tokens)
            except Exception as e:
                logger.warning("OpenRouter %s failed: %s", model, e)
                last_exc = e

    # 4. Groq
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if groq_key:
        for model in GROQ_CODE_MODELS:
            try:
                return _call(GROQ_URL, groq_key, model, prompt, system, max_tokens)
            except Exception as e:
                logger.warning("Groq %s failed: %s", model, e)
                last_exc = e

    raise RuntimeError(f"All LLM backends failed. Last error: {last_exc}")
