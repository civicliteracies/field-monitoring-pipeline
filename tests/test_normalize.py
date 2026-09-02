"""The same page reached three ways must reduce to one address."""

from field_monitoring_pipeline.normalize import canonical_url


def test_tracking_parameters_are_dropped() -> None:
    newsletter = "https://example.org/call?utm_source=news&utm_medium=email"
    shared = "https://example.org/call?fbclid=abc123"
    direct = "https://example.org/call"

    assert canonical_url(newsletter) == canonical_url(direct)
    assert canonical_url(shared) == canonical_url(direct)


def test_meaningful_parameters_are_kept() -> None:
    assert canonical_url("https://example.org/list?page=2") == "https://example.org/list?page=2"


def test_parameter_order_does_not_make_two_pages() -> None:
    first = canonical_url("https://example.org/c?b=2&a=1")
    second = canonical_url("https://example.org/c?a=1&b=2")
    assert first == second


def test_scheme_host_case_and_fragment_are_normalised() -> None:
    assert canonical_url("HTTPS://Example.ORG/call#apply") == "https://example.org/call"


def test_empty_path_becomes_root() -> None:
    assert canonical_url("https://example.org") == "https://example.org/"
