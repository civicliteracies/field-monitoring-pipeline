"""Own the data directory: what is already in it, and everything written to it.

Three folders live under it. `raw/` holds the items, `responses/` holds what
each source actually served before anything read it, and `state/` holds the
bookmarks the run keeps for itself.

Two jobs that belong together. Every write goes through one place rooted at
`data/`, so nothing in the run can reach the configuration people edit by hand.
And the names already captured are read once when the store is opened, so asking
whether an item is new can never be affected by what this run has just written.

That second point is what makes the ordering rule safe. The raw body is written
before anything asks whether the item was already known, and the answer still
reflects the state before the run began.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

RAW = "raw"
RESPONSES = "responses"
STATE = "state"


class Store:
    """The `data/` directory, and the only way anything writes into it."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        raw = self._root / RAW
        self._known = frozenset(path.stem for path in raw.glob("*.txt"))

    @property
    def known(self) -> frozenset[str]:
        """The item names present before this run started."""
        return self._known

    def is_new(self, item_id: str) -> bool:
        """Was this item absent when the run began?

        Answered from the snapshot taken at opening, so writing an item does not
        change the answer for that item.
        """
        return item_id not in self._known

    def write(self, *parts: str, data: bytes) -> Path:
        """Write one file inside the store and return where it went.

        The path is built from the store's own root, so a caller cannot address
        anything outside it. The check below makes that true rather than merely
        intended, which matters because one of the name inputs comes from the
        open web.
        """
        target = (self._root.joinpath(*parts)).resolve()
        if not target.is_relative_to(self._root):
            msg = f"refusing to write outside the store: {target}"
            raise ValueError(msg)

        target.parent.mkdir(parents=True, exist_ok=True)
        _ = target.write_bytes(data)
        return target

    def read(self, *parts: str) -> bytes | None:
        """Read one file from inside the store, or None if it is not there."""
        target = self._root.joinpath(*parts)
        if not target.is_file():
            return None
        return target.read_bytes()
