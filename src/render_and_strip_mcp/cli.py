"""Command-line startup for the Streamable HTTP MCP server."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import Settings, load_settings
from .server import create_server


def configure_logging(settings: Settings) -> None:
    """Configure process logging before starting the server."""

    logging.basicConfig(
        level=settings.logging.level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


def main(settings: Settings) -> None:
    """Start the configured Streamable HTTP server."""

    server = create_server(settings)
    server.run(
        transport="streamable-http",
        host=settings.server.host,
        port=settings.server.port,
    )


def cli() -> None:
    """Parse command-line configuration and run the server."""

    argument_parser = argparse.ArgumentParser(
        description="Run the render-and-strip Streamable HTTP MCP server."
    )
    argument_parser.add_argument(
        "configuration_path",
        nargs="?",
        type=Path,
        help="Optional TOML configuration path.",
    )
    arguments = argument_parser.parse_args()
    settings = load_settings(arguments.configuration_path)
    configure_logging(settings)
    main(settings)
