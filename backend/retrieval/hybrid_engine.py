import os
import sys
import json
import re
import math
import logging
from pathlib import Path
from typing import List, Dict, Any

# Ajout du dossier backend au sys.path pour permettre les imports absolus
backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

from app.core.config import settings
from database.vector_store import VectorStoreManager
from app.services.embedding_provider import OpenAIEmbeddingProvider
from database.indexer import generate_deterministic_vector

logger = logging.getLogger(__name__)

# =====================================================================
# IMPLÉMENTATION PURE PYTHON DE BM25 POUR ÉVITER LES ERREURS DE DÉPENDANCE
# =====================================================================
class BM25Searcher:
    """
    Implémentation standard de l'algorithme BM25 pour la recherche lexicale.
    """
    def __init__(self, corpus: List[Dict[str, Any]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus = corpus
        self.corpus_size = len(corpus)
        
        # Pré-découpage en tokens
        self.tokenized_corpus = [self._tokenize(doc["text"]) for doc in corpus]
        
        # Calcul de la longueur moyenne des documents
        total_len = sum(len(doc) for doc in self.tokenized_corpus)
        self.avgdl = total_len / self.corpus_size if self.corpus_size > 0 else 0
        
        self.doc_freqs = []
        self.idf = {}
        self._initialize()

    def _tokenize(self, text: str) -> List[str]:
        # Nettoyage et tokenisation basiques (lettres, chiffres, tirets pour les schémas tactiques)
        text_clean = re.sub(r'[^\w\s-]', ' ', text.lower())
        return [word for word in text_clean.split() if len(word) > 1]

    def _initialize(self):
        df = {}
        for doc in self.tokenized_corpus:
            frequencies = {}
            for word in doc:
                frequencies[word] = frequencies.get(word, 0) + 1
            self.doc_freqs.append(frequencies)
            for word in frequencies:
                df[word] = df.get(word, 0) + 1

        for word, count in df.items():
            # Formule d'IDF classique lissée
            self.idf[word] = math.log((self.corpus_size - count + 0.5) / (count + 0.5) + 1.0)

    def search(self, query: str, indices_filter: List[int] = None) -> List[Dict[str, Any]]:
        """
        Calcule les scores BM25 pour tous les documents ou une sous-sélection (filtre).
        """
        query_tokens = self._tokenize(query)
        scores = []
        
        # Si aucun filtre d'indice, on parcourt tout
        target_indices = indices_filter if indices_filter is not None else range(self.corpus_size)
        
        for idx in target_indices:
            doc_freq = self.doc_freqs[idx]
            doc_len = len(self.tokenized_corpus[idx])
            score = 0.0
            
            for token in query_tokens:
                if token not in self.idf:
                    continue
                
                f = doc_freq.get(token, 0)
                if f > 0:
                    idf_val = self.idf[token]
                    numerator = f * (self.k1 + 1)
                    denominator = f + self.k1 * (1 - self.b + self.b * (doc_len / self.avgdl))
                    score += idf_val * (numerator / denominator)
            
            scores.append((idx, score))
            
        # Trier par score descendant
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores


# =====================================================================
# FONCTION DE FILTRAGE DES MÉTADONNÉES
# =====================================================================
def matches_metadata(metadata: Dict[str, Any], filter_dict: Dict[str, Any]) -> bool:
    """
    Vérifie si les métadonnées d'un chunk matchent le filtre spécifié.
    """
    if not filter_dict:
        return True
        
    for key, val in filter_dict.items():
        # Retirer le préfixe 'metadata.' éventuel
        clean_key = key.replace("metadata.", "")
        
        if clean_key not in metadata:
            return False
            
        chunk_val = metadata[clean_key]
        
        # Gestion des listes (ex: tag_tactique ou equipes)
        if isinstance(val, list):
            if isinstance(chunk_val, list):
                if not any(v in chunk_val for v in val):
                    return False
            else:
                if chunk_val not in val:
                    return False
        else:
            if isinstance(chunk_val, list):
                if val not in chunk_val:
                    return False
            else:
                if chunk_val != val:
                    return False
    return True


# =====================================================================
# MOTEUR DE RECHERCHE HYBRIDE PRINCIPAL
# =====================================================================
class HybridSearchEngine:
    """
    Moteur de recherche hybride combinant sémantique (Qdrant) et lexical (BM25).
    """
    def __init__(self):
        self.vector_store = VectorStoreManager()
        self.processed_dir = Path(settings.get_processed_data_dir())
        self.chunks_file = self.processed_dir / "chunks.jsonl"
        
        # Charger tous les chunks enfants pour BM25
        self.chunks: List[Dict[str, Any]] = []
        self._load_corpus()
        
        # Initialiser le searcher BM25
        if self.chunks:
            self.bm25 = BM25Searcher(self.chunks)
        else:
            self.bm25 = None
            logger.warning("Corpus vide ! BM25 ne sera pas opérationnel.")
            
        # Initialiser OpenAI Embedding Provider
        api_key = settings.OPENAI_API_KEY
        self.use_openai = api_key and not api_key.startswith("mock-") and len(api_key.strip()) > 0
        if self.use_openai:
            self.emb_provider = OpenAIEmbeddingProvider(api_key=api_key)
        else:
            self.emb_provider = None

    def _load_corpus(self):
        if not self.chunks_file.exists():
            logger.warning(f"Fichier chunks {self.chunks_file} introuvable pour BM25.")
            return
            
        with open(self.chunks_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    self.chunks.append(json.loads(line))
        logger.info(f"Chargement de {len(self.chunks)} chunks pour l'index lexical BM25.")

    def search(self, query: str, top_k: int = 10, filter_dict: dict = None) -> List[Dict[str, Any]]:
        """
        Exécute la recherche hybride (Qdrant + BM25) avec pondération de score.
        """
        if not self.chunks:
            return []

        # 1. Obtenir le vecteur de requête sémantique
        try:
            if self.use_openai and self.emb_provider:
                query_vector = self.emb_provider.get_embedding(query)
            else:
                query_vector = generate_deterministic_vector(query)
        except Exception as e:
            logger.error(f"Erreur vectorisation requête, fallback simulation : {e}")
            query_vector = generate_deterministic_vector(query)

        # 2. Recherche Sémantique (Qdrant)
        # On remonte un pool large (ex: 50 résultats) pour fusionner ensuite
        semantic_results = self.vector_store.search_semantic(
            query_vector=query_vector,
            top_k=min(50, len(self.chunks)),
            filter_dict=filter_dict
        )
        
        semantic_map = {}
        for hit in semantic_results:
            # Récupérer l'ID unique (Qdrant point ID ou l'ID dans le payload)
            point_id = hit.payload["metadata"]["id"]
            semantic_map[point_id] = {
                "score": hit.score,
                "text": hit.payload["text"],
                "parent_id": hit.payload["parent_id"],
                "metadata": hit.payload["metadata"]
            }

        # 3. Recherche Lexicale (BM25)
        # Filtrer le corpus BM25 pour respecter le filtre de métadonnées
        indices_filter = []
        for idx, doc in enumerate(self.chunks):
            if matches_metadata(doc["metadata"], filter_dict):
                indices_filter.append(idx)
                
        bm25_results = []
        if self.bm25 and indices_filter:
            bm25_results = self.bm25.search(query, indices_filter=indices_filter)

        bm25_map = {}
        for rank, (idx, score) in enumerate(bm25_results[:50]):
            doc = self.chunks[idx]
            point_id = doc["metadata"]["id"]
            bm25_map[point_id] = {
                "score": score,
                "text": doc["text"],
                "parent_id": doc["metadata"].get("parent_id", ""),  # Note : run_etl n'a pas encore le parent_id dans le jsonl
                "metadata": doc["metadata"]
            }

        # 4. Fusion des scores (Min-Max Normalization)
        # Récupérer l'union des IDs
        all_ids = set(semantic_map.keys()).union(set(bm25_map.keys()))
        
        # Valeurs min/max pour normaliser les scores sémantiques (entre 0 et 1)
        sem_scores = [val["score"] for val in semantic_map.values()]
        min_sem = min(sem_scores) if sem_scores else 0.0
        max_sem = max(sem_scores) if sem_scores else 1.0
        sem_range = (max_sem - min_sem) if (max_sem - min_sem) > 0 else 1.0

        # Valeurs min/max pour normaliser les scores BM25
        lex_scores = [val["score"] for val in bm25_map.values()]
        min_lex = min(lex_scores) if lex_scores else 0.0
        max_lex = max(lex_scores) if lex_scores else 1.0
        lex_range = (max_lex - min_lex) if (max_lex - min_lex) > 0 else 1.0

        hybrid_results = []
        
        for pid in all_ids:
            # 1. Score sémantique normalisé
            if pid in semantic_map:
                sem_raw = semantic_map[pid]["score"]
                sem_norm = (sem_raw - min_sem) / sem_range
                text = semantic_map[pid]["text"]
                parent_id = semantic_map[pid]["parent_id"]
                metadata = semantic_map[pid]["metadata"]
            else:
                sem_raw = 0.0
                sem_norm = 0.0
                # Charger le texte depuis la map BM25
                text = bm25_map[pid]["text"]
                metadata = bm25_map[pid]["metadata"]
                # Générer le parent_id si manquant
                import uuid
                parent_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, metadata["source"]))

            # 2. Score BM25 normalisé
            if pid in bm25_map:
                lex_raw = bm25_map[pid]["score"]
                lex_norm = (lex_raw - min_lex) / lex_range
            else:
                lex_raw = 0.0
                lex_norm = 0.0

            # Calcul du score hybride (70% Sémantique, 30% Lexical)
            hybrid_score = 0.7 * sem_norm + 0.3 * lex_norm
            
            hybrid_results.append({
                "id": pid,
                "text": text,
                "parent_id": parent_id,
                "metadata": metadata,
                "scores": {
                    "semantic_raw": sem_raw,
                    "semantic_normalized": sem_norm,
                    "lexical_raw": lex_raw,
                    "lexical_normalized": lex_norm,
                    "hybrid": hybrid_score
                }
            })

        # Trier par score hybride décroissant et renvoyer le top_k
        hybrid_results.sort(key=lambda x: x["scores"]["hybrid"], reverse=True)
        return hybrid_results[:top_k]
