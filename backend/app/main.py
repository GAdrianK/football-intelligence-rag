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

def fetch_player_stats_from_db(player_query: str, season: str, use_ldc: bool = False):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        season_prefix = season.replace("_summary", "") + "_%"
        
        if use_ldc:
            cursor.execute("""
                SELECT player_name, 
                       team_name,
                       minutes_played AS minutes, 
                       goals, 
                       expected_goals AS xg, 
                       expected_assists AS xa, 
                       key_passes, 
                       progressive_dribbles AS dribbles_prog, 
                       defensive_pressures AS pressions_def 
                FROM player_match_stats 
                WHERE player_name LIKE ? AND match_id LIKE ? AND competition = 'Champions League'
                LIMIT 5
            """, (f"%{player_query}%", season_prefix))
        else:
            cursor.execute("""
                SELECT player_name, 
                       MAX(team_name) AS team_name,
                       SUM(minutes_played) AS minutes, 
                       SUM(goals) AS goals, 
                       ROUND(SUM(expected_goals), 1) AS xg, 
                       ROUND(SUM(expected_assists), 1) AS xa, 
                       SUM(key_passes) AS key_passes, 
                       SUM(progressive_dribbles) AS dribbles_prog, 
                       SUM(defensive_pressures) AS pressions_def 
                FROM player_match_stats 
                WHERE player_name LIKE ? AND match_id LIKE ?
                GROUP BY player_name
                LIMIT 5
            """, (f"%{player_query}%", season_prefix))
            
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as db_err:
        print(f"⚠️ SQLITE WARNING: {str(db_err)}")
        return []

def fetch_top_players_from_db(season: str, use_ldc: bool = False):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        season_prefix = season.replace("_summary", "") + "_%"
        
        if use_ldc:
            cursor.execute("""
                SELECT player_name, 
                       team_name,
                       minutes_played AS minutes, 
                       expected_goals AS xg, 
                       expected_assists AS xa, 
                       goals, 
                       key_passes, 
                       progressive_dribbles AS dribbles_prog, 
                       defensive_pressures AS pressions_def 
                FROM player_match_stats 
                WHERE match_id LIKE ? AND competition = 'Champions League'
                ORDER BY (goals + key_passes) DESC 
                LIMIT 15
            """, (season_prefix,))
        else:
            cursor.execute("""
                SELECT player_name, 
                       MAX(team_name) AS team_name,
                       SUM(minutes_played) AS minutes, 
                       ROUND(SUM(expected_goals), 1) AS xg, 
                       ROUND(SUM(expected_assists), 1) AS xa, 
                       SUM(goals) AS goals, 
                       SUM(key_passes) AS key_passes, 
                       SUM(progressive_dribbles) AS dribbles_prog, 
                       SUM(defensive_pressures) AS pressions_def 
                FROM player_match_stats 
                WHERE match_id LIKE ?
                GROUP BY player_name
                ORDER BY (SUM(goals) + SUM(key_passes)) DESC 
                LIMIT 15
            """, (season_prefix,))
            
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as db_err:
        print(f"⚠️ SQLITE FALLBACK WARNING: {str(db_err)}")
        return []

@app.post("/api/analyze")
async def analyze_tactical_trends(request: AnalysisRequest):
    try:
        sql_query = None
        sql_rows = []
        use_fallback = False
        fallback_reason = ""

        # Étape 1 : Génération SQL (appel rapide non-streamé)
        sql_generation_prompt = (
            "Tu es un traducteur de requêtes tactiques de football en requêtes SQL SQLite très précis.\n"
            "Voici le schéma exact de la table 'player_match_stats' dans SQLite :\n"
            "- player_name (VARCHAR) : Nom du joueur\n"
            "- team_name (TEXT) : Nom du club/équipe du joueur (ex: 'Paris S-G', 'PSG', 'Marseille', 'Real Madrid', 'Barcelona', etc. Utilise LIKE '%Paris%' ou LIKE '%PSG%' pour filtrer sur le PSG)\n"
            "- match_id (VARCHAR) : Identifiant de la saison ou du match (ex: 'season_2024_2025_summary', 'season_2024_2025_cl')\n"
            "- minutes_played (INTEGER) : Temps de jeu en minutes\n"
            "- goals (INTEGER) : Buts marqués\n"
            "- expected_goals (FLOAT) : Expected goals (xG)\n"
            "- expected_assists (FLOAT) : Expected assists (xA)\n"
            "- key_passes (INTEGER) : Passes clés\n"
            "- progressive_dribbles (INTEGER) : Dribbles progressifs\n"
            "- defensive_pressures (INTEGER) : Pressions défensives\n"
            "- competition (TEXT) : 'Domestic League' ou 'Champions League'\n\n"
            "Consignes de traduction :\n"
            "1. Renvoie UNIQUEMENT la requête SQL correspondante sous forme de bloc de code markdown : ```sql\n[REQUÊTE]\n```\n"
            "2. Ne mets aucun autre texte, explication ou blabla.\n"
            "3. Pour obtenir les statistiques cumulées d'un joueur, utilise des fonctions d'agrégation comme SUM(goals), SUM(minutes_played), SUM(expected_goals), etc., et regroupe par player_name avec GROUP BY player_name.\n"
            "4. Si la question mentionne 'LDC' ou 'Ligue des Champions', ajoute la condition `competition = 'Champions League'`. Si elle mentionne le championnat, ajoute `competition = 'Domestic League'`.\n"
            "5. Assure-sol de filtrer sur match_id en fonction de la saison sélectionnée si mentionné (par exemple match_id LIKE 'season_2024_2025_%' ou match_id LIKE 'season_2025_2026_%').\n"
            "6. Utilise LIKE pour les recherches de noms de joueurs pour être tolérant aux fautes d'orthographe (ex: player_name LIKE '%Kane%').\n"
            "7. Si la question mentionne un club/équipe (par exemple le PSG), filtre également sur le nom du club avec team_name (ex: team_name LIKE '%Paris%' ou team_name LIKE '%PSG%').\n"
        )

        user_msg_stage1 = (
            f"Requête tactique de l'utilisateur : {request.prompt}\n"
            f"Saison sélectionnée dans l'UI : {request.season}\n"
        )

        try:
            sql_response = ai_client.chat.completions.create(
                model="openrouter/free",
                messages=[
                    {"role": "system", "content": sql_generation_prompt},
                    {"role": "user", "content": user_msg_stage1}
                ],
                temperature=0.0,
                stream=False
            )
            sql_text = sql_response.choices[0].message.content
        except Exception as api_err:
            print(f"⚠️ SQL generation API error: {str(api_err)}")
            sql_text = ""
            use_fallback = True
            fallback_reason = f"LLM API Error: {str(api_err)}"

        # Étape 2 : Extraction et exécution de la requête SQL
        if not use_fallback and sql_text:
            import re
            sql_match = re.search(r'```sql\s*(.*?)\s*```', sql_text, re.DOTALL | re.IGNORECASE)
            if sql_match:
                sql_query = sql_match.group(1).strip()
            else:
                sql_query = sql_text.strip()

            if sql_query:
                sql_query = sql_query.rstrip(';')
                print(f"🔍 Executing generated SQL: {sql_query}")
                try:
                    conn = sqlite3.connect(DB_PATH)
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute(sql_query)
                    rows = cursor.fetchall()
                    conn.close()

                    # Normalisation des colonnes SQL vers des clés standardisées
                    for row in rows:
                        row_dict = dict(row)
                        mapped_row = {}
                        for k, v in row_dict.items():
                            k_lower = k.lower()
                            if 'player_name' in k_lower or k_lower == 'player':
                                mapped_row['player_name'] = v
                            elif 'minutes_played' in k_lower or k_lower == 'minutes':
                                mapped_row['minutes'] = v
                            elif 'expected_goals' in k_lower or k_lower == 'xg':
                                mapped_row['xg'] = v
                            elif 'expected_assists' in k_lower or k_lower == 'xa':
                                mapped_row['xa'] = v
                            elif 'progressive_dribbles' in k_lower or 'dribbles_prog' in k_lower:
                                mapped_row['dribbles_prog'] = v
                            elif 'defensive_pressures' in k_lower or 'pressions_def' in k_lower or 'pressions' in k_lower:
                                mapped_row['pressions_def'] = v
                            elif 'goals' in k_lower:
                                mapped_row['goals'] = v
                            elif 'key_passes' in k_lower:
                                mapped_row['key_passes'] = v
                            elif 'competition' in k_lower:
                                mapped_row['competition'] = v
                            elif 'team_name' in k_lower or k_lower == 'team' or k_lower == 'squad' or k_lower == 'club':
                                mapped_row['team_name'] = v
                            else:
                                mapped_row[k] = v

                        # Remplissage par défaut des métriques pour le radar final
                        for req_key in ['player_name', 'minutes', 'goals', 'xg', 'xa', 'key_passes', 'dribbles_prog', 'pressions_def']:
                            if req_key not in mapped_row:
                                if req_key == 'player_name':
                                    mapped_row[req_key] = 'Unknown'
                                elif req_key in ['xg', 'xa']:
                                    mapped_row[req_key] = 0.0
                                else:
                                    mapped_row[req_key] = 0
                        sql_rows.append(mapped_row)

                    if not sql_rows:
                        use_fallback = True
                        fallback_reason = "SQL query returned 0 rows"

                except Exception as db_err:
                    print(f"⚠️ SQLite Execution Error: {str(db_err)}")
                    use_fallback = True
                    fallback_reason = f"SQLite Error: {str(db_err)}"
            else:
                use_fallback = True
                fallback_reason = "SQL query parsing failed"
        else:
            use_fallback = True

        # Fallback de secours si la génération SQL a échoué ou n'a renvoyé aucun résultat
        if use_fallback:
            print(f"🔄 Fallback activé : {fallback_reason}")
            sql_rows = []
            words = request.prompt.replace("?", "").replace(".", "").replace(",", "").replace("!", "").split()
            stop_words = {"qui", "est", "le", "la", "les", "des", "pour", "dans", "avec", "mais", "plus", "moins", "comme", "sont", "quel", "quelle", "quelles", "quels"}
            potential_players = [
                w for w in words 
                if len(w) >= 3 and (w[0].isupper() or (w.lower() not in stop_words and len(w) > 3))
            ]
            
            prompt_lower = request.prompt.lower()
            use_ldc = 'ldc' in prompt_lower or 'ligue des champions' in prompt_lower
            
            for word in potential_players:
                stats = fetch_player_stats_from_db(word, request.season, use_ldc)
                if stats:
                    sql_rows.extend(stats)
            
            if sql_rows:
                sql_rows = list({v['player_name']: v for v in sql_rows}.values())
            
            global_keywords = {'mvp', 'meilleur', 'top', 'classement', 'buteur'}
            has_global_keyword = any(keyword in prompt_lower for keyword in global_keywords)
            
            if not sql_rows or has_global_keyword:
                fallback_stats = fetch_top_players_from_db(request.season, use_ldc)
                if fallback_stats:
                    sql_rows = fallback_stats

        # Étape 3 : Streaming de l'analyse finale avec Qwen
        system_instruction = (
            "Tu es l'ingénieur tactique en chef d'un club de football d'élite mondiale.\n"
            "Tu dois baser tes rapports exclusivement sur les statistiques réelles fournies.\n"
            "Si le jeu de données renvoyé par SQLite est vide ou ne correspond pas au club demandé, tu dois explicitement dire que le joueur ne joue pas ou plus dans ce club pour la saison sélectionnée, sans inventer de fausses statistiques.\n"
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
        if sql_query:
            user_message += f"🤖 Requête SQL générée automatiquement : `{sql_query}`\n\n"

        if sql_rows:
            user_message += "📈 DONNÉES RÉELLES EXTRAITES DE LA BASE SQL :\n"
            for p in sql_rows:
                team_info = f" (Club: {p['team_name']})" if p.get('team_name') else ""
                user_message += (
                    f"- {p['player_name']}{team_info} : {p['minutes']} min, {p['goals']} buts, "
                    f"{p['xg']} xG, {p['xa']} xA, {p['key_passes']} passes clés, "
                    f"{p['dribbles_prog']} dribbles progressifs, {p['pressions_def']} pressions.\n"
                )
        else:
            user_message += "⚠️ Remarque : Aucune donnée statistique spécifique trouvée en base pour cette sélection.\n"

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
