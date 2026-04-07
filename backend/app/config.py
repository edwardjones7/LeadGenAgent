from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Always resolve .env relative to this file's location (backend/app/../.env)
_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    yelp_api_key: str
    supabase_url: str
    supabase_key: str
    groq_api_key: str | None = None
    sambanova_api_key: str | None = None
    resend_api_key: str | None = None
    from_email: str | None = None

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8")


settings = Settings()
