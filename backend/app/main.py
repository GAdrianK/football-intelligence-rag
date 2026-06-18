from fastapi import FastAPI, Query, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.rag_engine import RAGEngine
from app.api.chat import router as chat_router
from app.api.pdf import router as pdf_router
from app.database.sql_store import engine, Base, get_sql_db, SessionLocal
from app.models.player_stats import PlayerMatchStats
from app.services.extractor_engine import FootballScraperEngine
from app.services.bulk_ingestion import run_bulk_ingestion

# Importation du pipeline de recherche avancée
from retrieval.hybrid_engine import HybridSearchEngine
from retrieval.reranker import TacticalReranker
from retrieval.trend_engine import TrendAnalysisEngine
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

# =================================================================
# CONFIGURATION DU MIDDLEWARE CORS (L'anti-NetworkError)
# =================================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],         # Autorise toutes les origines (indispensable en local)
    allow_credentials=True,
    allow_methods=["*"],         # Autorise toutes les méthodes (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],         # Autorise tous les en-têtes (Content-Type, etc.)
)

# Instance globale du moteur RAG
rag_engine = RAGEngine(
    knowledge_base_dir=settings.get_kb_dir(),
    openai_api_key=settings.OPENAI_API_KEY
)

# Instances des moteurs de recherche avancée
hybrid_search_engine = HybridSearchEngine()
tactical_reranker = TacticalReranker()
trend_engine = TrendAnalysisEngine()

# Schémas de requêtes et réponses pour l'analyse
class AnalysisRequest(BaseModel):
    query: str
    filter_dict: Optional[dict] = None
    periode: Optional[str] = None
    intervalle_temps: Optional[str] = None

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
    raw_results = hybrid_search_engine.search(
        query, 
        top_k=15, 
        filter_dict=request.filter_dict,
        periode_cible=request.periode,
        intervalle_cible=request.intervalle_temps
    )
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

    # 2. Appel OpenRouter/Qwen (si clé présente) ou Gemini ou OpenAI Structured Outputs (ou Fallback Mock)
    openrouter_key = settings.openrouter_key
    use_openrouter = openrouter_key and not openrouter_key.startswith("mock-") and len(openrouter_key.strip()) > 0

    gemini_key = settings.gemini_key
    use_gemini = gemini_key and not gemini_key.startswith("mock-") and len(gemini_key.strip()) > 0
    
    openai_key = settings.OPENAI_API_KEY
    use_openai = openai_key and not openai_key.startswith("mock-") and len(openai_key.strip()) > 0

    system_prompt = (
        "Tu es un expert mondial en tactique de football, un analyste chevronné travaillant pour des clubs professionnels.\n"
        "Ta mission est de rédiger un rapport tactique d'excellence basé UNIQUEMENT sur les documents fournis en contexte.\n"
        "Tu dois structurer ta réponse en renseignant minutieusement chacun des 10 piliers tactiques exigés.\n"
        "N'invente aucun fait. Si une information n'est pas présente dans le contexte, décris-la de manière neutre ou suggère une consigne générique cohérente.\n"
        "Voici le contexte tactique à utiliser pour ton analyse :\n\n"
        f"{context_text}"
    )

    if use_openrouter:
        try:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=openrouter_key
            )
            schema_instruction = (
                "\n\nIMPORTANT : Tu dois renvoyer STRICTEMENT un objet JSON valide conforme au schéma TacticalReportSchema.\n"
                "Le JSON doit obligatoirement avoir les champs suivants :\n"
                "- titre: str\n"
                "- match_ou_sujet: str\n"
                "- organisation_offensive: objet avec les champs (creation, espaces, largeur, profondeur)\n"
                "- transitions_off_def: objet avec les champs (repli_collectif, contre_pressing, zones_a_securiser)\n"
                "- organisation_defensive: objet avec les champs (hauteur_bloc, compacite_verticale_horizontale, cadrage_porteur, gestion_profondeur)\n"
                "- transitions_def_off: objet avec les champs (premiere_passe_relance, projection_verticale, securisation_possession)\n"
                "- coups_de_pied_arretes: objet avec les champs (corners_offensifs, coups_francs_offensifs, organisation_defensive_cpa)\n"
                "- animation_couloirs: objet avec les champs (role_lateraux, surcharges_ailiers)\n"
                "- gestion_interlignes: objet avec les champs (positionnement_receveur, blocage_passes_adversaires)\n"
                "- pressage_declencheurs: objet avec les champs (hauteur_pressing, triggers_declenchement, couverture_derriere)\n"
                "- faiblesses_a_exploiter: objet avec les champs (zones_vulnerables, joueurs_cibles)\n"
                "- consignes_individuelles: liste d'objets avec les champs (nom_joueur, role_tactique, consigne_cle)\n"
            )
            response = client.chat.completions.create(
                model="qwen/qwen-2.5-72b-instruct:free",
                messages=[
                    {"role": "system", "content": system_prompt + schema_instruction},
                    {"role": "user", "content": f"Génère le rapport tactique complet pour : '{query}'"}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            report_text = response.choices[0].message.content
            report = TacticalReportSchema.model_validate_json(report_text)
            return AnalysisResponse(report=report, sources=sources)
        except Exception as e:
            print(f"[WARNING] Erreur OpenRouter Qwen gratuit lors de l'analyse : {e}. Tentative avec la version payante.")
            try:
                response = client.chat.completions.create(
                    model="qwen/qwen-2.5-72b-instruct",
                    messages=[
                        {"role": "system", "content": system_prompt + schema_instruction},
                        {"role": "user", "content": f"Génère le rapport tactique complet pour : '{query}'"}
                    ],
                    temperature=0.2,
                    response_format={"type": "json_object"}
                )
                report_text = response.choices[0].message.content
                report = TacticalReportSchema.model_validate_json(report_text)
                return AnalysisResponse(report=report, sources=sources)
            except Exception as e2:
                print(f"[ERROR] Erreur critique OpenRouter (payant) lors de l'analyse : {e2}")
                if not use_gemini and not use_openai:
                    raise e2

    if use_gemini and not use_openrouter:
        try:
            from google import genai
            from google.genai import types
            
            client = genai.Client(api_key=gemini_key)
            response = client.models.generate_content(
                model="gemini-flash-latest",
                contents=f"Génère le rapport tactique complet pour : '{query}'",
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=TacticalReportSchema,
                    temperature=0.2
                )
            )
            report = TacticalReportSchema.model_validate_json(response.text)
            return AnalysisResponse(report=report, sources=sources)
        except Exception as e:
            print(f"[ERROR] Erreur critique Gemini lors de l'analyse : {e}")
            raise e

    if use_openai and not use_gemini and not use_openrouter:
        try:
            client = OpenAI(api_key=openai_key)
            
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

# -----------------------------------------------------------------------
# Endpoint POST /api/trends  — Moteur de Tendances Multi-Match
# -----------------------------------------------------------------------
class TrendsRequest(BaseModel):
    query: str
    competitions: Optional[List[str]] = None  # ex: ["UCL", "Ligue 1"]

class TrendsResponse(BaseModel):
    synthesis: str
    matches_analyzed: List[str]
    chunks_used: int

@app.post("/api/trends", response_model=TrendsResponse)
async def analyze_trends(request: TrendsRequest):
    """
    Analyse macro / comparative sur plusieurs matchs de la saison PSG.
    Exemples :
      - "Compare le pressing face à l'Inter et face à Man City"
      - "Évolution du rôle de Vitinha cette saison"
      - "Analyse de l'efficacité offensive en Ligue des Champions"
    """
    result = trend_engine.analyze(
        query=request.query,
        competitions=request.competitions,
    )
    return TrendsResponse(
        synthesis=result["synthesis"],
        matches_analyzed=result["matches_analyzed"],
        chunks_used=result["chunks_used"],
    )


class ScrapeMatchRequest(BaseModel):
    url: str
    match_id: str

@app.post("/api/scrape-match")
async def scrape_match(request: ScrapeMatchRequest, db: Session = Depends(get_sql_db)):
    """
    Scrape les stats FBref d'un match et les enregistre dans SQLite.
    """
    scraper = FootballScraperEngine()
    result_msg = scraper.fetch_and_save_match_stats(request.url, request.match_id, db)
    if result_msg.startswith("Erreur"):
        return {"status": "error", "message": result_msg}
    return {"status": "success", "message": result_msg}


class BulkScrapeMatchItem(BaseModel):
    url: str
    match_id: str


class BulkScrapeRequest(BaseModel):
    matches: List[BulkScrapeMatchItem]


def background_bulk_scrape(matches: List[Dict[str, str]]):
    import logging
    logger = logging.getLogger("app.main")
    logger.info(f"[BackgroundScrape] Démarrage de l'ingestion de {len(matches)} matches...")
    db = SessionLocal()
    try:
        run_bulk_ingestion(matches, db)
    except Exception as e:
        logger.error(f"[BackgroundScrape] Erreur lors de l'ingestion en arrière-plan : {e}")
    finally:
        db.close()


@app.post("/api/bulk-scrape")
async def bulk_scrape(request: BulkScrapeRequest, background_tasks: BackgroundTasks):
    """
    Lance l'ingestion de masse en arrière-plan (non bloquant).
    """
    match_list = [{"url": m.url, "match_id": m.match_id} for m in request.matches]
    background_tasks.add_task(background_bulk_scrape, match_list)
    return {
        "status": "pending",
        "message": f"Ingestion de masse lancée pour {len(match_list)} matches en arrière-plan."
    }


@app.on_event("startup")
async def startup_event():
    # Création des tables SQL si elles n'existent pas
    Base.metadata.create_all(bind=engine)
    # S'assurer que les variables de configuration sont chargées correctement (au moins une clé LLM)
    assert settings.OPENAI_API_KEY is not None or settings.gemini_key != "", "Aucune clé API (OpenAI ou Gemini) n'a pu être chargée !"
    # Initialiser le RAG
    rag_engine.initialize()
    print("Football IQ Assistant API démarrée avec succès.")

