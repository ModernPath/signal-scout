"""Dedicated local worker for the application's intelligence queue."""
import argparse
import logging
import signal
import threading
import time

from sqlalchemy import text
from .config import Settings
from .database import make_engine
from .intelligence import make_service
from .intelligence_jobs import process_one, recover_running
from .logging_setup import configure_logging


def tick(engine, agent):
    job=process_one(engine,agent)
    if job is None:
        current=time.monotonic()
        if current-getattr(agent,'_knowledge_cleanup_at',0)>=3600:
            agent.cleanup_expired()
            agent._knowledge_cleanup_at=current
        agent.knowledge.index_pending(limit=2)
    return job


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--once',action='store_true')
    args=parser.parse_args()
    configure_logging()
    engine=make_engine(Settings.from_env())
    try:
        agent=make_service(engine,use_subagents=True)
        agent.store.check_schema()
        if args.check:
            with engine.connect() as conn:
                conn.execute(text('SELECT 1 FROM intelligence_job LIMIT 1'))
            return
        stop=threading.Event()
        signal.signal(signal.SIGTERM,lambda *_:stop.set())
        signal.signal(signal.SIGINT,lambda *_:stop.set())
        recover_running(engine,force=True)
        logging.getLogger(__name__).info('Intelligence worker ready')
        while not stop.is_set():
            try:
                recover_running(engine)
                tick(engine,agent)
            except Exception:
                logging.getLogger(__name__).error('Intelligence worker database operation failed')
            if args.once:
                break
            stop.wait(2)
    finally:
        engine.dispose()


if __name__=='__main__':
    main()
