from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "chat2action API"
    api_prefix: str = "/api"
    dashscope_api_key: str | None = Field(default=None, alias="DASHSCOPE_API_KEY")
    model_name: str = Field(default="qwen-plus", alias="MODEL_NAME")
    dashscope_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        alias="DASHSCOPE_BASE_URL",
    )
    request_timeout_seconds: float = 25.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
