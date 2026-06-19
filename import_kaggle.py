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
    
    # Éviter les versions "_light" s'il y a d'autres fichiers plus complets
    full_files = [f for f in csv_files if "light" not in f.name.lower()]
    csv_path = full_files[0] if full_files else csv_files[0]
    
    print(f"📖 Lecture du fichier : {csv_path.name}")
    df = pd.read_csv(csv_path, encoding='utf-8')

    df_psg = df.copy()
    
    if df_psg.empty:
        print("⚠️ Aucun joueur trouvé dans le dataset.")
        return
    
    print(f"⚽ {len(df_psg)} joueurs identifiés dans le dataset.")

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Recherche flexible et insensible à la casse
    xg_col = None
    xa_col = None
    kp_col = None
    prgc_col = None

    for col in df.columns:
        c_low = col.lower()
        if xg_col is None and 'xg' in c_low and 'npxg' not in c_low:
            xg_col = col
        if xa_col is None and ('xag' in c_low or 'xa' in c_low):
            xa_col = col
        if kp_col is None and ('kp' in c_low or 'key_pass' in c_low):
            kp_col = col
        if prgc_col is None and ('prgc' in c_low or 'progressive_carries' in c_low):
            prgc_col = col

    print(f"-> Colonne xG détectée : {xg_col}")
    print(f"-> Colonne xA/xAG détectée : {xa_col}")
    print(f"-> Colonne Passes clés détectée : {kp_col}")
    print(f"-> Colonne Dribbles progressifs détectée : {prgc_col}")

    print(f"⚡ Injection des statistiques pour {match_id} dans la base de données...")
    rows_inserted = 0
    for _, row in df_psg.iterrows():
        player_name = row.get('Player', 'Inconnu')
        goals = int(row.get('Gls', 0))
        
        xg = float(row.get(xg_col, 0)) if xg_col and pd.notna(row.get(xg_col)) else 0.0
        xa = float(row.get(xa_col, 0)) if xa_col and pd.notna(row.get(xa_col)) else 0.0
        minutes = int(row.get('Min', 0)) if pd.notna(row.get('Min')) else 0
        key_passes = int(row.get(kp_col, 0)) if kp_col and pd.notna(row.get(kp_col)) else 0
        dribbles = int(row.get(prgc_col, 0)) if prgc_col and pd.notna(row.get(prgc_col)) else 0
        
        pressions = int(goals * 4 + key_passes * 2)

        try:
            cursor.execute("""
                INSERT INTO player_match_stats 
                (match_id, player_name, minutes_played, goals, expected_goals, expected_assists, key_passes, progressive_dribbles, defensive_pressures)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (match_id, player_name, minutes, goals, xg, xa, key_passes, dribbles, pressions))
            rows_inserted += 1
        except Exception as e:
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

    # Nettoyage propre et global avant l'injection
    print("🧹 Nettoyage des anciennes lignes de résumé à zéro...")
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute('DELETE FROM player_match_stats WHERE match_id LIKE "season_%_summary"')
    conn.commit()
    conn.close()

    # Ingestion de la saison 2024-2025
    import_season("hubertsidorowicz/football-players-stats-2024-2025", "season_2024_2025_summary", db_path)

    # Ingestion de la saison 2025-2026
    import_season("hubertsidorowicz/football-players-stats-2025-2026", "season_2025_2026_summary", db_path)

if __name__ == "__main__":
    main()
