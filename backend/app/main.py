from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from openai import OpenAI

from app.core.config import settings
from app.services.rag_engine import RAGEngine
from app.api.chat import router as chat_router
from app.api.pdf import router as pdf_router

# Importation du pipeline de recherche avancée
from retrieval.hybrid_engine import HybridSearchEngine
from retrieval.reranker import TacticalReranker
from generation.schemas import (
    TacticalReportSchema, OrganisationOffensive, OrganisationDefensive,
    Transitions, Pressing, Construction, Couloirs, Milieu, Occasions,
    JoueurCle, Recommandations
)

app = FastAPI(
    title="Football IQ Assistant API",
    description="API du Football IQ Assistant - Phase 1 MVP",
    version="1.0.0"
)

# Enregistrer les routeurs
app.include_router(chat_router)
app.include_router(pdf_router)

# Configuration CORS pour autoriser le frontend (local ou distant)
origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instance globale du moteur RAG
rag_engine = RAGEngine(
    knowledge_base_dir=settings.get_kb_dir(),
    openai_api_key=settings.OPENAI_API_KEY
)

# Instances des moteurs de recherche avancée
hybrid_search_engine = HybridSearchEngine()
tactical_reranker = TacticalReranker()

# Schémas de requêtes et réponses pour l'analyse
class AnalysisRequest(BaseModel):
    query: str
    filter_dict: Optional[dict] = None

class AnalysisResponse(BaseModel):
    report: TacticalReportSchema
    sources: List[Dict[str, Any]]

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

@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_match(request: AnalysisRequest):
    query = request.query
    
    # 1. Utiliser le moteur de recherche hybride pour récupérer les chunks
    raw_results = hybrid_search_engine.search(query, top_k=15, filter_dict=request.filter_dict)
    # Rerank et récupération du Top 5 parent-child
    top_results = tactical_reranker.rerank_and_resolve(query, raw_results, top_k=5)

    # Extraire les textes des documents parents pour les injecter dans le contexte
    context_documents = []
    sources = []
    for res in top_results:
        parent_ctx = res.get("parent_context", {})
        parent_content = parent_ctx.get("content", "")
        parent_source = parent_ctx.get("source", "")
        
        if parent_content and parent_content not in context_documents:
            context_documents.append(parent_content)
        
        sources.append({
            "source": parent_source,
            "score": res["scores"]["rerank"],
            "text": res["text"]
        })

    context_text = "\n\n---\n\n".join(context_documents) if context_documents else "Aucune fiche tactique pertinente trouvée."

    # 2. Appel OpenAI Structured Outputs (ou Fallback Mock)
    api_key = settings.OPENAI_API_KEY
    use_openai = api_key and not api_key.startswith("mock-") and len(api_key.strip()) > 0

    if use_openai:
        try:
            client = OpenAI(api_key=api_key)
            
            system_prompt = (
                "Tu es un expert mondial en tactique de football, un analyste chevronné travaillant pour des clubs professionnels.\n"
                "Ta mission est de rédiger un rapport tactique d'excellence basé UNIQUEMENT sur les documents fournis en contexte.\n"
                "Tu dois structurer ta réponse en renseignant minutieusement chacun des 10 piliers tactiques exigés.\n"
                "N'invente aucun fait. Si une information n'est pas présente dans le contexte, décris-la de manière neutre ou suggère une consigne générique cohérente.\n"
                "Voici le contexte tactique à utiliser pour ton analyse :\n\n"
                f"{context_text}"
            )
            
            # Utilisation de Structured Outputs d'OpenAI pour forcer le schéma strict
            response = client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Génère le rapport tactique complet pour : '{query}'"}
                ],
                response_format=TacticalReportSchema,
                temperature=0.2
            )
            
            report = response.choices[0].message.parsed
            return AnalysisResponse(report=report, sources=sources)
            
        except Exception as e:
            # En cas d'erreur de clé ou de quota OpenAI, bascule automatique sur le mock
            print(f"[WARNING] Erreur OpenAI lors de l'analyse : {e}. Bascule sur le mock.")
            
    # Générateur de mock tactique réaliste pour la démonstration locale / offline
    mock_report = TacticalReportSchema(
        titre=f"Analyse Tactique Professionnelle : {query}",
        match_ou_sujet="Paris Saint-Germain vs Olympique de Marseille (Simulation)",
        organisation_offensive=OrganisationOffensive(
            creation="Utilisation intensive des demi-espaces par des passes intérieures courtes pour déstabiliser le bloc médian adverse.",
            espaces="Occupation des demi-espaces droits et gauches par les milieux offensifs excentrés pour libérer les couloirs.",
            largeur="Maintien d'une largeur maximale par les latéraux offensifs qui étirent la ligne défensive adverse.",
            profondeur="Courses répétées de l'attaquant axial pour forcer les défenseurs centraux à reculer et créer de l'interligne."
        ),
        organisation_defensive=OrganisationDefensive(
            bloc="Mise en place d'un bloc bas compact (low block) glissant vers un bloc médian lors des phases de pressing déclenchées.",
            compacite="Forte compacité horizontale (25 mètres maximum) limitant les passes verticales adverses.",
            duels="Engagement intense dans les duels individuels dans l'axe, compensé par des prises à deux systématiques.",
            couverture="Glissement latéral fluide de la charnière centrale pour couvrir les montées des latéraux."
        ),
        transitions=Transitions(
            offensive="Projection ultra-rapide des ailiers dès la récupération dans les zones de transition intermédiaire.",
            defensive="Contre-pressing immédiat (gegenpressing) pendant 6 secondes à la perte du ballon avant de se repositionner en bloc bas."
        ),
        pressing=Pressing(
            intensite="Intensité modérée avec déclenchement agressif dès que le défenseur central adverse s'oriente vers son pied faible.",
            zones="Pressing principalement orienté dans le tiers médian pour forcer le jeu long adverse."
        ),
        construction=Construction(
            relance="Sortie propre depuis le gardien par passes courtes au sol avec le pivot venant offrir une solution d'appui.",
            progression="Progression par passes progressives courtes combinées à des renversements de jeu rapides."
        ),
        couloirs=Couloirs(
            ailes="Fixation extérieure des ailiers inversés qui rentrent sur leur pied fort pour combiner ou frapper.",
            centres="Centres tendus ras de terre en retrait vers le point de penalty à privilégier."
        ),
        milieu=Milieu(
            domination="Supériorité numérique créée par le décrochage du faux 9, permettant une domination technique.",
            creation="Orientation et distribution fluide assurées par le double pivot axial distribuant vers les demi-espaces."
        ),
        occasions=Occasions(
            qualite="Recherche de tirs à haute probabilité (xG > 0.15) à l'intérieur de la surface de réparation.",
            volume="Volume stable de 12 à 15 tirs par match grâce à une progression construite."
        ),
        joueurs_cles=[
            JoueurCle(
                nom="Vitinha",
                impact="Maître du tempo, régule les transitions et assure la compacité du bloc axial.",
                erreurs="Vigilance requise sur les ballons perdus lors des passes risquées sous haute pression."
            ),
            JoueurCle(
                nom="Ousmane Dembélé",
                impact="Fixation extérieure créant des décalages majeurs, forte accélération dans le demi-espace.",
                erreurs="Déchet technique parfois élevé sur le dernier geste ou le centre final."
            )
        ],
        recommandations=Recommandations(
            axes_travail=[
                "Améliorer la transition défensive immédiate pour contrer les attaques rapides adverses.",
                "Optimiser la qualité des centres ras de terre en retrait."
            ],
            exercice_entrainement="Rondo de transition sous pression 4v4+2 dans un espace réduit de 20x20m avec transition rapide cible en moins de 6 secondes."
        )
    )
    
    # Remplir des sources si la base locale est vide
    if not sources:
        sources = [
            {"source": "bloc_bas.md", "score": 0.8942, "text": "Le low block nécessite une compacité verticale..."},
            {"source": "roles_modernes.md", "score": 0.7651, "text": "L'ailier inversé rentre sur son pied fort pour combiner..."}
        ]
        
    return AnalysisResponse(report=mock_report, sources=sources)

@app.on_event("startup")
async def startup_event():
    # S'assurer que les variables de configuration sont chargées correctement
    assert settings.OPENAI_API_KEY is not None, "La clé API OpenAI n'a pas pu être chargée !"
    # Initialiser le RAG
    rag_engine.initialize()
    print("Football IQ Assistant API démarrée avec succès.")

