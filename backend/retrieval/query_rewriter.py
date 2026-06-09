import json
import logging
import re
from typing import List
from openai import OpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

class QueryRewriter:
    """
    QueryRewriter utilise GPT-4o-mini pour réécrire et diversifier les requêtes tactiques
    afin d'optimiser le taux de rappel (Recall) lors de la recherche hybride.
    """
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.use_openai = self.api_key and not self.api_key.startswith("mock-") and len(self.api_key.strip()) > 0
        if self.use_openai:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None

    def rewrite(self, query: str) -> List[str]:
        """
        Réécrit la requête en 2-3 variations optimisées pour la recherche.
        """
        if not query.strip():
            return []

        if self.use_openai and self.client:
            try:
                system_prompt = (
                    "Tu es un expert en tactique de football spécialisé dans l'ingénierie RAG.\n"
                    "Ton rôle est de prendre une question utilisateur sur le football et de générer "
                    "2 à 3 requêtes de recherche simplifiées ou variations sémantiques (mots-clés, concepts tactiques, équipes) "
                    "qui maximisent les chances de trouver les bons documents dans une base vectorielle.\n"
                    "Exemple :\n"
                    "Question: 'Comment Paris a géré le contre-pressing de l'OM ?'\n"
                    "Variations: [\"PSG pressing Marseille\", \"sortie de balle PSG sous pression\", \"contre-pressing tactique OM\"]\n"
                    "Renvoie uniquement un tableau JSON de chaînes de caractères. Pas de markdown, pas d'explication."
                )

                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Génère des variations pour cette question : '{query}'"}
                    ],
                    temperature=0.2,
                    max_tokens=100
                )
                
                content = response.choices[0].message.content.strip()
                # Nettoyer les balises de code markdown éventuelles
                content = re.sub(r"```json\s*", "", content)
                content = re.sub(r"\s*```", "", content)
                
                variations = json.loads(content)
                if isinstance(variations, list):
                    # S'assurer que la requête d'origine est incluse si elle n'y est pas
                    if query not in variations:
                        variations.insert(0, query)
                    return [v.strip() for v in variations if isinstance(v, str)]
            except Exception as e:
                logger.error(f"Erreur lors du Query Rewriting via OpenAI: {e}. Utilisation du fallback local.")
        
        # Fallback déterministe local par règles (mode hors-ligne ou erreur)
        return self._fallback_rewrite(query)

    def _fallback_rewrite(self, query: str) -> List[str]:
        """
        Génère des variations simples basées sur des règles de mots-clés de football.
        """
        variations = [query]
        query_lower = query.lower()
        
        # Extraction simplifiée de mots tactiques clés
        keywords = []
        for kw in ["pressing", "contre-pressing", "bloc bas", "bloc median", "low-block", "transition", "possession", "lateral", "ailier"]:
            if kw in query_lower:
                keywords.append(kw)
                
        # Extraction simplifiée d'équipes clés
        teams = []
        for team in ["psg", "paris", "om", "marseille", "real", "madrid", "barca", "barcelone"]:
            if team in query_lower:
                teams.append(team)

        if teams and keywords:
            # ex: "psg pressing"
            variations.append(f"{' '.join(teams)} { ' '.join(keywords) }")
        elif keywords:
            # ex: "pressing tactique"
            variations.append(f"{keywords[0]} tactique")
            
        # Variation standard
        variations.append(f"{query} tactique football")
        
        # Dédupliquer tout en gardant l'ordre
        seen = set()
        dedup_vars = []
        for v in variations:
            if v.lower() not in seen:
                seen.add(v.lower())
                dedup_vars.append(v)
                
        return dedup_vars[:3]
