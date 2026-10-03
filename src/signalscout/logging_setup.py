"""Minimal process logging without environment or connection values."""

import logging


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
