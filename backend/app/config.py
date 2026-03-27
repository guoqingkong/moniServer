from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CVM Monitor API"
    app_env: str = "development"

    tencent_secret_id: str = Field(default="")
    tencent_secret_key: str = Field(default="")
    tencent_region: str = Field(default="ap-guangzhou")
    default_instance_id: str = Field(default="")
    cors_origins: str = Field(default="http://localhost:5173")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
