from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Reads values from environment variables, falling back to a local .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://careguard:careguard@localhost:5432/careguard"
    gemini_api_key: str = ""
    gemini_model: str = ""
    # Best policy chunk must score at least this (cosine similarity) or the LLM is not called.
    # 0.37 chosen 2026-11-24: lowest in-policy question scored 0.387, out-of-policy mostly < 0.37.
    min_score: float = 0.37
    # Empty means every admin request is refused.
    admin_api_key: str = ""


settings = Settings()
