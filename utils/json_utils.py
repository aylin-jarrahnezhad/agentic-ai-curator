import json
import logging
from pathlib import Path
from typing import Any, TypeAlias

logger = logging.getLogger(__name__)

JSONScalar: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]


def _existing_json_nonempty(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        old = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if isinstance(old, list):
        return len(old) > 0
    if isinstance(old, dict):
        return len(old) > 0
    return old not in (None, "", False)


def write_json(
    path: Path,
    payload: Any,
    *,
    preserve_if_empty_would_erase: bool = False,
) -> bool:
    """Write JSON to ``path``. Returns True if a write occurred.

    If ``preserve_if_empty_would_erase`` is True and ``payload`` is ``[]`` or ``{}``,
    an existing file with non-empty JSON content is left unchanged (returns False)
    so a failed or empty fetch does not wipe prior pipeline data.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if preserve_if_empty_would_erase and payload in ([], {}):
        if _existing_json_nonempty(path):
            logger.warning(
                "Skipping write to %s: would replace non-empty data with empty %s; keeping existing file.",
                path,
                type(payload).__name__,
            )
            return False
    path.write_text(json.dumps(payload, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    return True


def read_json(path: Path) -> JSONValue:
    return json.loads(path.read_text(encoding="utf-8"))
