import pytest

from signalscout.config import ConfigurationError, Settings


@pytest.mark.parametrize(
    "environment",
    [
        {},
        {"DATABASE_URL": ""},
        {"DATABASE_URL": "postgresql://scout:secret@localhost/signalscout"},
        {"DATABASE_URL": "postgresql+psycopg://scout:secret@/signalscout"},
    ],
)
def test_database_url_is_required_and_validated_without_exposing_secrets(environment):
    with pytest.raises(ConfigurationError) as error:
        Settings.from_env(environment)

    assert "DATABASE_URL" in str(error.value)
    assert "secret" not in str(error.value)


def test_provider_credentials_are_not_needed_for_core_startup():
    url = "postgresql+psycopg://scout:secret@localhost:5432/signalscout"

    settings = Settings.from_env({"DATABASE_URL": url})

    assert settings.database_url == url
