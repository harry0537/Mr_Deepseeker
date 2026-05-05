import os
from pathlib import Path


def load_env(path: Path | None = None) -> None:
    """Load .env into os.environ. Skips blank lines, comments, and malformed entries."""
    if path is None:
        path = Path(__file__).parent.parent / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k or " " in k:
            continue
        os.environ.setdefault(k, v)
