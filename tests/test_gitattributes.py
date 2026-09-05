"""The archive and the frozen fixtures come back exactly as they went in.

Everything the quote check does rests on one assumption: that a captured page is
the same bytes tomorrow, and on someone else's machine, as it was when it was
written. Git does not guarantee that by default. It has an opinion about line
endings, and this repository tells it to act on that opinion for every file.

This test is the guard on the exception that spares the evidence. It is slower
than the rest of the suite because it drives git, which is the only way to prove
what git actually does rather than what its documentation says it does.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SERVED = b"The deadline for applications\r\nis February 16, 2024.\r\n"
"""A capture from a source whose server uses Windows line endings."""


def git(where: Path, *args: str) -> None:
    """Run one git command and ignore what it says.

    Deliberately not asking for text back. Doing so would decode git's output
    using whatever code page the machine happens to use, and on the machine this
    was written on that turns an accent or a dash into a replacement character.
    Nothing here reads the output, so the safest form is not to decode it at all.
    """
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=where,
        capture_output=True,
        check=False,
    )


@pytest.mark.parametrize(
    "kept",
    ["data/raw/item.txt", "tests/fixtures/a-source/input.txt"],
    ids=["the-archive", "a-frozen-fixture"],
)
def test_evidence_survives_a_commit_and_a_clone(kept: str) -> None:
    """Measured: without the exception, 54 bytes were stored as 52 and came back as 52.

    A quote spanning a line break then matched on the machine that captured the
    page and failed on every other machine, so the push-time check and the
    rebuild would both refuse an honest quote for a reason nobody could see.
    """
    with tempfile.TemporaryDirectory(prefix="fieldbook-eol-") as scratch:
        origin, clone = Path(scratch) / "origin", Path(scratch) / "clone"
        (origin / kept).parent.mkdir(parents=True)
        git(origin, "init", "-q", ".")
        shutil.copy(ROOT / ".gitattributes", origin / ".gitattributes")
        (origin / kept).write_bytes(SERVED)

        git(origin, "add", ".gitattributes", kept)
        git(origin, "commit", "-q", "-m", "capture")
        subprocess.run(["git", "clone", "-q", str(origin), str(clone)], capture_output=True, check=False)

        assert (clone / kept).read_bytes() == SERVED
        # The consequence, stated as the thing that would actually go wrong: a
        # quote spanning the line break has to be findable after a clone.
        quote = "The deadline for applications\r\nis February 16, 2024."
        assert quote in (clone / kept).read_bytes().decode()
