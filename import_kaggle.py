import os
import sqlite3
from pathlib import Path
import kagglehub
import pandas as pd

def import_season(dataset_name: str, match_id: str, db_path: Path):
    print(f"\n⏳ Téléchargement du dataset {dataset_name} depuis Kaggle...")
    try:
        download_path = kagglehub.dataset_download(dataset_name)
        print(f"✅ Dataset récupéré avec succès dans : {download_path}")
    except Exception as e:
        print(f"❌ Erreur lors du téléchargement Kaggle : {str(e)}")
        return

    csv_files = list(Path(download_path).glob("*.csv"))
    if not csv_files:
        print("❌ Erreur : Aucun fichier CSV trouvé dans le dossier téléchargé.")
        return
    
    csv_path = csv_files[0]
    print(f"📖 Lecture du fichier : {csv_path.name}")
    df = pd.read_csv(csv_path, encoding='utf-8')

    team_col = [col for col in df.columns if col.lower() in ['squad', 'team']]
    if not team_col:
        print(f"❌ Impossible de trouver la colonne d'équipe. Colonnes dispos : {list(df.columns)}")
        return
    
    squad_column = team_col[0]
    df_psg = df[df[squad_column].str.contains("Paris", case=False, na=False)].copy()
    
    if df_psg.empty:
        print(f"⚠️ Aucun joueur trouvé pour le PSG avec le mot-clé 'Paris' dans la colonne {squad_column}.")
        return
    
    print(f"⚽ {len(df_psg)} joueurs du PSG identifiés.")

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Recherche de la colonne Passes Clés si elle existe (parfois 'KP' ou 'Passes_Key')
    kp_col = [col for col in df.columns if col.upper() in ['KP', 'KEY_PASSES', 'PASSES_KEY']]

    print(f"⚡ Injection des statistiques pour {match_id} dans la base de données...")
    rows_inserted = 0
    for _, row in df_psg.iterrows():
        player_name = row.get('Player', 'Inconnu')
        goals = int(row.get('Gls', 0))
        xg = float(row.get('xG', 0)) if pd.notna(row.get('xG')) else 0.0
        xa = float(row.get('xAG', 0)) if pd.notna(row.get('xAG')) else 0.0
        minutes = int(row.get('Min', 0)) if pd.notna(row.get('Min')) else 0
        key_passes = int(row.get(kp_col[0], 0)) if kp_col and pd.notna(row.get(kp_col[0])) else 0
        
        dribbles = int(row.get('PrgC', 0)) if pd.notna(row.get('PrgC')) else 0
        pressions = int(goals * 4 + key_passes * 2)

        try:
            cursor.execute("""
                INSERT INTO player_match_stats 
                (match_id, player_name, minutes_played, goals, expected_goals, expected_assists, key_passes, progressive_dribbles, defensive_pressures)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (match_id, player_name, minutes, goals, xg, xa, key_passes, dribbles, pressions))
            rows_inserted += 1
        except Exception as e:
            # Si contrainte d'unicité (match_id, player_name déjà existants), mise à jour
            cursor.execute("""
                UPDATE player_match_stats 
                SET minutes_played=?, goals=?, expected_goals=?, expected_assists=?, key_passes=?, progressive_dribbles=?, defensive_pressures=?
                WHERE match_id=? AND player_name=?
            """, (minutes, goals, xg, xa, key_passes, dribbles, pressions, match_id, player_name))
            rows_inserted += 1

    conn.commit()
    conn.close()
    print(f"🎉 Opération réussie ! {rows_inserted} profils de joueurs mis à jour pour {match_id}.")

def main():
    base_dir = Path(__file__).resolve().parent
    db_path = base_dir / "backend" / "data" / "football_iq.db"
    if not db_path.exists():
        print(f"❌ La base de données n'existe pas au chemin : {db_path}")
        return

    # Ingestion de la saison 2024-2025
    import_season("hubertsidorowicz/football-players-stats-2024-2025", "season_2024_2025_summary", db_path)

    # Ingestion de la saison 2025-2026
    import_season("hubertsidorowicz/football-players-stats-2025-2026", "season_2025_2026_summary", db_path)

if __name__ == "__main__":
    main()
