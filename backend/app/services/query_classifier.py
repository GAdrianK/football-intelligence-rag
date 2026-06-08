import re
from typing import Dict, Any

class QueryClassifier:
    """
    Classifie les requêtes de l'utilisateur pour déterminer le type
    (salutation, hors-sujet, question tactique) et extraire les intentions sémantiques.
    """
    def __init__(self):
        # Mots-clés pour les salutations
        self.greeting_patterns = [
            r"\b(salut|bonjour|bonsoir|hello|hey|yo|coucou|hi)\b",
            r"\bca\s+va\b",
            r"\bcomment\s+ca\s+va\b",
            r"\bcomment\s+allez-vous\b",
            r"\bcomment\s+vas-tu\b"
        ]
        
        # Mots-clés hors-sujet (cuisine, météo, actualités, politique, etc.)
        self.out_of_scope_patterns = [
            r"\bpizza\b",
            r"\brecette\b",
            r"\bcuisine\b",
            r"\bmeteo\b",
            r"\bmétéo\b",
            r"\bpolitique\b",
            r"\bcinema\b",
            r"\bcinéma\b",
            r"\bfilm\b",
            r"\bmusique\b",
            r"\bchanson\b",
            r"\bprésident\b",
            r"\bpresident\b",
            r"\bmacron\b",
            r"\bgouvernement\b",
            r"\bclimat\b"
        ]

        # Dictionnaires d'intentions
        self.intent_keywords = {
            "defend": [
                "défend", "defend", "couliss", "compac", "fermer l'axe", "défens", "defens",
                "marquage", "recul-frein", "garer le bus", "fermer les espaces", "repli", "reconstitution"
            ],
            "attack": [
                "attaqu", "attack", "déséquilibr", "desequilibr", "percer", "contourn", "marqu",
                "offens", "centr", "dédoubl", "dedoubl", "amplitude", "surcharge", "overload",
                "underlap", "overlap", "creer des espaces", "créer des espaces"
            ],
            "roles": [
                "faux 9", "pivot", "double pivot", "box-to-box", "gardien-libero", "gardien-libéro",
                "sweeper keeper", "inverted fullback", "latéral inversé", "relayeur", "mezzala",
                "raumdeuter", "inside forward", "piston"
            ],
            "formations": [
                "4-3-3", "3-5-2", "4-4-2", "3-4-3", "3-2-4-1", "4-2-3-1",
                "433", "352", "442", "343", "3241", "4231",
                "système", "systeme", "formation"
            ]
        }

        # Dictionnaires de phases
        self.phase_keywords = {
            "offensive": ["attaqu", "offens", "possession", "construction", "finition"],
            "defensive": ["défend", "défens", "defens", "repli", "recule", "coulisse", "marquage"],
            "transition": ["transition", "contre-press", "gegenpress", "récupér", "perte", "contre-attaq", "recupér"]
        }

    def classify(self, message: str) -> Dict[str, Any]:
        """
        Analyse le message et renvoie sa classification complète.
        """
        msg_lower = message.lower().strip()
        
        # 1. Vérification des Salutations
        is_greeting = False
        for pattern in self.greeting_patterns:
            if re.search(pattern, msg_lower):
                is_greeting = True
                break
                
        if is_greeting:
            return {
                "type": "greeting",
                "intent": "general",
                "phase": "general"
            }
            
        # 2. Vérification des Hors-Sujets
        is_out_of_scope = False
        for pattern in self.out_of_scope_patterns:
            if re.search(pattern, msg_lower):
                is_out_of_scope = True
                break
                
        if is_out_of_scope:
            return {
                "type": "out_of_scope",
                "intent": "general",
                "phase": "general"
            }
            
        # 3. Extraction des Intentions Tactiques
        detected_intent = "general"
        for intent, keywords in self.intent_keywords.items():
            for kw in keywords:
                if kw in msg_lower:
                    # Permet de prioriser les intentions spécifiques (attack/defend)
                    if detected_intent == "general" or detected_intent in ["roles", "formations"]:
                        detected_intent = intent
                    break
                    
        # 4. Extraction de la Phase de Jeu
        detected_phase = "general"
        for phase, keywords in self.phase_keywords.items():
            for kw in keywords:
                if kw in msg_lower:
                    detected_phase = phase
                    break
                    
        return {
            "type": "tactical_question",
            "intent": detected_intent,
            "phase": detected_phase
        }
