import os
import sqlite3
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

# Résolution robuste du chemin de base du backend
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(dotenv_path=BASE_DIR / ".env")

app = FastAPI(
    title="Football IQ - Professional Tactical Engine",
    description="API de scouting européen propulsée par Qwen 2.5 & SQLite"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY or "mock-key" in OPENROUTER_API_KEY:
    print("⚠️ WARNING: OPENROUTER_API_KEY is not configured or is a mock key! Calls to Qwen LLM will fail with 401.")
else:
    print("🚀 OPENROUTER_API_KEY correctly loaded.")

ai_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)

DB_PATH = str(BASE_DIR / "data" / "football_iq.db")

class AnalysisRequest(BaseModel):
    prompt: str
    season: Optional[str] = "season_2025_2026_summary"

def fetch_player_stats_from_db(player_query: str, season: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT player_name, 
                   minutes_played AS minutes, 
                   goals, 
                   expected_goals AS xg, 
                   expected_assists AS xa, 
                   key_passes, 
                   progressive_dribbles AS dribbles_prog, 
                   defensive_pressures AS pressions_def 
            FROM player_match_stats 
            WHERE match_id = ? AND player_name LIKE ?
            LIMIT 5
        """, (season, f"%{player_query}%"))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as db_err:
        print(f"⚠️ SQLITE WARNING: {str(db_err)}")
        return []

def fetch_top_players_from_db(season: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT player_name, 
                   minutes_played AS minutes, 
                   expected_goals AS xg, 
                   expected_assists AS xa, 
                   goals, 
                   key_passes, 
                   progressive_dribbles AS dribbles_prog, 
                   defensive_pressures AS pressions_def 
            FROM player_match_stats 
            WHERE match_id = ? 
            ORDER BY (goals + key_passes) DESC 
            LIMIT 15
        """, (season,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as db_err:
        print(f"⚠️ SQLITE FALLBACK WARNING: {str(db_err)}")
        return []

@app.post("/api/analyze")
async def analyze_tactical_trends(request: AnalysisRequest):
    try:
        # Nettoyage et filtrage propre des mots pour éviter d'interroger la base pour des mots-clés courants
        words = request.prompt.replace("?", "").replace(".", "").replace(",", "").replace("!", "").split()
        stop_words = {"qui", "est", "le", "la", "les", "des", "pour", "dans", "avec", "mais", "plus", "moins", "comme", "sont", "quel", "quelle", "quelles", "quels"}
        potential_players = [
            w for w in words 
            if len(w) >= 3 and (w[0].isupper() or (w.lower() not in stop_words and len(w) > 3))
        ]
        
        sql_context = []
        for word in potential_players:
            stats = fetch_player_stats_from_db(word, request.season)
            if stats:
                sql_context.extend(stats)
        
        # Déduplication par nom de joueur
        if sql_context:
            sql_context = list({v['player_name']: v for v in sql_context}.values())
        else:
            sql_context = []

        # Détection des questions globales ou absence de résultats spécifiques
        prompt_lower = request.prompt.lower()
        global_keywords = {'mvp', 'meilleur', 'top', 'classement', 'buteur'}
        has_global_keyword = any(keyword in prompt_lower for keyword in global_keywords)

        is_fallback = False
        if not sql_context or has_global_keyword:
            fallback_stats = fetch_top_players_from_db(request.season)
            if fallback_stats:
                sql_context = fallback_stats
                is_fallback = True

        system_instruction = (
            "Tu es l'ingénieur tactique en chef d'un club de football d'élite mondiale.\n"
            "Tu dois baser tes rapports exclusivement sur les statistiques réelles fournies.\n"
            "Formatte tes réponses en Markdown clair, avec des tableaux comparatifs, "
            "des puces lisibles et des directives de coaching exploitables.\n\n"
            "À la toute fin de ta réponse, après l'analyse textuelle, tu dois TOUJOURS ajouter un bloc de données JSON "
            "structuré sous cette forme exacte, entouré de balises de code markdown (```json ... ```) :\n"
            "```json\n"
            "{\n"
            "  \"chart_type\": \"radar\",\n"
            "  \"metrics\": [\"goals\", \"xg\", \"xa\", \"key_passes\", \"dribbles_prog\", \"pressions_def\"],\n"
            "  \"players\": [\n"
            "    {\"name\": \"NomJoueur1\", \"data\": [goals_val, xg_val, xa_val, key_passes_val, dribbles_prog_val, pressions_def_val]},\n"
            "    {\"name\": \"NomJoueur2\", \"data\": [...]}\n"
            "  ]\n"
            "}\n"
            "```\n"
            "Utilise les vraies valeurs extraites du contexte SQL pour chaque joueur (pas de placeholders, pas de valeurs fictives). "
            "Ne mets aucun texte après ce bloc JSON."
        )
        
        user_message = f"Requête tactique de l'utilisateur : {request.prompt}\n\n"
        if sql_context:
            if is_fallback:
                user_message += "📈 DONNÉES RÉELLES DU TOP 15 DES JOUEURS (Classés par Buts + Passes Clés) :\n"
            else:
                user_message += "📈 DONNÉES RÉELLES EXTRAITES DE LA BASE SQL :\n"
            for p in sql_context:
                user_message += (
                    f"- {p['player_name']} ({request.season}) : {p['minutes']} min, {p['goals']} buts, "
                    f"{p['xg']} xG, {p['xa']} xA, {p['key_passes']} passes clés, "
                    f"{p['dribbles_prog']} dribbles progressifs, {p['pressions_def']} pressions.\n"
                )
        else:
            user_message += "⚠️ Remarque : Aucune donnée statistique spécifique trouvée en base pour cette sélection. Utilise tes connaissances générales sur le Big 5.\n"

        response = ai_client.chat.completions.create(
            model="openrouter/free",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_message}
            ],
            temperature=0.3,
            stream=True
        )
        
        def generate_chunks():
            try:
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
            except Exception as e:
                print(f"💥 ERREUR DE STREAMING : {str(e)}")

        return StreamingResponse(generate_chunks(), media_type="text/plain")
    except Exception as e:
        print(f"💥 ERREUR CRITIQUE BACKEND : {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    return {"status": "online", "engine": "Qwen-2.5-72B-via-OpenRouter", "database": "Connected"}
