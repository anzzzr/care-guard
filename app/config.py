from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Reads values from environment variables, falling back to a local .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://careguard:careguard@localhost:5432/careguard"


settings = Settings()
