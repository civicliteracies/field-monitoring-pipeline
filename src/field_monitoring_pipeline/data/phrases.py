"""Give the one form in which the topic check compares words, and the shape of a phrase of the topic list.

Both sides of every comparison are read in this form: case ignored, a hyphen read as a space (the ASCII
hyphen and the non-breaking hyphen, both found in the stored text) and a run of spacing read as one space.
A dash is left as it is: it separates words and is not a letter or a digit.
"""

import re
from dataclasses import dataclass

_HYPHEN = re.compile("[-‑]")


def form(text: str) -> str:
    return " ".join(_HYPHEN.sub(" ", text).casefold().split())


@dataclass(frozen=True)
class Phrase:
    text: str
    topic: str
    weak: bool
