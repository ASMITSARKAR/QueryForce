from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

class Settings(BaseSettings):
    GROQ_API_KEY: SecretStr
    QUERYFORCE_API_KEY: SecretStr
    ANALYTICS_DB_PATH: str = "data/analytics.db"
    TELEMETRY_DB_PATH: str = "data/telemetry.db"
    CHROMA_DIR: str = "data/chroma_persist"
    MAX_RETRIES: int = 2
    LLM_SQL_MODEL: str = "llama-3.3-70b-versatile"
    LLM_SYNTH_MODEL: str = "llama-3.1-8b-instant"

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"), 
        env_file_encoding="utf-8"
    )

settings = Settings()
