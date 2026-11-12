from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    bot_token: str
    admin_password: str
    manager_password: str
    admin_ids: str = ""
    database_url: str = "sqlite+aiosqlite:///./data/repair_bot.db"
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    @property
    def admin_id_set(self) -> set[int]:
        return {int(x.strip()) for x in self.admin_ids.split(",") if x.strip().isdigit()}

settings = Settings()
Path("data").mkdir(exist_ok=True)
