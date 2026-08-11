"""HTTP(S) and same-origin policy checks for the tracked top-level page."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from .errors import BrowserAgentError


@dataclass(frozen=True)
class Origin:
    """A URL origin using normalized scheme, host, and effective port."""

    scheme: str
    host: str
    port: int


class UrlPolicy:
    """Apply HTTP(S) and same-origin checks anchored to one initial URL."""

    def __init__(self, initial_url: str, allow_plain_http: bool):
        self.initial_url = initial_url
        self.allow_plain_http = allow_plain_http

    @property
    def origin(self) -> Origin:
        """Return this URL's normalized permitted origin."""

        return self._origin_for_url(self.initial_url)

    def _origin_for_url(self, url: str) -> Origin:
        try:
            parsed_url = urlsplit(url)
            port = parsed_url.port
        except ValueError as error:
            raise BrowserAgentError("URL has an invalid port.") from error
        scheme = parsed_url.scheme.lower()
        if scheme not in {"http", "https"}:
            raise BrowserAgentError("Only HTTP(S) URLs are permitted.")
        if scheme == "http" and not self.allow_plain_http:
            raise BrowserAgentError("Plain HTTP URLs are disabled by configuration.")
        if not parsed_url.hostname:
            raise BrowserAgentError("URL must include a host.")
        return Origin(
            scheme=scheme,
            host=parsed_url.hostname.lower(),
            port=port if port is not None else (443 if scheme == "https" else 80),
        )

    def validate_initial_url(self) -> Origin:
        """Validate this caller-supplied initial URL and return its normalized origin."""

        if not self.initial_url.strip():
            raise BrowserAgentError("The initial URL must not be empty.")
        return self.origin

    def validate_observed_url(self, observed_url: str) -> None:
        """Enforce that this browser-observed location remains at an allowed origin."""

        allowed_origin = self.origin
        if self._origin_for_url(observed_url) != allowed_origin:
            raise BrowserAgentError(
                "Browser navigation left the initial document origin "
                f"({allowed_origin.scheme}://{allowed_origin.host}:{allowed_origin.port})."
            )
