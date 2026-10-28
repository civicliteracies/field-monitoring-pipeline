from pathlib import Path

import pytest

from tests.test_calls import WATCH_LIST


# The morning run's tests are in two files, and both write the same watch list into the test folder.
@pytest.fixture
def watch_list(tmp_path: Path) -> Path:
    path = tmp_path / "config" / "sources.toml"
    path.parent.mkdir()
    path.write_text(WATCH_LIST, encoding="utf-8")
    return path
