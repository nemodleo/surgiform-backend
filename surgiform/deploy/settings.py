from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

load_dotenv()  # .env → os.environ


class Settings(BaseSettings):
    # --- App ---
    app_env: str = Field("dev", alias="APP_ENV")
    app_host: str = Field("0.0.0.0", alias="APP_HOST")
    app_port: int = Field(8000, alias="APP_PORT")

    # --- OpenAI ---
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")

    # --- Elasticsearch ---
    es_host: str = Field("http://localhost:9200", alias="ES_HOST")
    es_user: str | None = Field(None, alias="ES_USER")
    es_password: str | None = Field(None, alias="ES_PASSWORD")

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # noqa: E501