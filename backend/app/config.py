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
    monitor_instance_ids: str = Field(default="ins-ltludxxq,ins-da3g9cte")
    monitor_cos_bucket_names: str = Field(default="adp-1333737643,xmmj-1333737643")

    bandwidth_alert_threshold_mbps: float = Field(default=50.0)
    bandwidth_alert_poll_seconds: int = Field(default=300)
    bandwidth_alert_recipient: str = Field(default="kangguoqing@szeduai.com")
    bandwidth_alert_log_path: str = Field(default="data/bandwidth_alerts.jsonl")
    bandwidth_alert_state_path: str = Field(default="data/bandwidth_alert_state.json")
    metrics_collection_poll_seconds: int = Field(default=300)
    metrics_collection_lookback_minutes: int = Field(default=15)

    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=465)
    smtp_username: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_from_email: str = Field(default="")
    smtp_use_ssl: bool = Field(default=True)
    sqlite_db_path: str = Field(default="data/monitor.db")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def monitor_instance_id_list(self) -> list[str]:
        return [item.strip() for item in self.monitor_instance_ids.split(",") if item.strip()]

    @property
    def monitor_cos_bucket_name_list(self) -> list[str]:
        return [item.strip() for item in self.monitor_cos_bucket_names.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
