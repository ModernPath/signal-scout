"""Runtime settings shared by the web and worker processes."""

from dataclasses import dataclass
import os
from typing import Mapping, Optional
from urllib.parse import urlsplit


class ConfigurationError(ValueError):
    """A required runtime setting is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    database_url: str

    @classmethod
    def from_env(cls, environment: Optional[Mapping[str, str]] = None) -> "Settings":
        values = os.environ if environment is None else environment
        url = values.get("DATABASE_URL", "")
        try:
            parsed = urlsplit(url)
            valid = (
                parsed.scheme == "postgresql+psycopg"
                and bool(parsed.username)
                and bool(parsed.password)
                and bool(parsed.hostname)
                and bool(parsed.path.strip("/"))
                and parsed.port is not None
                and not parsed.query
                and not parsed.fragment
            )
        except ValueError:
            valid = False
        if not valid:
            raise ConfigurationError(
                "DATABASE_URL must be a complete postgresql+psycopg URL "
                "with user, password, host, port, and database"
            )
        return cls(database_url=url)
