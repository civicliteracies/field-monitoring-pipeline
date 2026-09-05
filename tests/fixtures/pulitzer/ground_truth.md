# What a person read off this page

This is the human reading, agreed before any model saw the page. It is not what
the test asserts. The test asserts that the recorded reply beside it produces the
record in `expected.json`, which proves the deterministic half.

| Field | What the page states |
|---|---|
| title | Open Call for Proposals for Pulitzer Center's AI Accountability Fellowships (2026-2027) |
| type | fellowship |
| funder | Pulitzer Center |
| deadline | 2026-07-12 |
| budget | up to $25,000, being up to $20,000 for reporting and $5,000 for engagement |
| eligibility | journalists, and those from the Global South are encouraged |
| area | global |

## Why this page is in the set

**The area is a derived value.** The word "global" appears nowhere on the page.
It is a reading, and the sentence that supports it says the centre is recruiting
journalists from around the world. So a value may be an honest interpretation
while its quote must be the page's own words. This is the case the fixture exists
to force.

**The page carries other programmes in its own markup.** Its menus name several
other grants run by the same organisation. A sentence from one of those is a real
substring of this page and would pass a substring check while describing a
different grant entirely. The extraction drops a page's declared furniture before
reading it, which removes most of these, and this fixture is where that is
checked.

## How the reply beside this was recorded

The answer in `reply.txt` came from a live run using prompt `v2` and model `gemini-3.5-flash-lite`. It is one answer from one run, kept so the test is the same every time. It is not a claim that the model answers this way every time, and on this project it does not always.

The frozen page carries at least one value that changes on every request, so regenerating it shows a difference even when the funder has changed nothing. Read the words rather than the diff.
