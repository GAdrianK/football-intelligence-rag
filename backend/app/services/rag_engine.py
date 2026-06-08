import os
from typing import List, Dict, Any, Optional
from app.services.document_loader import DocumentLoader
from app.services.embedding_provider import (
    EmbeddingProvider,
    OpenAIEmbeddingProvider,
    TFIDFEmbeddingProvider,
    get_cosine_similarity
)

class RAGEngine:
    """
    Moteur RAG (Retrieval-Augmented Generation) local en mémoire.
    Charge, découpe, vectorise les fiches tactiques et recherche sémantiquement.
    """
    def __init__(self, knowledge_base_dir: str, openai_api_key: Optional[str] = None):
        self.kb_dir = knowledge_base_dir
        self.api_key = openai_api_key
        
        self.loader = DocumentLoader(self.kb_dir)
        self.chunks: List[Dict[str, Any]] = []
        self.embeddings: List[List[float]] = []
        self.provider: Optional[EmbeddingProvider] = None
        self.mode = "offline"  # ou "online" (OpenAI)

    def initialize(self):
        """
        Initialise le moteur RAG : charge les documents, sélectionne le provider d'embeddings
        et génère l'index en mémoire.
        """
        print(f"Initialisation du RAGEngine avec la base : {self.kb_dir}")
        self.chunks = self.loader.load_all_documents()
        
        if not self.chunks:
            print("Avertissement : Aucun document trouvé dans la base de connaissances.")
            return

        texts = [chunk["text"] for chunk in self.chunks]
        
        # Sélection du fournisseur d'embeddings
        use_openai = False
        if self.api_key and not self.api_key.startswith("mock-") and len(self.api_key.strip()) > 0:
            use_openai = True
            
        if use_openai:
            try:
                print("Sélection du mode : OpenAI Embeddings (En ligne)")
                openai_provider = OpenAIEmbeddingProvider(api_key=self.api_key)
                # Test de connexion rapide sur un mini-texte
                openai_provider.get_embedding("test")
                
                # Calculer les embeddings pour tous les chunks
                self.embeddings = openai_provider.get_embeddings(texts)
                self.provider = openai_provider
                self.mode = "online"
                print(f"Indexation réussie de {len(self.chunks)} chunks via OpenAI.")
                return
            except Exception as e:
                print(f"Erreur d'initialisation OpenAI : {e}. Bascule sur le fallback local TF-IDF.")
        
        # Fallback local TF-IDF (sans clé ou si OpenAI a échoué)
        print("Sélection du mode : TF-IDF Local (Hors-ligne)")
        tfidf_provider = TFIDFEmbeddingProvider()
        tfidf_provider.fit(texts)
        self.embeddings = tfidf_provider.get_embeddings(texts)
        self.provider = tfidf_provider
        self.mode = "offline"
        print(f"Indexation locale réussie de {len(self.chunks)} chunks via TF-IDF.")

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Recherche sémantique des chunks les plus proches de la requête.
        """
        if not self.chunks or not self.provider or not self.embeddings:
            return []

        try:
            # Calculer l'embedding de la requête
            query_vector = self.provider.get_embedding(query)
        except Exception as e:
            print(f"Erreur lors du calcul d'embedding de la requête : {e}")
            # Si plantage OpenAI à la requête, on peut essayer d'utiliser un backup ou retourner vide
            return []

        # Calculer le score de similarité pour chaque chunk
        results = []
        for idx, chunk in enumerate(self.chunks):
            chunk_vector = self.embeddings[idx]
            score = get_cosine_similarity(query_vector, chunk_vector)
            results.append({
                "text": chunk["text"],
                "source": chunk["source"],
                "score": round(score, 4),
                "metadata": chunk["metadata"]
            })

        # Trier par score décroissant et renvoyer les top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
