"""Worker configuration. Secrets come from environment variables only (GitHub Secrets in CI)."""
from __future__ import annotations

import os
from pathlib import Path

USER_AGENT = "LiveShowRadarBot/0.1 (concert alert prototype)"
ROBOTS_TOKEN = "LiveShowRadarBot"
REQUEST_TIMEOUT = 15          # seconds
MAX_BYTES = 2_000_000         # per fetched page
MIN_HOST_DELAY = 2.0          # seconds between requests to the same host
MAX_REDIRECTS = 3
# Bump when extraction logic changes: pages are re-processed once even if their content is unchanged.
EXTRACTOR_VERSION = "5"
DEFAULT_SOURCE_LIMIT = 300    # followed-artist + promoter sources checked per run
DEFAULT_CATALOG_LIMIT = 25    # other catalog artists' sources checked per run (each at most once a day)


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError("Missing required environment variable: " + name)
    return value


def load_env_file(path: str = ".env.local") -> None:
    """Local-dev convenience: load KEY=VALUE lines without overriding real environment variables."""
    p = Path(path)
    if not p.is_file():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def flag(name: str) -> bool:
    return os.environ.get(name, "").strip() == "1"
