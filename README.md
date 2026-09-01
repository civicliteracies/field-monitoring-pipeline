# The archive

This branch holds what the scheduled run captures. It shares no history with
`main`: the code lives there, the data lives here, and the two never tangle.

## What is here

`data/raw/` holds one text file per captured item, named by a hash, with a
small JSON record beside it saying where the item came from and which rule
produced its name.

`data/state/` holds one small file per source, carrying whatever that source
gave to identify its current version, so an unchanged source can be checked
without downloading the whole thing again. It is a cache: deleting it costs
one full fetch per source and nothing else.

Both folders appear on the first successful capture. Until then this note is
all there is.

## How to treat it

Nothing here is edited by hand. The run writes it, and every file can be
rebuilt by deleting a folder and letting the run fill it again.

The run commits here and never to `main`. The branch rules require a pull
request for every change to `main`, and that binds automation as well as
people, so routing the run to its own branch means it never has to get past
those rules and needs no bypass and no extra credential.

See `docs/ARCHITECTURE.md` on `main` for what each part of the pipeline does,
and record 0018 in `docs/decisions/` for why this branch exists.
