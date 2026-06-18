import os
import sqlite3
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
ai_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)

DB_PATH = str(BASE_DIR / "data" / "football_iq.db")

class AnalysisRequest(BaseModel):
    prompt: str
    season: Optional[str] = "season_2025_2026_summary"

def fetch_player_stats_from_db(player_query: str, season: str):
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

@app.post("/api/analyze")
async def analyze_tactical_trends(request: AnalysisRequest):
    try:
        words = request.prompt.split()
        potential_players = [w for w in words if len(w) > 3 and w[0].isupper() or w.lower() in request.prompt.lower()]
        
        sql_context = []
        for word in potential_players:
            stats = fetch_player_stats_from_db(word, request.season)
            if stats:
                sql_context.extend(stats)
        
        sql_context = {v['player_name']: v for v in sql_context}.values()

        system_instruction = (
            "Tu es l'ingénieur tactique en chef d'un club de football d'élite mondiale.\n"
            "Tu dois baser tes rapports exclusivement sur les statistiques réelles fournies.\n"
            "Formatte tes réponses en Markdown clair, avec des tableaux comparatifs, "
            "des puces lisibles et des directives de coaching exploitables."
        )
        
        user_message = f"Requête tactique de l'utilisateur : {request.prompt}\n\n"
        if sql_context:
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
            model="qwen/qwen-2.5-72b-instruct:free",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_message}
            ],
            temperature=0.3
        )
        
        return {
            "status": "success",
            "query": request.prompt,
            "season_analyzed": request.season,
            "players_found": [p['player_name'] for p in sql_context],
            "analysis": response.choices[0].message.content
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    return {"status": "online", "engine": "Qwen-2.5-72B-via-OpenRouter", "database": "Connected"}
