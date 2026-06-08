from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.services.rag_engine import RAGEngine
from app.api.chat import router as chat_router

app = FastAPI(
    title="Football IQ Assistant API",
    description="API du Football IQ Assistant - Phase 1 MVP",
    version="1.0.0"
)

# Enregistrer les routeurs
app.include_router(chat_router)

# Configuration CORS pour autoriser le frontend (local ou distant)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Dans un projet de prod réel, on restreindrait, mais pour le MVP c'est parfait
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instance globale du moteur RAG
rag_engine = RAGEngine(
    knowledge_base_dir=settings.get_kb_dir(),
    openai_api_key=settings.OPENAI_API_KEY
)

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "project": "Football IQ Assistant",
        "version": "1.0.0",
        "rag_mode": rag_engine.mode,
        "rag_chunks_loaded": len(rag_engine.chunks)
    }

@app.get("/api/search")
async def search_knowledge_base(query: str = Query(..., description="La requête de recherche tactique")):
    results = rag_engine.search(query, top_k=3)
    return {
        "query": query,
        "results": results
    }

@app.on_event("startup")
async def startup_event():
    # S'assurer que les variables de configuration sont chargées correctement
    assert settings.OPENAI_API_KEY is not None, "La clé API OpenAI n'a pas pu être chargée !"
    # Initialiser le RAG
    rag_engine.initialize()
    print("Football IQ Assistant API démarrée avec succès.")
