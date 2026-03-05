from __future__ import annotations

import os
from pathlib import Path
from threading import Lock

_ENV_LOCK = Lock()
_ENV_LOADED = False


def load_project_env() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return

    with _ENV_LOCK:
        if _ENV_LOADED:
            return
        for path in _candidate_env_paths():
            _load_env_file(path)
        _ENV_LOADED = True


def _candidate_env_paths() -> list[Path]:
    backend_root = Path(__file__).resolve().parents[1]
    repo_root = Path(__file__).resolve().parents[2]
    cwd = Path.cwd()

    candidates = [
        backend_root / ".env",
        repo_root / ".env",
        cwd / ".env",
    ]

    seen: set[Path] = set()
    ordered: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        ordered.append(resolved)
    return ordered


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value
