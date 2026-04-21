from __future__ import annotations

import os
from datetime import datetime, timedelta

import pytest

from services.storage.output_store import LocalOutputStore, OutputObject, latest_object_name


def test_local_output_store_rejects_parent_traversal(tmp_path) -> None:
    store = LocalOutputStore(tmp_path / "outputs")
    with pytest.raises(ValueError, match="cannot include"):
        store.write_text("../escape.txt", "bad")


def test_local_output_store_read_missing_raises(tmp_path) -> None:
    store = LocalOutputStore(tmp_path / "outputs")
    with pytest.raises(FileNotFoundError):
        store.read_bytes("missing.txt")


def test_latest_object_name_uses_timestamp_order(tmp_path) -> None:
    store = LocalOutputStore(tmp_path / "outputs")
    first = store.write_text("a.txt", "a")
    second = store.write_text("b.txt", "b")
    old_time = (datetime.now() - timedelta(minutes=5)).timestamp()
    os.utime(first, (old_time, old_time))

    assert latest_object_name(store, pattern="*.txt") == "b.txt"
    assert second.endswith("b.txt")


def test_latest_object_name_returns_none_for_empty() -> None:
    assert latest_object_name(_MemoryStore([]), pattern="*.txt") is None


class _MemoryStore:
    def __init__(self, objects: list[OutputObject]) -> None:
        self._objects = objects

    def write_text(self, name: str, content: str, *, encoding: str = "utf-8") -> str:  # noqa: ARG002
        return name

    def read_bytes(self, name: str) -> bytes:  # noqa: ARG002
        return b""

    def list_objects(self, *, pattern: str = "*") -> list[OutputObject]:  # noqa: ARG002
        return self._objects

    def ensure_ready(self) -> None:
        return None
