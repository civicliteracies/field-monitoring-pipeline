# What a person read off this page

This is the human reading, agreed before any model saw the page. It is not what
the test asserts. The test asserts that the recorded reply beside it produces the
record in `expected.json`, which proves the deterministic half.

This file is the other half: what the answer should be, for a person doing the
check by eye.

| Field | What the page states |
|---|---|
| title | Introducing the Tech Accountability Fund and a Call for Proposals |
| type | grant |
| funder | CIPESA in partnership with Digital Action |
| deadline | 2024-02-16 |
| budget | USD 5,000 to USD 20,000 |
| eligibility | African civil society entities |
| area | Sub-Saharan Africa |

## Where a model has differed

**The kind of call.** Read as a grant here. A model reading the same page has
called it a grant on some runs and a request for proposals on others. Both are on
the fixed list, so both pass every check. The page supports either reading: it
announces a fund that makes grants, by way of a call for proposals. This is the
clearest example in the fixture set of a value that is checked for being a real
option and not for being the right one.

**Who may apply.** There is no formal eligibility clause on this page. No sentence
says applicants must be anything. The best support describes who the fund is for,
which is honest but weaker than a rule, and a model has answered "not stated" for
it on at least one run.

## How the reply beside this was recorded

The answer in `reply.txt` came from a live run using prompt `v2` and model `gemini-3.5-flash-lite`. It is one answer from one run, kept so the test is the same every time. It is not a claim that the model answers this way every time, and on this project it does not always.

The frozen page carries at least one value that changes on every request, so regenerating it shows a difference even when the funder has changed nothing. Read the words rather than the diff.
