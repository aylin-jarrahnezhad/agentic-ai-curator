import json
from pathlib import Path

from utils.json_utils import write_json


def test_write_json_preserve_skips_empty_over_nonempty(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    path.write_text(json.dumps([{"id": 1}]), encoding="utf-8")
    assert write_json(path, [], preserve_if_empty_would_erase=True) is False
    assert json.loads(path.read_text(encoding="utf-8")) == [{"id": 1}]


def test_write_json_empty_when_no_prior_file(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    assert write_json(path, [], preserve_if_empty_would_erase=True) is True
    assert json.loads(path.read_text(encoding="utf-8")) == []
