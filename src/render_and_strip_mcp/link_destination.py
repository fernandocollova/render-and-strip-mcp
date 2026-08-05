"""Safe visible-link destination resolution for cleaned documents."""

from __future__ import annotations

from urllib.parse import urljoin, urlsplit


def sanitize_link_destination(
    href: object,
    final_url: str,
    allow_plain_http: bool,
) -> str | None:
    """Resolve and retain only permitted safe absolute link destinations."""

    if not isinstance(href, str):
        return None
    candidate = href.strip()
    if not candidate or any(character.isspace() for character in candidate):
        return None
    if candidate.startswith("#"):
        return candidate
    try:
        destination = urljoin(final_url, candidate)
        parsed_destination = urlsplit(destination)
        if parsed_destination.username is not None or parsed_destination.password is not None:
            return None
        scheme = parsed_destination.scheme.lower()
        if scheme in {"mailto", "tel"}:
            return destination if parsed_destination.path else None
        if scheme == "https" and parsed_destination.hostname:
            return destination
        if scheme == "http" and allow_plain_http and parsed_destination.hostname:
            return destination
    except ValueError:
        return None
    return None
