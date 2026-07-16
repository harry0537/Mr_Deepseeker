import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Canonical key files (chmod 600) — fallback when a key isn't in .env/environ
_KEY_FILES = {
    "DEEPSEEK_API_KEY": "~/.deepseek_key",
    "OPENROUTER_API_KEY": "~/.openrouter_key",
    "OPENAI_API_KEY": "~/.openai_key",
    "GROQ_API_KEY": "~/.groq_key",
}


def load_env(path: Path | None = None) -> None:
    """Load .env into os.environ, then fall back to ~/.<service>_key files."""
    if path is None:
        path = Path(__file__).parent.parent / ".env"
    if path.exists():
        for lineno, raw in enumerate(path.read_text().splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                logger.warning(".env line %d skipped (no '='): %r", lineno, raw)
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            if not k:
                logger.warning(".env line %d skipped (empty key): %r", lineno, raw)
                continue
            if " " in k:
                logger.warning(
                    ".env line %d skipped (space in key %r): %r", lineno, k, raw
                )
                continue
            os.environ.setdefault(k, v)

    for var, keyfile in _KEY_FILES.items():
        if os.environ.get(var):
            continue
        p = Path(keyfile).expanduser()
        if p.exists():
            v = p.read_text().strip()
            if v:
                os.environ[var] = v
                logger.info("%s loaded from %s", var, keyfile)
