"""Scheduled collection worker entry point."""

import argparse
import logging
import signal
import sys
import threading

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .config import ConfigurationError, Settings
from .database import make_engine
from .database import make_session_factory
from .logging_setup import configure_logging
from .adapters import build_adapters
from .collection import process_one, queue_scheduled, recover_stale_runs


logger = logging.getLogger(__name__)


def run_cycle(session_factory, adapters, now=None):
    """Drain one queued run or create and process the current UTC slot."""
    recover_stale_runs(session_factory, now)
    processed = process_one(session_factory, adapters)
    if processed is not None:
        return processed
    queue_scheduled(session_factory, now)
    return process_one(session_factory, adapters)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SignalScout collection worker")
    parser.add_argument("--check", action="store_true", help="check database readiness and exit")
    parser.add_argument("--once", action="store_true", help="run one collection cycle and exit")
    args = parser.parse_args(argv)
    configure_logging()

    try:
        settings = Settings.from_env()
    except ConfigurationError as error:
        logger.error("%s", error)
        return 1

    engine = make_engine(settings)
    try:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            logger.error("Database unavailable")
            return 1

        if args.check:
            return 0

        stop = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
        signal.signal(signal.SIGINT, lambda *_: stop.set())
        session_factory = make_session_factory(engine)
        adapters = build_adapters()
        recover_stale_runs(session_factory, force=True)
        logger.info("Worker ready; waiting for collection work")
        while not stop.is_set():
            try:
                run_cycle(session_factory, adapters)
            except SQLAlchemyError:
                logger.error("Collection database operation failed")
            if args.once:
                break
            stop.wait(10)
        logger.info("Worker stopped")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
