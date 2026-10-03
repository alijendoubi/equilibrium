"""Logging setup. Never log secret values; log only whether they are configured."""

import logging

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(level: str) -> None:
    """Configure root logging at application startup."""
    logging.basicConfig(level=level, format=LOG_FORMAT)
