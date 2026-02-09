from pathlib import Path


class FileStore:
    def __init__(self, root: str = "./tmp") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, key: str) -> Path:
        return self.root / key
