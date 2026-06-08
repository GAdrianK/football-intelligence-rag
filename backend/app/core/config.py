import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Chemin vers la racine du dossier backend
BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    OPENAI_API_KEY: str
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Recherche le fichier .env dans le dossier racine du backend
    model_config = SettingsConfigDict(
        env_file=os.path.join(BASE_DIR, ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
