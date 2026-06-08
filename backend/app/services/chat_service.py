import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from openai import OpenAI
from app.core.config import settings
from app.services.rag_engine import RAGEngine
from app.schemas.chat import ChatMode, ChatRequest, ChatResponse, SourceReference

# Dossier des prompts
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

class ChatService:
    """
    Service de Chat orchestrant la recherche RAG et la génération LLM
    selon différents profils d'assistance footballistique.
    """
    def __init__(self, rag_engine: RAGEngine, openai_api_key: Optional[str] = None):
        self.rag_engine = rag_engine
        self.api_key = openai_api_key
        self.prompts: Dict[ChatMode, str] = {}
        self._load_prompts()

    def _load_prompts(self):
        """
        Charge les fichiers de prompts système depuis le disque.
        """
        modes_files = {
            ChatMode.COACH: "coach_prompt.txt",
            ChatMode.ANALYST: "analyst_prompt.txt",
            ChatMode.FAN: "fan_prompt.txt"
        }
        
        for mode, filename in modes_files.items():
            path = PROMPTS_DIR / filename
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        self.prompts[mode] = f.read().strip()
                except Exception as e:
                    print(f"Erreur de chargement du prompt {filename} : {e}")
                    self.prompts[mode] = self._get_fallback_prompt_text(mode)
            else:
                self.prompts[mode] = self._get_fallback_prompt_text(mode)

    def _get_fallback_prompt_text(self, mode: ChatMode) -> str:
        """
        Prompts de secours codés en dur au cas où les fichiers texte soient absents.
        """
        if mode == ChatMode.COACH:
            return "Tu es un coach tactique de football. Reste structuré, concret et technique."
        elif mode == ChatMode.ANALYST:
            return "Tu es un analyste vidéo tactique. Sois clinique, objectif et analytique."
        else:
            return "Tu es un supporter passionné. Sois enthousiaste et familier."

    def generate_response(self, request: ChatRequest) -> ChatResponse:
        # 1. Recherche RAG
        search_results = self.rag_engine.search(request.message, top_k=3)
        
        # Formater les sources Pydantic
        sources = [
            SourceReference(
                text=res["text"],
                source=res["source"],
                score=res["score"]
            )
            for res in search_results
        ]
        
        # 2. Récupérer le prompt système correspondant au mode
        system_prompt = self.prompts.get(request.mode, self._get_fallback_prompt_text(request.mode))
        
        # 3. Construire le contexte pour le prompt utilisateur
        rag_context = ""
        if search_results:
            rag_context = "\n\n".join([
                f"--- EXTRAIT SOURCE: {res['source']} ---\n{res['text']}"
                for res in search_results
            ])
            
        user_prompt = f"""[CONTEXTE DE LA BASE DE CONNAISSANCES TACTIQUES]
{rag_context if rag_context else "Aucun document tactique pertinent trouvé dans la base de connaissances."}

[CONSIGNE CRITIQUE]
Base-toi uniquement sur le contexte ci-dessus si présent pour répondre à la question. Ne sors pas du cadre footballistique.

[MESSAGE DE L'UTILISATEUR]
{request.message}"""

        # 4. Génération (OpenAI ou Fallback Mock local)
        use_openai = False
        if self.api_key and not self.api_key.startswith("mock-") and len(self.api_key.strip()) > 0:
            use_openai = True

        if use_openai:
            try:
                client = OpenAI(api_key=self.api_key)
                
                # Construire les messages pour le chat completion
                messages = [{"role": "system", "content": system_prompt}]
                
                # Ajouter l'historique s'il existe (limité aux 5 derniers messages pour éviter de saturer la fenêtre)
                if request.history:
                    for h in request.history[-5:]:
                        messages.append({"role": h.role, "content": h.content})
                        
                messages.append({"role": "user", "content": user_prompt})
                
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.2
                )
                
                answer = response.choices[0].message.content
                return ChatResponse(
                    answer=answer,
                    mode=request.mode,
                    sources=sources
                )
            except Exception as e:
                print(f"Erreur lors de l'appel OpenAI : {e}. Bascule sur le fallback local mock.")

        # Fallback Mock enrichi
        answer = self._generate_mock_response(request.mode, request.message, sources)
        return ChatResponse(
            answer=answer,
            mode=request.mode,
            sources=sources
        )

    def _generate_mock_response(self, mode: ChatMode, query: str, sources: List[SourceReference]) -> str:
        """
        Génère une réponse simulée crédible en intégrant les données du RAG.
        """
        source_names = ", ".join(list(set([s.source for s in sources]))) if sources else "aucune"
        top_text = ""
        if sources:
            # Extraire une ligne ou deux du premier chunk pour simuler l'intégration
            lines = sources[0].text.split("\n")
            # Ignorer le préfixe [...]
            relevant_lines = [l for l in lines if not l.startswith("[") and l.strip()]
            if relevant_lines:
                top_text = relevant_lines[0]

        if mode == ChatMode.COACH:
            return f"""### 📋 Analyse du Coach
Voici mon plan d'action pour aborder votre question : "{query}".
En me basant sur nos principes tactiques (sources consultées : {source_names}), voici ce qu'il faut retenir :
> {top_text if top_text else "Nous devons rester structurés et agressifs dans les zones définies."}

### 🏃‍♂️ Consignes Individuelles/Collectives
1. **Pression immédiate** : Dès la perte, le joueur le plus proche cadre le porteur.
2. **Compensation** : Les milieux axiaux coulissent pour fermer l'intérieur.

### ⚽ Exercice Recommandé sur le Terrain
* **Jeu de transition 4 contre 4 + 3 jokers** sur terrain réduit (30x40m).
* **Objectif** : Travailler la vitesse de réaction à la perte et la fermeture rapide des lignes de passes internes."""

        elif mode == ChatMode.ANALYST:
            return f"""### 🔍 Observations Structurelles
Analyse technique suite à votre requête : "{query}".
Les données RAG extraites (fichiers : {source_names}) mettent en évidence les comportements structurels suivants :
* **Animation principale** : {top_text if top_text else "Mise en place d'une structure géométrique rigoureuse."}
* **Bloc de hauteur** : Déploiement d'un bloc médian compact garantissant la couverture des interlignes.

### 📐 Schéma de Transition / Animation
Lors de la phase active, l'équipe se réorganise en supériorité numérique axiale (structure de type double pivot).

### ⚖️ Forces/Faiblesses du Système
* **Force** : Excellente couverture des demi-espaces.
* **Faiblesse** : Vulnérabilité sur les flancs en cas de transition rapide de l'adversaire."""

        else: # Fan Passionné
            return f"""### 📣 L'Avis du Virage
Ah mon pote, parlons-en de ça : "{query}" !
Dans les tribunes, on ne jure que par ça ! En plus, nos grimoires ({source_names}) le disent bien :
"{top_text if top_text else "Il faut tout donner et mouiller le maillot !"}"

### ⭐️ Le Joueur Clé
Notre numéro 6, un vrai guerrier qui ratisse tous les ballons au milieu et distribue proprement !

### 🔥 La Tribune s'enflamme
Si les gars appliquent ces consignes de pressing et se projettent vite vers l'avant, ça va chanter très fort dans le virage ! Allez, tous au stade !"""
