from pathlib import Path

import pytest

from tests.test_calls import WATCH_LIST
from tests.test_tags import TOPIC_LIST


# The morning run's tests are in two files, and both write the same watch list and topic list into the test folder.
@pytest.fixture
def watch_list(tmp_path: Path) -> Path:
    path = tmp_path / "config" / "sources.toml"
    path.parent.mkdir()
    path.write_text(WATCH_LIST, encoding="utf-8")
    return path


@pytest.fixture
def topic_list(watch_list: Path) -> Path:
    path = watch_list.parent / "tags.toml"
    path.write_text(TOPIC_LIST, encoding="utf-8")
    return path
