import re
from pathlib import Path

_SAFE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


class FileStore:
    def __init__(self, root: str = "./tmp") -> None:
        root_path = Path(root)
        root_path.mkdir(parents=True, exist_ok=True)
        self.root = root_path.resolve()

    def path_for(self, key: str) -> Path:
        if not key or not _SAFE_KEY_PATTERN.fullmatch(key):
            raise ValueError("invalid storage key")

        path = (self.root / key).resolve(strict=False)
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("invalid storage key") from exc
        return path
