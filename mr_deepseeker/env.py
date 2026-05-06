import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def load_env(path: Path | None = None) -> None:
    """Load .env into os.environ. Skips blank lines, comments, and malformed entries."""
    if path is None:
        path = Path(__file__).parent.parent / ".env"
    if not path.exists():
        return
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
            logger.warning(".env line %d skipped (space in key %r): %r", lineno, k, raw)
            continue
        os.environ.setdefault(k, v)
