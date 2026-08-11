"""Tests for the single-class HTTP(S) and same-origin policy."""

from __future__ import annotations

import pytest

from render_and_strip_mcp.errors import BrowserAgentError
from render_and_strip_mcp.url_policy import Origin, UrlPolicy


def test_initial_url_requires_permitted_http_scheme_and_host() -> None:
    """Initial URLs reject empty, non-HTTP(S), hostless, and unconfigured HTTP values."""

    for url in ("", "file:///tmp/page", "https:///missing-host", "http://example.test/"):
        with pytest.raises(BrowserAgentError):
            UrlPolicy(url, allow_plain_http=False).validate_initial_url()


def test_observed_url_uses_normalized_origin_and_effective_port() -> None:
    """The class accepts same-origin locations and rejects a changed host or port."""

    policy = UrlPolicy("https://Example.test/path", allow_plain_http=False)

    assert policy.validate_initial_url() == Origin(scheme="https", host="example.test", port=443)
    policy.validate_observed_url("https://example.test/next")
    with pytest.raises(BrowserAgentError, match="left the initial document origin"):
        policy.validate_observed_url("https://example.test:8443/next")
