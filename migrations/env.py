"""Alembic configuration using the same settings as the application."""

from logging.config import fileConfig

from alembic import context

from signalscout.config import Settings
from signalscout.database import Base, make_engine


config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_online() -> None:
    engine = make_engine(Settings.from_env())
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


run_migrations_online()
