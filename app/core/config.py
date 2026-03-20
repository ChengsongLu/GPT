from pathlib import Path

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    app_name: str = "Git Progress Tracker"
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 18000
    timezone: str = "Asia/Shanghai"
    data_dir: Path = Path("data")
    db_filename: str = "app.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @computed_field
    @property
    def database_url(self) -> str:
        db_path = (self.data_dir / self.db_filename).resolve()
        return f"sqlite+aiosqlite:///{db_path}"


settings = AppConfig()
