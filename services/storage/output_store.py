from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from config.runtime import RuntimeConfig


@dataclass(frozen=True)
class OutputObject:
    name: str
    updated_at: datetime | None = None


class OutputStore(Protocol):
    def write_text(self, name: str, content: str, *, encoding: str = "utf-8") -> str: ...

    def read_bytes(self, name: str) -> bytes: ...

    def list_objects(self, *, pattern: str = "*") -> list[OutputObject]: ...

    def ensure_ready(self) -> None: ...


def _validate_object_name(name: str) -> str:
    normalized = name.strip().lstrip("/")
    if not normalized:
        raise ValueError("Output object name cannot be empty.")
    if ".." in Path(normalized).parts:
        raise ValueError("Output object name cannot include '..'.")
    return normalized


def _latest(objects: list[OutputObject]) -> OutputObject | None:
    if not objects:
        return None
    return max(objects, key=lambda item: ((item.updated_at or datetime.min), item.name))


class LocalOutputStore:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, name: str) -> Path:
        safe_name = _validate_object_name(name)
        path = (self.root_dir / safe_name).resolve()
        if self.root_dir.resolve() not in path.parents and path != self.root_dir.resolve():
            raise ValueError("Output object path escapes output directory.")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def write_text(self, name: str, content: str, *, encoding: str = "utf-8") -> str:
        path = self._resolve(name)
        path.write_text(content, encoding=encoding)
        return str(path)

    def read_bytes(self, name: str) -> bytes:
        path = self._resolve(name)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(name)
        return path.read_bytes()

    def list_objects(self, *, pattern: str = "*") -> list[OutputObject]:
        if not self.root_dir.exists():
            return []
        out: list[OutputObject] = []
        for path in self.root_dir.iterdir():
            if not path.is_file():
                continue
            if not fnmatch.fnmatch(path.name, pattern):
                continue
            out.append(OutputObject(name=path.name, updated_at=datetime.fromtimestamp(path.stat().st_mtime)))
        return out

    def ensure_ready(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)


def latest_object_name(store: OutputStore, *, pattern: str) -> str | None:
    latest = _latest(store.list_objects(pattern=pattern))
    return latest.name if latest else None


def create_output_store(runtime: RuntimeConfig | None = None) -> OutputStore:
    runtime_cfg = runtime or RuntimeConfig.from_env()
    return LocalOutputStore(runtime_cfg.output_dir)
