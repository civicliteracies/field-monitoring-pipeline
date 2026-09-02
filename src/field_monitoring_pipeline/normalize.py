"""Reduce a link to one canonical form before it is used as a name.

The same funding call reaches us from a newsletter, from a shared post and from
a direct visit, each carrying different tracking parameters. Without this step
each of those would look like a different item and be captured three times.

This works on the text of a link and makes no network request, so a link that
redirects is left pointing at the redirector. Resolving those costs one request
per item on every run, and a feed almost always publishes its own identifier for
an item, which takes precedence over the link when naming it. That work is
therefore deferred to the slice that hardens canonicalisation, where it can be
done for the items that actually need it.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PREFIXES = ("utm_",)
"""Whole families of tracking parameters share a prefix."""

TRACKING_NAMES = frozenset({
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "igshid",
    "ref",
    "ref_src",
    "cmpid",
    "spm",
    "source",
})
"""Individual tracking parameters that carry no meaning for the page itself."""


def _is_tracking(name: str) -> bool:
    lowered = name.lower()
    return lowered.startswith(TRACKING_PREFIXES) or lowered in TRACKING_NAMES


def canonical_url(url: str) -> str:
    """Return the form of `url` used to recognise the same page twice.

    Lowercases the scheme and host, drops the fragment, removes tracking
    parameters, and sorts what remains so that parameter order cannot make one
    page look like two.
    """
    parts = urlsplit(url.strip())
    kept = sorted(
        (name, value) for name, value in parse_qsl(parts.query, keep_blank_values=True) if not _is_tracking(name)
    )
    host = parts.netloc.lower()
    path = parts.path or "/"
    return urlunsplit((parts.scheme.lower(), host, path, urlencode(kept), ""))
