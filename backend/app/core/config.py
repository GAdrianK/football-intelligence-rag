import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Chemin vers la racine du dossier backend
BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    APISPORTS_KEY: str = ""
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    KNOWLEDGE_BASE_DIR: str = ""

    @property
    def gemini_key(self) -> str:
        # Préférer GEMINI_API_KEY puis GOOGLE_API_KEY
        key = self.GEMINI_API_KEY or self.GOOGLE_API_KEY or ""
        return key.strip()

    @property
    def openrouter_key(self) -> str:
        return self.OPENROUTER_API_KEY.strip()
    ALLOWED_ORIGINS: str = "*"

    RAW_DATA_DIR: str = ""
    PROCESSED_DATA_DIR: str = ""
    QDRANT_URL: str = ":memory:"
    QDRANT_COLLECTION_NAME: str = "football_intelligence"
    SQLITE_DB_PATH: str = ""

    def get_kb_dir(self) -> str:
        if self.KNOWLEDGE_BASE_DIR:
            return self.KNOWLEDGE_BASE_DIR
        return os.path.abspath(os.path.join(BASE_DIR.parent, "knowledge_base"))

    def get_raw_data_dir(self) -> str:
        if self.RAW_DATA_DIR:
            return self.RAW_DATA_DIR
        return os.path.abspath(os.path.join(BASE_DIR, "data", "raw"))

    def get_processed_data_dir(self) -> str:
        if self.PROCESSED_DATA_DIR:
            return self.PROCESSED_DATA_DIR
        return os.path.abspath(os.path.join(BASE_DIR, "data", "processed"))

    def get_sqlite_db_path(self) -> str:
        if self.SQLITE_DB_PATH:
            return self.SQLITE_DB_PATH
        return os.path.abspath(os.path.join(BASE_DIR, "data", "parent_store.db"))

    # Recherche le fichier .env dans le dossier racine du backend
    model_config = SettingsConfigDict(
        env_file=os.path.join(BASE_DIR, ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
