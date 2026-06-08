from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

app = FastAPI(
    title="Football IQ Assistant API",
    description="API du Football IQ Assistant - Phase 1 MVP",
    version="1.0.0"
)

# Configuration CORS pour autoriser le frontend (local ou distant)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Dans un projet de prod réel, on restreindrait, mais pour le MVP c'est parfait
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "project": "Football IQ Assistant",
        "version": "1.0.0"
    }

@app.on_event("startup")
async def startup_event():
    # S'assurer que les variables de configuration sont chargées correctement
    assert settings.OPENAI_API_KEY is not None, "La clé API OpenAI n'a pas pu être chargée !"
    print("Football IQ Assistant API démarrée avec succès.")
